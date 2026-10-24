import csv
import json
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.models.domain import SourceMetadata, TaskAssignment, TimeWindow
from app.models.prd_v2_1 import EquipmentPlanningConstraint, FixedTaskConstraint, PRDNoticePlanningInput
from app.services.optimizer import optimize
from app.services.prd_v2_1 import sensitivity_policy_experiment, validate_prd_schedule
from app.services.sensitivity import sensitivity


ROOT = Path(__file__).resolve().parents[2]
TZ = ZoneInfo("Asia/Seoul")
DAY = date(2026, 9, 11)
SOURCE = SourceMetadata(status="user_provided", source="test input")


def moment(hour: int, minute: int = 0, day: int = 11) -> datetime:
    return datetime(2026, 9, day, hour, minute, tzinfo=TZ)


def planning(**updates) -> PRDNoticePlanningInput:
    values = {
        "notice_id": "demo-notice",
        "total_work_window": TimeWindow(start=time(7), end=time(18)),
        "road_excavation": True,
        "road_occupancy_permit_window": TimeWindow(start=time(8), end=time(17)),
        "equipment_constraints": [EquipmentPlanningConstraint(equipment_id="excavator", category="굴착기", specification="06W", max_daily_count=1, required_usage_minutes=60, permitted_time_windows=[TimeWindow(start=time(8), end=time(17))], source_metadata=SOURCE)],
        "fixed_tasks": [FixedTaskConstraint(task_id="restore", fixed_start=time(16), fixed_end=time(17), reason="당일 복구", source_metadata=SOURCE)],
        "same_day_restoration_required": True,
        "project_completion_date": DAY,
        "non_adjustable_conditions": ["restore fixed"],
        "source_evidence": {"page": "p.2"},
        "provenance": "user_provided",
    }
    values.update(updates)
    return PRDNoticePlanningInput(**values)


def test_prd_notice_model_rejects_permit_without_road_excavation():
    with pytest.raises(ValidationError):
        planning(road_excavation=False)


def test_explicit_schedule_constraints_return_infeasible_instead_of_ignoring_them():
    assignments = [
        TaskAssignment(task_id="dig", start=moment(7), end=moment(8)),
        TaskAssignment(task_id="restore", start=moment(16, 15), end=moment(17, 15)),
    ]
    result = validate_prd_schedule(planning(), DAY, assignments, {"restore": ["dig"]}, {"dig": "excavator", "restore": None}, {"restore"})
    assert result["feasible"] is False
    assert {item["code"] for item in result["violations"]} >= {"outside_equipment_time_window", "outside_road_occupancy_permit", "fixed_task_start_changed", "fixed_task_end_changed"}


def test_equipment_count_and_required_usage_are_checked_from_explicit_input():
    assignments = [TaskAssignment(task_id="dig", start=moment(8), end=moment(8, 30)), TaskAssignment(task_id="restore", start=moment(16), end=moment(17))]
    result = validate_prd_schedule(planning(), DAY, assignments, {"restore": ["dig"]}, {"dig": "excavator", "restore": None}, {"restore"}, {"dig": 2})
    assert {item["code"] for item in result["violations"]} >= {"equipment_daily_count_exceeded", "equipment_required_usage_mismatch"}


def test_validator_does_not_invent_universal_07_18_or_08_17_rules():
    custom = planning(total_work_window=TimeWindow(start=time(6), end=time(19)), road_excavation=False, road_occupancy_permit_window=None, equipment_constraints=[], fixed_tasks=[], same_day_restoration_required=False)
    result = validate_prd_schedule(custom, DAY, [TaskAssignment(task_id="early", start=moment(6), end=moment(7))], {}, {"early": None}, set())
    assert result == {"feasible": True, "violations": [], "policy_version": "prd_v2_1_explicit_input_only"}


def test_legacy_sensitivity_shape_and_value_remain_unchanged():
    actual = sensitivity(moment(8), "university", exam_period=True)
    assert actual == {"time_period": "day", "base_weight": 1.0, "adjustments": {"university_exam": 0.5}, "weight": 1.5, "is_sensitive_time": True, "weight_status": "assumed", "status": "assumed"}


@pytest.mark.parametrize("factor", [1.1, 1.3, 1.5])
def test_prd_experimental_sensitivity_uses_maximum_single_multiplier(factor):
    actual = sensitivity(moment(6), "school", policy_version="prd_max_v2_1_experimental", experimental_context_multiplier=factor)
    assert actual["weight"] == 1.5
    assert actual["overlap_rule"] == "maximum_single_multiplier"
    assert actual["adjustments"] == {"experimental_context_multiplier": factor}


def test_prd_experiment_is_separate_and_does_not_change_default_optimizer():
    before = optimize("final-demo-congestion", DAY, background_profile="road_traffic_observed_profile")
    experiment = sensitivity_policy_experiment("final-demo-congestion", DAY, "road_traffic_observed_profile")
    after = optimize("final-demo-congestion", DAY, background_profile="road_traffic_observed_profile")
    assert experiment["status"] == "simulated"
    assert [case["multiplier"] for case in experiment["cases"]] == [1.1, 1.3, 1.5]
    assert [item.id for item in before["pareto_candidates"]] == [item.id for item in after["pareto_candidates"]]
    assert experiment["baseline_recommended_candidate_ids"] == [item["candidate"].id for item in before["recommended_options"]]
    committed = json.loads((ROOT / "data/processed/prd_v2_1_sensitivity_experiment.json").read_text())
    assert [(case["multiplier"], case["recommended_candidate_ids"], case["weighted_sensitive_exposure"]) for case in committed["cases"]] == [
        (case["multiplier"], case["recommended_candidate_ids"], case["recommended_metrics"][0]["sensitivity_weighted_new_project_receptor_minutes"])
        for case in experiment["cases"]
    ]


def test_demo_fixture_matches_sdot_daily_rows_and_quality():
    fixture = json.loads((ROOT / "backend/app/data/demo_2026_09_11.json").read_text())
    with (ROOT / "data/processed/sdot_sinchon_clean.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    for expected in fixture["sdot_daily_audit"]["days"]:
        selected = [row for row in rows if row["observed_at"].startswith(expected["date"])]
        assert len(selected) == expected["row_count"] == 72
        assert len({(row["sensor_serial"], row["observed_at"]) for row in selected}) == 72
        for sensor in expected["sensors"]:
            sensor_rows = [row for row in selected if row["sensor_serial"] == sensor["sensor_serial"]]
            assert sum(row["quality_status"] == "valid" for row in sensor_rows) == sensor["valid_count"]
            assert sum(row["quality_status"] == "held" for row in sensor_rows) == sensor["held_count"]


def test_demo_fixture_keeps_official_and_assumed_events_separate():
    fixture = json.loads((ROOT / "backend/app/data/demo_2026_09_11.json").read_text())
    events = fixture["context_events"]
    official = [event for event in events if event["status"] == "verified_public"]
    waste = next(event for event in events if event["kind"] == "waste_collection")
    assert all(event["noise_db"] is None for event in official)
    assert waste["status"] == "assumed"
    assert fixture["new_demo_notice"]["status"] == "assumed"
