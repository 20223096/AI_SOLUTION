from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.domain import ImpactRequest, TaskAssignment
from app.services.acoustics import energy_sum, reference_energy_exposure
from app.services.data import get_scenario
from app.services.impact import calculate_impact
from app.services.optimizer import optimize
from app.services.pareto import non_dominated_multi
from app.services.prediction import default_assignments, predict
from app.services.sensitivity import sensitivity


TZ = ZoneInfo("Asia/Seoul")
A_DAY = date(2026, 10, 26)
B_DAY = date(2026, 9, 11)
PROFILE = "road_traffic_observed_profile"


@pytest.mark.parametrize("background", [50.0, 70.0, 85.0])
def test_background_masking_does_not_remove_project_energy(background):
    project = 75.0
    total = energy_sum([background, project])
    assert reference_energy_exposure(project, 15) == pytest.approx(150.0)
    assert total > background


def test_reference_energy_exposure_has_linear_duration_and_energy_units():
    assert reference_energy_exposure(65, 15, 65) == pytest.approx(15)
    assert reference_energy_exposure(75, 15, 65) == pytest.approx(150)
    assert reference_energy_exposure(75, 30, 65) == pytest.approx(300)
    with pytest.raises(ValueError):
        reference_energy_exposure(75, -1)


def test_sensitive_time_boundaries_and_assumed_weight_are_both_exposed():
    before = sensitivity(datetime(2026, 10, 26, 6, 59, tzinfo=TZ), "residential")
    at_day = sensitivity(datetime(2026, 10, 26, 7, 0, tzinfo=TZ), "residential")
    exam = sensitivity(datetime(2026, 10, 26, 8, 0, tzinfo=TZ), "university", exam_period=True)
    assert before["is_sensitive_time"] is True and before["weight"] == 1.5
    assert at_day["is_sensitive_time"] is False and at_day["weight"] == 1.0
    assert exam["is_sensitive_time"] is True and exam["weight"] == 1.5
    assert exam["weight_status"] == "assumed"


def test_simultaneous_and_non_simultaneous_event_exposure_are_distinct():
    result = optimize("final-demo-congestion", B_DAY, background_profile=PROFILE)
    simultaneous = next(x for x in result["valid_candidates"] if x.id == "offset-0")
    separate = next(x for x in result["valid_candidates"] if x.id == "offset-120")
    assert simultaneous.objective_values["existing_high_noise_overlap_minutes"] == 180
    assert separate.objective_values["existing_high_noise_overlap_minutes"] == 60
    assert simultaneous.metrics.existing_noise_overlap_receptor_minutes > separate.metrics.existing_noise_overlap_receptor_minutes
    assert simultaneous.metrics.new_project_energy_exposure_65db_ref_minutes == pytest.approx(separate.metrics.new_project_energy_exposure_65db_ref_minutes)


def test_continuous_project_exposure_detects_a_gap():
    scenario = get_scenario("case-a")
    assignments = default_assignments(scenario, A_DAY)
    shifted = [assignments[0]] + [x.model_copy(update={"start": x.start + timedelta(minutes=15), "end": x.end + timedelta(minutes=15)}) for x in assignments[1:]]
    from app.services.metrics import schedule_metrics
    assert schedule_metrics("case-a", A_DAY, assignments).max_continuous_new_project_minutes == 540
    assert schedule_metrics("case-a", A_DAY, shifted).max_continuous_new_project_minutes == 480


def test_multi_axis_pareto_uses_every_axis_without_weighted_sum():
    points = [
        {"id": "a", "energy": 1, "sensitive": 3, "continuous": 2, "change": 2},
        {"id": "b", "energy": 2, "sensitive": 2, "continuous": 2, "change": 1},
        {"id": "c", "energy": 3, "sensitive": 3, "continuous": 3, "change": 3},
    ]
    axes = ["energy", "sensitive", "continuous", "change"]
    assert {x["id"] for x in non_dominated_multi(points, axes)} == {"a", "b"}


def test_schedule_change_definitions_are_not_mixed():
    result = optimize("official_reference_equipment", A_DAY, background_profile=PROFILE)
    shifted = next(x for x in result["valid_candidates"] if x.id == "offset-120")
    assert shifted.schedule_change_details["total_task_start_shift_minutes"] == 480
    assert shifted.schedule_change_details["project_start_shift_minutes"] == 120
    assert shifted.schedule_change_details["project_end_shift_minutes"] == 120
    assert shifted.schedule_change_details["predecessor_order_preserved"] is True
    assert shifted.schedule_change_details["resource_conflicts"] == []


def test_fixed_schedule_validation_scenario_only_allows_original():
    result = optimize("validation-fixed-schedule", A_DAY)
    assert [x.id for x in result["valid_candidates"]] == ["offset-0"]
    assert all(any("변경 불가" in reason for reason in x["infeasibility_reasons"]) for x in result["diagnostics"]["candidate_metrics"][1:])


def test_parallel_equipment_validation_combines_energy_and_reports_both_tasks():
    start = datetime(2026, 10, 26, 7, tzinfo=TZ)
    assignments = [
        TaskAssignment(task_id="cut", start=start, end=start + timedelta(minutes=60)),
        TaskAssignment(task_id="break", start=start, end=start + timedelta(minutes=60)),
    ]
    row = next(x for x in predict("case-a", A_DAY, assignments=assignments)["predictions"] if x["receptor_id"] == "residential-1" and x["slot_start"] == start)
    assert set(row["active_task_ids"]) == {"cut", "break"}
    assert row["new_project_contribution_db"] > 80


def test_different_equipment_durations_are_preserved():
    rows = predict("case-a", A_DAY)["predictions"]
    residential = [x for x in rows if x["receptor_id"] == "residential-1"]
    active_counts = {task: sum(task in row["active_task_ids"] for row in residential) for task in ["cut", "break", "excavate", "compact"]}
    assert active_counts == {"cut": 4, "break": 8, "excavate": 20, "compact": 4}


def test_legacy_saturation_version_and_api_contract_are_preserved():
    saturated = calculate_impact(ImpactRequest(total_noise_db=90, baseline_noise_db=85, duration_minutes=15, continuous_minutes=15, sensitivity_weight=1))
    assert saturated["saturation"]["incremental_zero_despite_increase"] is True
    client = TestClient(app)
    legacy = client.post("/api/schedules/optimize", json={"scenario_id": "final-demo-congestion", "analysis_date": "2026-09-11", "background_profile": PROFILE})
    multi = client.post("/api/schedules/optimize", json={"scenario_id": "final-demo-congestion", "analysis_date": "2026-09-11", "background_profile": PROFILE, "objective_mode": "multi_axis"})
    assert legacy.status_code == multi.status_code == 200
    assert legacy.json()["scoring_version"] == "legacy_v1"
    assert multi.json()["diagnostics"]["pareto_axes"] == ["physical_energy_cost", "sensitive_exposure_cost", "continuous_burden_cost", "change_cost"]
    assert multi.json()["recommended_options"][0]["recommendation_reasons"]


def test_multi_axis_is_deterministic_and_case_d_stays_infeasible():
    first = optimize("final-demo-congestion", B_DAY, background_profile=PROFILE, objective_mode="multi_axis")
    second = optimize("final-demo-congestion", B_DAY, background_profile=PROFILE, objective_mode="multi_axis")
    assert [x.id for x in first["pareto_candidates"]] == [x.id for x in second["pareto_candidates"]]
    assert optimize("scenario-d-restricted", A_DAY, objective_mode="multi_axis")["optimization_status"] == "infeasible"
