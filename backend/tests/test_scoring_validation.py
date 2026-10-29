from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.data import get_scenario
from app.services.optimizer import OBJECTIVE_FIELDS, optimize


PROFILE = "road_traffic_observed_profile"
A_DAY = date(2026, 10, 26)
B_DAY = date(2026, 9, 11)


def candidate(result, candidate_id):
    return next(x for x in result["valid_candidates"] if x.id == candidate_id)


def test_default_objective_and_eighth_iteration_result_are_preserved():
    result = optimize("official_reference_equipment", A_DAY, background_profile=PROFILE)
    original = candidate(result, "offset-0")
    assert result["diagnostics"]["objective_mode"] == "incremental_impact"
    assert original.metrics.incremental_impact_cost == 13.72
    assert original.objective_values["resident_cost"] == 13.72


@pytest.mark.parametrize("mode", ["physical_energy", "sensitive_exposure", "continuous_burden"])
def test_experimental_objectives_keep_separate_units(mode):
    result = optimize("final-demo-congestion", B_DAY, background_profile=PROFILE, objective_mode=mode)
    original = candidate(result, "offset-0")
    field, unit = OBJECTIVE_FIELDS[mode]
    assert original.objective_values["resident_cost"] == pytest.approx(getattr(original.metrics, field))
    assert result["diagnostics"]["objective_unit"] == unit
    assert result["diagnostics"]["default_objective_unchanged"] is True
    assert result["diagnostics"]["balanced_selection"] is None
    assert all("balanced" not in option["character"] for option in result["recommended_options"])
    assert result["diagnostics"]["policy_overlap_cost_included_in_pareto"] is False


def test_high_existing_event_masks_incremental_score_not_construction_energy():
    a = candidate(optimize("official_reference_equipment", A_DAY, background_profile=PROFILE), "offset-0")
    b = candidate(optimize("final-demo-congestion", B_DAY, background_profile=PROFILE), "offset-0")
    assert b.metrics.existing_noise_overlap_receptor_minutes > 0
    assert b.objective_values["existing_high_noise_overlap_minutes"] == 180
    assert b.objective_values["existing_noise_overlap_minutes"] == b.metrics.existing_noise_overlap_receptor_minutes


def test_near_residential_receptor_is_explicitly_assumed_and_additive():
    base = get_scenario("final-demo-congestion")
    scenario = get_scenario("final-demo-congestion-near-residential")
    assert {x.id for x in base["receptors"]} == {x.id for x in scenario["receptors"]}
    receptor = next(x for x in scenario["receptors"] if x.id == "assumed-residential-25m")
    assert receptor.distance_to_source_m == 25
    assert receptor.latitude is receptor.longitude is None
    assert receptor.spatial_status == "assumed"


def test_official_equipment_distribution_bounds_are_monotonic():
    ids = ["official-reference-equipment-min", "official_reference_equipment", "official-reference-equipment-max"]
    values = []
    for scenario_id in ids:
        result = optimize(scenario_id, A_DAY, background_profile=PROFILE)
        original = candidate(result, "offset-0")
        values.append((original.metrics.new_project_energy_exposure_65db_ref_minutes, original.metrics.incremental_impact_cost))
    assert values[0][0] < values[1][0] < values[2][0]
    assert values[0][1] < values[1][1] < values[2][1]


def test_new_project_time_metrics_are_distinct_from_whole_day_quiet_window():
    original = candidate(optimize("official_reference_equipment", A_DAY, background_profile=PROFILE), "offset-0")
    metrics = original.metrics
    assert metrics.longest_quiet_window_minutes == 0
    assert metrics.new_project_inactive_minutes == 120
    assert metrics.max_continuous_new_project_minutes == 540
    assert metrics.sensitive_new_project_receptor_minutes == 1620


def test_alternative_objectives_are_deterministic_and_api_compatible():
    for mode in ("physical_energy", "sensitive_exposure", "continuous_burden"):
        first = optimize("final-demo-congestion", B_DAY, background_profile=PROFILE, objective_mode=mode)
        second = optimize("final-demo-congestion", B_DAY, background_profile=PROFILE, objective_mode=mode)
        assert [x.id for x in first["pareto_candidates"]] == [x.id for x in second["pareto_candidates"]]
    response = TestClient(app).post("/api/schedules/optimize", json={"scenario_id": "final-demo-congestion", "analysis_date": "2026-09-11", "background_profile": PROFILE, "objective_mode": "physical_energy"})
    assert response.status_code == 200
    assert response.json()["diagnostics"]["objective_unit"] == "65 dB-reference energy-minutes"
