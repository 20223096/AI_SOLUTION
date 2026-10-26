from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.domain import ImpactRequest
from app.services.acoustics import energy_sum
from app.services.impact import calculate_impact
from app.services.optimizer import optimize
from app.services.prediction import predict

DAY = date(2026, 10, 26)
client = TestClient(app)


def first_row(result, receptor="residential-1", hour=7):
    return next(x for x in result["predictions"] if x["receptor_id"] == receptor and x["slot_start"].hour == hour)


def test_no_new_project_has_zero_incremental_impact():
    result = predict("case-a", DAY, assignments=[])
    assert all(row["incremental_impact"] == 0 and row["delta_total_db"] == 0 for row in result["predictions"])
    assert all(row["new_project_contribution_db"] is None for row in result["predictions"])


def test_new_project_uses_energy_sum_and_not_db_subtraction():
    row = first_row(predict("case-a", DAY))
    expected = energy_sum([row["existing_environment_db"], row["new_project_contribution_db"]])
    assert row["with_new_project_db"] == pytest.approx(expected, abs=.02)
    assert row["delta_total_db"] == pytest.approx(row["with_new_project_db"] - row["existing_environment_db"], abs=.02)
    assert row["new_project_contribution_db"] != pytest.approx(row["delta_total_db"], abs=.1)


def test_existing_event_is_part_of_baseline_environment():
    row = first_row(predict("scenario-b-congestion", DAY))
    assert row["existing_event_ids"]
    assert row["existing_environment_db"] > row["background_only_db"]
    assert row["baseline_impact"] > 0


def test_incremental_impact_uses_same_slot_and_sensitivity():
    row = first_row(predict("scenario-c-exam", DAY), receptor="university-1", hour=8)
    total = calculate_impact(ImpactRequest(total_noise_db=row["with_new_project_db"], duration_minutes=15 if row["with_new_project_db"] >= 65 else 0, continuous_minutes=15 if row["with_new_project_db"] >= 65 else 0, sensitivity_weight=row["sensitivity"]["weight"]))["score"]
    baseline = calculate_impact(ImpactRequest(total_noise_db=row["existing_environment_db"], duration_minutes=15 if row["existing_environment_db"] >= 65 else 0, continuous_minutes=15 if row["existing_environment_db"] >= 65 else 0, sensitivity_weight=row["sensitivity"]["weight"]))["score"]
    assert row["incremental_impact"] == pytest.approx(max(0, total - baseline), abs=.01)


def test_incremental_impact_changes_with_background_level():
    increments = []
    for background in [50, 60, 70, 75]:
        total = energy_sum([background, 80])
        total_score = calculate_impact(ImpactRequest(total_noise_db=total, duration_minutes=15, continuous_minutes=15, sensitivity_weight=1))["score"]
        baseline_score = calculate_impact(ImpactRequest(total_noise_db=background, duration_minutes=15 if background >= 65 else 0, continuous_minutes=15 if background >= 65 else 0, sensitivity_weight=1))["score"]
        increments.append(round(total_score - baseline_score, 2))
    assert increments == sorted(increments, reverse=True)


def test_impact_component_saturation_is_detected():
    result = calculate_impact(ImpactRequest(total_noise_db=90, baseline_noise_db=85, duration_minutes=15, continuous_minutes=15, sensitivity_weight=1))
    assert result["incremental_score"] == 0
    assert result["saturation"]["level_component_at_ceiling"] is True
    assert result["saturation"]["incremental_zero_despite_increase"] is True


def test_absolute_and_incremental_modes_preserve_values_but_select_requested_cost():
    absolute = optimize("case-a", DAY, background_profile="road_traffic_observed_profile", objective_mode="absolute_impact")
    incremental = optimize("case-a", DAY, background_profile="road_traffic_observed_profile", objective_mode="incremental_impact")
    a = absolute["valid_candidates"][0].objective_values
    i = incremental["valid_candidates"][0].objective_values
    assert a["absolute_impact_cost"] == i["absolute_impact_cost"]
    assert a["incremental_impact_cost"] == i["incremental_impact_cost"]
    assert a["resident_cost"] == a["absolute_impact_cost"]
    assert i["resident_cost"] == i["incremental_impact_cost"]


def test_objective_modes_have_correct_pareto_for_constant_baseline():
    absolute = optimize("case-a", DAY, background_profile="road_traffic_observed_profile", objective_mode="absolute_impact")
    incremental = optimize("case-a", DAY, background_profile="road_traffic_observed_profile", objective_mode="incremental_impact")
    assert [x.id for x in absolute["pareto_candidates"]] == [x.id for x in incremental["pareto_candidates"]]


def test_overlap_policy_cost_is_reported_but_not_double_counted():
    result = optimize("scenario-b-congestion", DAY)
    candidate = result["valid_candidates"][0]
    assert candidate.objective_values["policy_overlap_cost"] > 0
    assert candidate.objective_values["resident_cost"] == candidate.objective_values["incremental_impact_cost"]
    assert result["diagnostics"]["policy_overlap_cost_included_in_pareto"] is False


def test_case_d_remains_infeasible_for_both_objectives():
    for mode in ["absolute_impact", "incremental_impact"]:
        result = optimize("scenario-d-restricted", DAY, objective_mode=mode)
        assert result["optimization_status"] == "infeasible" and not result["valid_candidates"]


def test_api_is_backward_compatible_and_exposes_incremental_fields():
    response = client.post("/api/noise/predict", json={"scenario_id":"case-a","analysis_date":"2026-10-26"})
    assert response.status_code == 200
    row = response.json()["predictions"][0]
    assert "total_estimated_db" in row and "with_new_project_db" in row and "incremental_impact" in row
    impact = client.post("/api/impact/calculate", json={"total_noise_db":90,"baseline_noise_db":85,"duration_minutes":15,"continuous_minutes":15,"sensitivity_weight":1})
    assert impact.status_code == 200 and impact.json()["incremental_score"] == 0


def test_incremental_optimization_is_deterministic():
    first = optimize("scenario-c-exam", DAY, background_profile="road_traffic_observed_profile")
    second = optimize("scenario-c-exam", DAY, background_profile="road_traffic_observed_profile")
    assert [x.model_dump() for x in first["pareto_candidates"]] == [x.model_dump() for x in second["pareto_candidates"]]
