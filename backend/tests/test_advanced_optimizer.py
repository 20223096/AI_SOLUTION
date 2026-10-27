from datetime import date, time

from app.models.domain import ConstructionPeriod, SourceMetadata, TimeWindow
from app.models.prd_v2_1 import EquipmentPlanningConstraint, PRDNoticePlanningInput
from app.services.advanced_optimizer import PARETO_AXES, optimize_advanced
from app.services.pareto import non_dominated_multi
from fastapi.testclient import TestClient
from app.main import app
from tests.test_prd_integrated_workflow import integrated_payload


DAY = date(2026, 9, 11)
SOURCE = SourceMetadata(status="user_provided", source="test-confirmed form")
EQUIPMENT = (("cutter", 60), ("breaker", 120), ("excavator", 300), ("roller", 60))
PREDECESSORS = {"break": ["cut"], "excavate": ["break"], "compact": ["excavate"]}
EQUIPMENT_BY_TASK = {"cut": "cutter", "break": "breaker", "excavate": "excavator", "compact": "roller"}


def planning(start=time(7), end=time(18)) -> PRDNoticePlanningInput:
    return PRDNoticePlanningInput(
        notice_id="advanced-test", project_name="test", location="Sinchon",
        construction_period=ConstructionPeriod(start=DAY, end=DAY),
        total_work_window=TimeWindow(start=start, end=end), road_excavation=False,
        equipment_constraints=[EquipmentPlanningConstraint(equipment_id=e, category=e, max_daily_count=1, required_usage_minutes=minutes, permitted_time_windows=[TimeWindow(start=start, end=end)], source_metadata=SOURCE) for e, minutes in EQUIPMENT],
        same_day_restoration_required=False, project_completion_date=DAY,
        field_provenance={"construction_period": SOURCE, "total_work_window": SOURCE}, provenance="user_provided",
    )


def run(value: PRDNoticePlanningInput, **kwargs):
    return optimize_advanced("final-demo-congestion", DAY, value, PREDECESSORS, EQUIPMENT_BY_TASK, set(), solution_limit=2000, **kwargs)


def test_cp_sat_explores_task_level_schedules_and_reports_only_real_pareto_points():
    result = run(planning())
    assert result["solver"] == "ortools_cp_sat"
    assert result["explored_candidate_count"] > 9
    assert result["search_complete"] is True
    assert result["global_optimality_guaranteed"] is False
    expected = non_dominated_multi([{"id": row.id, **row.objective_values} for row in result["candidates"]], PARETO_AXES)
    assert {row.id for row in result["pareto_candidates"]} == {row["id"] for row in expected}


def test_cp_sat_exact_window_returns_one_real_candidate_without_fabrication():
    result = run(planning(end=time(16)))
    assert result["explored_candidate_count"] == 1
    assert result["pareto_candidate_count"] == 1
    assert len(result["candidates"]) == 1


def test_cp_sat_no_solution_reports_infeasible_reason():
    result = run(planning(start=time(8), end=time(16)))
    assert result["optimization_status"] == "infeasible"
    assert result["candidates"] == []
    assert result["infeasibility_reasons"]


def test_existing_event_toggle_changes_only_the_configured_overlap_experiment():
    with_events = run(planning(), include_existing_events=True)
    without_events = run(planning(), include_existing_events=False)
    assert max(row.metrics.existing_noise_overlap_receptor_minutes for row in with_events["candidates"]) > 0
    assert all(row.metrics.existing_noise_overlap_receptor_minutes == 0 for row in without_events["candidates"])
    assert {tuple((x.task_id, x.start) for x in row.task_assignments) for row in with_events["candidates"]} == {tuple((x.task_id, x.start) for x in row.task_assignments) for row in without_events["candidates"]}


def test_prd_api_keeps_offset_default_and_exposes_cp_sat_as_additive_choice():
    client = TestClient(app)
    legacy = client.post("/api/prd/recommendations/constraint-filtered", json=integrated_payload())
    assert legacy.status_code == 200
    assert legacy.json()["candidate_generation_mode"] == "existing_optimizer_15_minute_offsets_0_to_120"
    payload = integrated_payload()
    payload["recommendation_engine"] = "cp_sat_v2"
    advanced = client.post("/api/prd/recommendations/constraint-filtered", json=payload)
    assert advanced.status_code == 200
    body = advanced.json()
    assert body["solver"] == "ortools_cp_sat"
    assert body["explored_candidate_count"] == 495
    assert body["pareto_candidate_count"] == len(body["candidates"])
    assert body["global_optimality_guaranteed"] is False
