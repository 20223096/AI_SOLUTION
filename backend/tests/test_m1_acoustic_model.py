from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.domain import M1Point, M1PredictRequest, M1UncertaintyRequest
from app.services.m1_acoustics import analyze_uncertainty, compare_m0_m1, distance_3d_m, predict_m1, validation_metrics
from app.services.prediction import predict

KST = timezone(timedelta(hours=9))
START = datetime(2026, 10, 26, 7, 0, tzinfo=KST)
END = START + timedelta(minutes=15)


def payload(active=15, count=1, distance=10, lw=100, overlap_mode="complete_concurrent"):
    return {
        "slot_start": START.isoformat(), "slot_end": END.isoformat(),
        "background_laeq_db": 50, "background_provenance": "assumed",
        "overlap_mode": overlap_mode,
        "sources": [{
            "id": "excavator-a", "segment_id": "segment-yeonse-ro-2na-gil",
            "source_type": "moving_work", "equipment_category": "굴삭기", "count": count,
            "sound_power_level_db": lw, "lw_provenance": "assumed",
            "position": {"x": 200000, "y": 550000, "z_m": 1, "crs": "EPSG:5186", "provenance": "assumed"},
            "deployment_start": START.isoformat(), "deployment_end": END.isoformat(),
            "actual_active_minutes": active, "activity_provenance": "assumed"
        }],
        "receptors": [{"id": "r1", "position": {"x": 200000 + distance, "y": 550000, "z_m": 1, "crs": "EPSG:5186", "provenance": "assumed"}}]
    }


def result(data):
    return predict_m1(M1PredictRequest.model_validate(data))["results"][0]


def test_activity_zero_half_full_energy_average():
    zero, half, full = result(payload(0)), result(payload(7.5)), result(payload(15))
    assert zero["new_project_contribution_laeq_db"] is None
    assert half["new_project_contribution_laeq_db"] == pytest.approx(full["new_project_contribution_laeq_db"] - 3.01, abs=0.02)
    assert half["new_project_energy_exposure_65db_ref_minutes"] == pytest.approx(full["new_project_energy_exposure_65db_ref_minutes"] / 2, rel=1e-5)


def test_equipment_count_is_summed_as_energy():
    one, two = result(payload(count=1)), result(payload(count=2))
    assert two["new_project_contribution_laeq_db"] == pytest.approx(one["new_project_contribution_laeq_db"] + 3.01, abs=0.02)


def test_double_distance_reduces_point_source_by_six_db():
    near, far = result(payload(distance=10)), result(payload(distance=20))
    assert far["new_project_contribution_laeq_db"] == pytest.approx(near["new_project_contribution_laeq_db"] - 6.02, abs=0.02)


def test_source_and_receptor_height_use_three_dimensional_distance():
    source = M1Point(x=0, y=0, z_m=0, crs="EPSG:5186", provenance="assumed")
    receptor = M1Point(x=3, y=4, z_m=12, crs="EPSG:5186", provenance="assumed")
    assert distance_3d_m(source, receptor) == 13


def test_geographic_crs_is_converted_to_metre_distance_and_mixed_crs_fails():
    a = M1Point(x=127, y=37, crs="EPSG:4326", provenance="assumed")
    b = M1Point(x=127, y=37.001, crs="EPSG:4326", provenance="assumed")
    assert 110 < distance_3d_m(a, b) < 112
    with pytest.raises(ValueError, match="CRS must match"):
        distance_3d_m(a, M1Point(x=200000, y=550000, crs="EPSG:5186", provenance="assumed"))


def test_invalid_crs_is_rejected_by_api_schema():
    data = payload()
    data["sources"][0]["position"]["crs"] = "EPSG:3857"
    response = TestClient(app).post("/api/noise/predict-m1", json=data)
    assert response.status_code == 422


def two_source_payload(mode, intervals=False, partial=False):
    data = payload(active=10, overlap_mode=mode)
    second = deepcopy(data["sources"][0])
    second["id"] = "breaker-b"
    second["equipment_category"] = "브레이커"
    second["source_type"] = "impulsive"
    second["segment_id"] = "segment-chungjeong-ro"
    if intervals:
        data["sources"][0]["active_intervals"] = [{"start": START.isoformat(), "end": (START + timedelta(minutes=10)).isoformat()}]
        second["active_intervals"] = [{"start": (START + timedelta(minutes=5 if partial else 10)).isoformat(), "end": END.isoformat()}]
        data["sources"][0]["actual_active_minutes"] = None
        second["actual_active_minutes"] = None
        data["sources"][0]["activity_provenance"] = "field_verified"
        second["activity_provenance"] = "field_verified"
    data["sources"].append(second)
    return data


def test_complete_concurrent_and_unknown_overlap_have_same_slot_energy_but_feasible_peak_bound():
    concurrent = result(two_source_payload("complete_concurrent"))
    unknown = result(two_source_payload("overlap_unknown"))
    assert concurrent["new_project_contribution_laeq_db"] == unknown["new_project_contribution_laeq_db"]
    assert unknown["simultaneity"]["complete_sequential_feasible"] is False
    assert unknown["simultaneity"]["pairwise_overlap"][0]["minimum_overlap_minutes"] == 5
    assert unknown["simultaneity"]["minimum_feasible_combined_level_db"] == concurrent["maximum_concurrent_combined_level_db"]


def test_partial_overlap_exact_intervals_detects_concurrent_peak():
    partial = result(two_source_payload("exact", intervals=True, partial=True))
    sequential = result(two_source_payload("exact", intervals=True, partial=False))
    assert partial["max_simultaneous_lp_db"] == pytest.approx(sequential["max_simultaneous_lp_db"] + 3.01, abs=0.02)


def test_unknown_overlap_returns_bounds_not_false_precision():
    row = result(two_source_payload("overlap_unknown"))
    assert row["max_simultaneous_lp_db"] is None
    assert row["simultaneity"]["confidence_interval"] is None
    assert row["simultaneity"]["maximum_possible_combined_level_db"] == row["simultaneity"]["minimum_feasible_combined_level_db"]


def test_rammer_cannot_match_roller_model_and_missing_reference_defers():
    data = payload()
    source = data["sources"][0]
    source.update({"equipment_category": "램머", "equipment_model": "SV512D", "sound_power_level_db": None, "lw_provenance": "unknown"})
    response = predict_m1(M1PredictRequest.model_validate(data))
    assert response["calculation_status"] == "deferred"
    assert response["missing_required_inputs"][0]["status"] == "missing_noise_reference"


def test_exact_official_model_reference_preserves_source_but_not_field_condition():
    data = payload()
    source = data["sources"][0]
    source.update({"equipment_category": "콘크리트 절단기", "equipment_model": "K950", "sound_power_level_db": None, "lw_provenance": "unknown"})
    row = result(data)["sources"][0]
    assert row["lw_source"]["status"] == "exact_model_reference"
    assert row["lw_source"]["provenance"] == "official_reference"
    assert row["lw_source"]["measurement_condition_verified"] is False


def test_low_median_high_reference_is_deterministic_and_ten_db_is_tenfold_energy():
    low_data = payload(lw=None)
    low_data["sources"][0].update({"sound_power_level_db": None, "lw_provenance": "unknown", "reference_scenario": "low"})
    high_data = deepcopy(low_data); high_data["sources"][0]["reference_scenario"] = "high"
    low, high = result(low_data), result(high_data)
    assert high["new_project_contribution_laeq_db"] > low["new_project_contribution_laeq_db"]
    base, plus_ten = result(payload(lw=100)), result(payload(lw=110))
    assert plus_ten["new_project_energy_exposure_65db_ref_minutes"] == pytest.approx(base["new_project_energy_exposure_65db_ref_minutes"] * 10, rel=1e-5)


def test_two_segments_stay_attached_to_independent_sources():
    row = result(two_source_payload("complete_concurrent"))
    assert {x["segment_id"] for x in row["sources"]} == {"segment-yeonse-ro-2na-gil", "segment-chungjeong-ro"}


def test_missing_position_or_activity_defers_instead_of_assuming_full_operation():
    data = payload()
    data["sources"][0]["position"] = None
    data["sources"][0]["actual_active_minutes"] = None
    data["sources"][0]["activity_provenance"] = "unknown"
    response = predict_m1(M1PredictRequest.model_validate(data))
    assert response["calculation_status"] == "deferred"
    assert {x["field"] for x in response["missing_required_inputs"]} >= {"position", "actual_active_minutes"}


def test_corrections_are_not_silently_treated_as_zero_effect():
    response = predict_m1(M1PredictRequest.model_validate(payload()))
    assert all(x == {"status": "not_modelled", "value_db": None} for x in response["corrections"].values())


def test_m0_m1_comparison_and_existing_m0_are_deterministic():
    request = M1PredictRequest.model_validate(payload(active=7.5))
    first, second = compare_m0_m1(request), compare_m0_m1(request)
    assert first == second
    comparison = first["comparisons"][0]
    assert comparison["m0_new_project_laeq_db"] == pytest.approx(comparison["m1_new_project_laeq_db"] + 3.01, abs=0.02)
    old_first = predict("case-a", START.date())
    old_second = predict("case-a", START.date())
    assert old_first == old_second and old_first["model_version"] == "poc-0.1.0"


def test_validation_is_not_evaluable_without_measurements_and_computes_aligned_metrics():
    assert validation_metrics([60], [])["validation_status"] == "not_evaluable"
    metrics = validation_metrics([61, 59], [60, 60])
    assert metrics == {"validation_status": "evaluated", "sample_count": 2, "mae": 1, "rmse": 1, "bias": 0}


def test_uncertainty_analysis_returns_declared_case_range_without_confidence_interval():
    request = M1UncertaintyRequest.model_validate({"cases": [
        {"id": "activity-50", "varied_variable": "activity_ratio", "request": payload(active=7.5)},
        {"id": "activity-100", "varied_variable": "activity_ratio", "request": payload(active=15)},
    ]})
    analysis = analyze_uncertainty(request)
    metric = analysis["ranges"][0]["metrics"]["new_project_energy_exposure_65db_ref_minutes"]
    assert metric["maximum"] == pytest.approx(metric["minimum"] * 2, rel=1e-5)
    assert analysis["confidence_interval"] is None
    assert analysis["probability_distribution"] is None

