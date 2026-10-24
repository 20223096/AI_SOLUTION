from copy import deepcopy
from datetime import datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.domain import DesignBasedSimulationRequest
from app.services.design_simulation import _base_assignments, _validate, design_simulation_catalog, run_design_rescheduling

KST = timezone(timedelta(hours=9))


def request(segment="segment-yeonse-ro-2na-gil", receptor="yeonse-sim-r1"):
    return DesignBasedSimulationRequest(
        segment_id=segment, receptor_id=receptor, receptor_segment_id=segment, distance_m=30,
    )


def test_two_official_segments_stay_spatially_separate_and_geometry_null():
    segments = design_simulation_catalog()["official_design_data"]["segments"]
    assert [(x["id"], x["route_length_m"], x["geometry"], x["simulation_geometry"]) for x in segments] == [
        ("segment-yeonse-ro-2na-gil", 328, None, None),
        ("segment-chungjeong-ro", 155, None, None),
    ]
    assert segments[0]["receptor_set_id"] != segments[1]["receptor_set_id"]


def test_receptor_from_other_segment_is_rejected():
    with pytest.raises(ValueError, match="receptor must belong"):
        DesignBasedSimulationRequest(
            segment_id="segment-yeonse-ro-2na-gil", receptor_id="wrong-r1",
            receptor_segment_id="segment-chungjeong-ro", distance_m=30,
        )


def test_official_quantities_are_preserved_and_not_converted_to_hours():
    catalog = design_simulation_catalog()
    packages = catalog["official_design_data"]["work_packages"]
    cutting = next(x for x in packages if x["category"] == "포장절단")
    pump = next(x for x in packages if x["category"] == "물푸기")
    assert [(x["quantity"], x["unit"]) for x in cutting["items"]] == [(1095, "m"), (198, "m")]
    assert (pump["items"][0]["quantity"], pump["items"][0]["unit"]) == (328, "hr")
    assert "not allocated" in run_design_rescheduling(request())["quantity_allocation"]


def test_excavator_bucket_capacity_is_not_inferred_from_model_names():
    match = design_simulation_catalog()["excavator_capacity_match"]
    assert match["match_status"] == "not_classifiable"
    assert match["requested_bucket_capacities_m3"] == [0.2, 0.4, 0.7]
    assert match["records_must_not_be_pooled_as_capacity_matches"] is True


def test_precedence_violation_candidate_is_blocked():
    result = run_design_rescheduling(request())
    invalid = next(x for x in result["candidates"] if x["id"] == "D-invalid-order-swap")
    assert invalid["feasible"] is False
    assert "precedence violation: cut->break" in invalid["infeasibility_reasons"]


def test_single_workfront_resource_conflict_is_blocked():
    start = datetime(2026, 10, 26, 7, 0, tzinfo=KST)
    assignments = _base_assignments(start)
    assignments[1]["start"] = assignments[0]["start"]
    assignments[1]["end"] = assignments[1]["start"] + timedelta(minutes=90)
    failures = _validate(assignments, start, datetime(2026, 10, 26, 18, 0, tzinfo=KST))
    assert any("single-workfront resource conflict" in x for x in failures)


def test_concurrent_and_sequential_keep_energy_but_change_combined_level():
    result = run_design_rescheduling(request())
    original = next(x for x in result["candidates"] if x["id"] == "A-original")
    sequential = next(x for x in result["candidates"] if x["id"] == "D-sequential-break-equipment")
    assert sequential["metrics"]["new_project_energy_exposure_partial"] == pytest.approx(original["metrics"]["new_project_energy_exposure_partial"])
    assert sequential["metrics"]["maximum_concurrent_combined_level_db_partial"] < original["metrics"]["maximum_concurrent_combined_level_db_partial"]


def test_candidates_respect_assumed_end_of_workday():
    result = run_design_rescheduling(request())
    cutoff = datetime(2026, 10, 26, 18, 0, tzinfo=KST)
    assert all(x["metrics"]["project_end"] <= cutoff for x in result["candidates"] if x["feasible"])


def test_m1_slot_results_include_contribution_total_and_partial_warning():
    candidate = run_design_rescheduling(request())["candidates"][0]
    assert candidate["slot_results"]
    calculated = [row for row in candidate["slot_results"] if row.get("calculation_status") != "incomplete_missing_noise_reference"]
    incomplete = [row for row in candidate["slot_results"] if row.get("calculation_status") == "incomplete_missing_noise_reference"]
    assert calculated and incomplete
    assert all(row["slot_laeq_dba"] is not None and row["total_laeq_db"] is not None for row in calculated)
    assert all(row["slot_laeq_dba"] is None and row["total_laeq_db"] is None for row in incomplete)
    assert candidate["acoustic_completeness"] == "partial"
    assert "램머 80kg" in candidate["missing_noise_equipment"]


def test_pareto_and_recommendation_are_deterministic_without_cross_unit_sum():
    first = run_design_rescheduling(request())
    second = run_design_rescheduling(request())
    assert [x["id"] for x in first["pareto_candidates"]] == [x["id"] for x in second["pareto_candidates"]]
    assert first["recommended_candidate"]["id"] == second["recommended_candidate"]["id"] == "C-delay-high-noise-60"
    assert first["recommendation_reasons"][1]["code"] == "no_cross_unit_sum"


def test_process_adjustment_changes_sensitive_exposure_not_total_known_energy():
    result = run_design_rescheduling(request())
    original = next(x for x in result["candidates"] if x["id"] == "A-original")
    delayed = next(x for x in result["candidates"] if x["id"] == "C-delay-high-noise-60")
    assert delayed["metrics"]["sensitive_exposure_minutes_partial"] == 120
    assert original["metrics"]["sensitive_exposure_minutes_partial"] == 180
    assert delayed["metrics"]["new_project_energy_exposure_partial"] == original["metrics"]["new_project_energy_exposure_partial"]
    assert delayed["metrics"]["maximum_continuous_known_noise_minutes"] < original["metrics"]["maximum_continuous_known_noise_minutes"]


def test_api_is_additive_and_preserves_provenance_and_validation_status():
    client = TestClient(app)
    assert client.get("/api/noise/design-simulation/catalog").status_code == 200
    response = client.post("/api/noise/design-simulation/reschedule", json=request().model_dump(mode="json"))
    assert response.status_code == 200
    body = response.json()
    assert body["result_type"] == "design_based_simulation"
    assert body["official_field_prediction_status"] == "deferred"
    assert body["validation_status"] == "not_evaluable"
    assert "simulation_assumption" in body["data_quality"]
    assert body["simulation_geometry"]["official_geometry_unchanged"] is None
