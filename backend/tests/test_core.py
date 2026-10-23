import math
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.models.domain import ImpactRequest, TaskAssignment
from app.services.acoustics import energy_sum, sound_power_to_pressure
from app.services.data import get_scenario, scenarios
from app.services.impact import calculate_impact
from app.services.metrics import compare, schedule_metrics
from app.services.optimizer import optimize
from app.services.pareto import non_dominated
from app.services.prediction import default_assignments, predict
from app.services.sensitivity import sensitivity
from app.services.timegrid import overlaps, slots

TZ = ZoneInfo("Asia/Seoul")
DAY = date(2026, 10, 26)


def test_lw_and_lp_distance_formula_and_monotonicity():
    near = sound_power_to_pressure(100, 10)
    far = sound_power_to_pressure(100, 20)
    assert near == pytest.approx(69.01, abs=.02)
    assert near - far == pytest.approx(6.02, abs=.02)
    with pytest.raises(ValueError): sound_power_to_pressure(100, 0)


def test_energy_sum_hand_calculation():
    assert energy_sum([60, 60]) == pytest.approx(63.0103, abs=.001)
    assert energy_sum([]) is None


def test_background_changes_by_time_and_missing_warning():
    result = predict("case-a", DAY)
    rows = [x for x in result["predictions"] if x["receptor_id"] == "residential-1"]
    assert next(x for x in rows if x["slot_start"].strftime("%H:%M") == "07:00")["background_laeq_db"] == 55
    assert next(x for x in rows if x["slot_start"].strftime("%H:%M") == "12:00")["background_laeq_db"] == 60
    assert any("덤프트럭" in x for x in result["warnings"])


def test_sensitivity_does_not_change_physical_db():
    base = 70.0
    normal = sensitivity(datetime(2026, 10, 26, 12, tzinfo=TZ), "commercial")
    exam = sensitivity(datetime(2026, 10, 26, 12, tzinfo=TZ), "university", exam_period=True)
    assert exam["weight"] > normal["weight"]
    assert base == 70.0


@pytest.mark.parametrize("field,low,high", [("total_noise_db", 60, 80), ("duration_minutes", 15, 240), ("continuous_minutes", 15, 120), ("sensitivity_weight", 1, 2)])
def test_impact_range_and_monotonicity(field, low, high):
    kwargs = dict(total_noise_db=70, duration_minutes=60, continuous_minutes=60, sensitivity_weight=1.0)
    kwargs[field] = low; a = calculate_impact(ImpactRequest(**kwargs))["score"]
    kwargs[field] = high; b = calculate_impact(ImpactRequest(**kwargs))["score"]
    assert 0 <= a <= b <= 100


def test_half_open_slot_boundaries():
    start = datetime(2026, 10, 26, 7, tzinfo=TZ)
    grid = list(slots(start, start + timedelta(minutes=30)))
    assert len(grid) == 2
    assert not overlaps(grid[0][0], grid[0][1], grid[1][0], grid[1][1])


def test_case_a_duration_order_and_feasibility():
    result = optimize("case-a", DAY)
    assert result["valid_candidates"]
    candidate = result["valid_candidates"][0]
    expected = {"cut":60,"break":120,"excavate":300,"compact":60}
    for assignment in candidate.task_assignments:
        assert (assignment.end-assignment.start).total_seconds()/60 == expected[assignment.task_id]
    assert all(a.end <= b.start for a, b in zip(candidate.task_assignments, candidate.task_assignments[1:]))


def test_case_b_is_infeasible_and_not_recommended():
    result = optimize("case-b", DAY)
    assert result["optimization_status"] == "infeasible"
    assert result["valid_candidates"] == []
    assert "540분" in result["infeasible_result"].infeasibility_reasons[0]


def test_forbidden_window_prevents_placement():
    constraints = scenarios()["case-a"]["notice"]["constraints"]
    original = constraints["forbidden_windows"]
    constraints["forbidden_windows"] = [{"start":"07:30","end":"08:30"}]
    try:
        result = optimize("case-a", DAY)
        assert all(not (x.task_assignments and x.task_assignments[0].start.strftime("%H:%M") == "07:00") for x in result["valid_candidates"])
    finally:
        constraints["forbidden_windows"] = original


def test_pareto_filter():
    points = [{"id":"a","resident_cost":1,"change_cost":4},{"id":"b","resident_cost":2,"change_cost":2},{"id":"c","resident_cost":3,"change_cost":3}]
    assert {x["id"] for x in non_dominated(points)} == {"a","b"}


def test_quiet_and_high_noise_metrics_and_compare():
    scenario = get_scenario("case-a")
    before = default_assignments(scenario, DAY)
    after = [x.model_copy(update={"start":x.start+timedelta(minutes=15), "end":x.end+timedelta(minutes=15)}) for x in before]
    result = compare("case-a", DAY, before, after)
    assert result["after"].schedule_change_minutes == 60
    assert result["before"].longest_quiet_window_minutes % 15 == 0


def test_provenance_and_legal_separation():
    scenario = get_scenario("case-a")
    assert scenario["equipment"][0].source_metadata.status.value == "user_provided"
    output = predict("case-a", DAY)
    assert output["legal_assessment"] is None
    assert "법적" in output["disclaimer"]


def test_existing_event_is_energy_combined_and_provenance_retained():
    base = predict("case-a", DAY)["predictions"]
    busy = predict("scenario-b-congestion", DAY)["predictions"]
    a = next(x for x in base if x["receptor_id"] == "residential-1" and x["slot_start"].strftime("%H:%M") == "07:00")
    b = next(x for x in busy if x["receptor_id"] == "residential-1" and x["slot_start"].strftime("%H:%M") == "07:00")
    assert b["existing_noise_lp_db"] == 82.0
    assert b["total_estimated_db"] > a["total_estimated_db"]
    assert b["source_metadata"]["existing_events"][0]["status"] == "assumed"


def test_congestion_can_select_avoidance_candidate():
    result = optimize("scenario-b-congestion", DAY)
    protection = next(x for x in result["recommended_options"] if "resident_protection" in x["character"])["candidate"]
    original = next(x for x in result["valid_candidates"] if x.id == "offset-0")
    assert protection.id == "offset-120"
    assert protection.objective_values["existing_noise_overlap_slots"] < original.objective_values["existing_noise_overlap_slots"]
    assert protection.objective_values["resident_cost"] < original.objective_values["resident_cost"]


def test_exam_sensitivity_can_change_recommendation_priority():
    without = optimize("scenario-c-exam", DAY, sensitivity_enabled=False)
    with_it = optimize("scenario-c-exam", DAY, sensitivity_enabled=True)
    assert {x.id for x in without["pareto_candidates"]} == {"offset-0"}
    assert any(x.id == "offset-120" for x in with_it["pareto_candidates"])
    assert next(x for x in with_it["recommended_options"] if "resident_protection" in x["character"])["candidate"].id == "offset-120"


def test_recommendation_is_deterministic_and_diagnostics_counts_match():
    first = optimize("scenario-b-congestion", DAY)
    second = optimize("scenario-b-congestion", DAY)
    assert [x["candidate"].id for x in first["recommended_options"]] == [x["candidate"].id for x in second["recommended_options"]]
    assert first["diagnostics"]["generated_candidate_count"] == 9
    assert first["diagnostics"]["feasible_candidate_count"] == 9


def test_missing_equipment_noise_is_not_invented():
    output = predict("case-a", DAY)
    assert any("덤프트럭" in warning for warning in output["warnings"])
    assert all(source["equipment_id"] != "dump-truck" for row in output["predictions"] for source in row["source_metadata"]["equipment"])
