import math

import pytest

from app.models.domain import FieldValidationRequest, M1ScheduleEvaluationRequest
from app.services.accuracy_readiness import input_sensitivity_analysis, physical_cross_checks
from app.services.field_validation import evaluate_field_validation
from app.services.m1_acoustics import evaluate_m1_schedule_candidates
from app.services.public_data import official_construction_design
from tests.test_m1_temporal_schedule import START, END, schedule_payload


def test_point_source_matches_independent_hand_calculation():
    checks = physical_cross_checks()
    expected = 100 - 10 * math.log10(4 * math.pi * 10**2)
    assert checks["point_source_10m"]["hand_db"] == pytest.approx(expected)
    assert checks["point_source_10m"]["model_db"] == pytest.approx(expected, abs=0.01)
    assert abs(checks["point_source_10m"]["difference_db"]) < 0.01


def test_activity_distance_count_and_3d_hand_relations():
    checks = physical_cross_checks()
    assert checks["half_activity"]["model_db"] == pytest.approx(checks["half_activity"]["hand_db"], abs=0.01)
    assert checks["double_distance_change_db"] == pytest.approx(-6.02, abs=0.02)
    assert checks["double_count_change_db"] == pytest.approx(3.01, abs=0.02)
    assert checks["three_dimensional_distance_example_m"] == 13


def test_combined_level_is_never_labelled_as_measured_lafmax():
    assert physical_cross_checks()["maximum_concurrent_is_measured_lafmax"] is False


def test_deterministic_sensitivity_has_no_probability_or_confidence_interval():
    analysis = input_sensitivity_analysis()
    assert analysis["analysis_type"] == "one_factor_deterministic_sensitivity"
    assert analysis["probability_distribution"] is None
    assert analysis["confidence_interval"] is None


def test_sensitivity_ranges_capture_expected_physical_relations():
    groups = input_sensitivity_analysis()["groups"]
    assert groups["activity_ratio"]["energy_ratio"] == pytest.approx(4, rel=1e-5)
    assert groups["equipment_count"]["energy_ratio"] == pytest.approx(4, rel=1e-5)
    assert groups["receptor_distance"]["energy_ratio"] == pytest.approx(16, rel=1e-4)
    assert groups["background_level"]["slot_laeq_span_db"] == 0
    assert groups["simultaneity"]["slot_laeq_span_db"] == 0
    assert groups["simultaneity"]["maximum_concurrent_span_db"] == pytest.approx(3.01, abs=0.02)


def test_official_segments_remain_geometry_null_and_independent():
    segments = official_construction_design()["segments"]
    assert [(x["nominal_address"], x["route_length_m"], x["geometry"]) for x in segments] == [
        ("연세로2나길 20 일대", 328, None),
        ("충정로 35-17 일대", 155, None),
    ]
    assert all(x["representative_point"] is None for x in segments)


def test_physical_location_identity_is_distinct_from_coordinate_tolerance():
    common_point = {"x": 200010, "y": 550000, "z_m": 1, "crs": "EPSG:5186", "provenance": "field_verified"}
    request = FieldValidationRequest.model_validate({
        "observations": [{
            "id": "obs", "receptor_id": "r1", "physical_location_id": "survey-mark-a", "receptor_position": common_point,
            "start": START, "end": END, "laeq_dba": 60, "measurement_duration_minutes": 15,
            "equipment_active": {}, "instrument": "meter", "calibration_before": "ok", "calibration_after": "ok",
            "weather": {"wind_mps": 1}, "source": "field"
        }],
        "predictions": [{
            "receptor_id": "r1", "physical_location_id": "survey-mark-b", "receptor_position": common_point,
            "start": START, "end": END, "predicted_laeq_dba": 60, "equipment_ids": []
        }]
    })
    result = evaluate_field_validation(request)
    assert result["validation_status"] == "not_evaluable"
    assert result["alignment_failures"][0]["reason"] == "physical_location_id_mismatch"


def test_legacy_field_validation_request_without_location_id_remains_accepted():
    common_point = {"x": 200010, "y": 550000, "z_m": 1, "crs": "EPSG:5186", "provenance": "field_verified"}
    request = FieldValidationRequest.model_validate({
        "observations": [{
            "id": "legacy-obs", "receptor_id": "r1", "receptor_position": common_point,
            "start": START, "end": END, "laeq_dba": 60, "measurement_duration_minutes": 15,
            "equipment_active": {}, "instrument": "meter", "calibration_before": "ok", "calibration_after": "ok",
            "weather": {"wind_mps": 1}, "source": "legacy field payload"
        }],
        "predictions": [{
            "receptor_id": "r1", "receptor_position": common_point, "start": START, "end": END,
            "predicted_laeq_dba": 60, "equipment_ids": []
        }]
    })
    result = evaluate_field_validation(request)
    assert result["validation_status"] == "evaluated"
    assert result["coordinate_tolerance_note"].startswith("0.01m is a numeric")


def test_time_shift_only_keeps_energy_and_sensitive_time_can_change_recommendation():
    baseline = evaluate_m1_schedule_candidates(M1ScheduleEvaluationRequest.model_validate(schedule_payload()))
    assert len({x["objective_axes"]["new_project_energy_exposure"] for x in baseline["candidates"]}) == 1
    assert baseline["recommended_candidate"]["id"] == "offset-0"
    sensitive_payload = schedule_payload(); sensitive_payload["scenario_id"] = "scenario-c-exam"
    sensitive = evaluate_m1_schedule_candidates(M1ScheduleEvaluationRequest.model_validate(sensitive_payload))
    assert sensitive["recommended_candidate"]["id"] == "offset-120"
    assert len(sensitive["pareto_candidates"]) == 5
    assert sensitive["recommended_candidate"]["objective_axes"]["sensitive_exposure_receptor_minutes"] == 600


def test_official_candidate_evaluation_stays_deferred_without_geometry():
    data = schedule_payload(position=False)
    result = evaluate_m1_schedule_candidates(M1ScheduleEvaluationRequest.model_validate(data))
    assert result["evaluation_status"] == "deferred"
    assert result["validation_status"] == "not_evaluable"
