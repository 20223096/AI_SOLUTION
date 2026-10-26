from copy import deepcopy
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.domain import FieldValidationRequest, M1PredictRequest, M1ScheduleEvaluationRequest
from app.services.field_validation import evaluate_field_validation, load_field_observations
from app.services.m1_acoustics import evaluate_m1_schedule_candidates, predict_m1
from tests.test_m1_acoustic_model import END, START, payload, result, two_source_payload


def test_ten_plus_ten_requires_five_minute_overlap_and_blocks_sequential_mode():
    unknown = result(two_source_payload("overlap_unknown"))
    pair = unknown["simultaneity"]["pairwise_overlap"][0]
    assert pair == {"source_ids": ["excavator-a", "breaker-b"], "minimum_overlap_minutes": 5.0, "maximum_overlap_minutes": 10.0, "complete_sequential_feasible": False}
    assert unknown["maximum_concurrent_combined_level_db"] == pytest.approx(72.02, abs=0.02)
    response = TestClient(app).post("/api/noise/predict-m1", json=two_source_payload("sequential_possible"))
    assert response.status_code == 422
    assert "infeasible" in response.json()["detail"]


def test_five_plus_five_allows_complete_sequential_operation():
    data = two_source_payload("sequential_possible")
    for source in data["sources"]:
        source["actual_active_minutes"] = 5
    row = result(data)
    assert row["simultaneity"]["complete_sequential_feasible"] is True
    assert row["simultaneity"]["pairwise_overlap"][0]["minimum_overlap_minutes"] == 0
    assert row["maximum_concurrent_combined_level_db"] == pytest.approx(69.01, abs=0.02)


def test_fifteen_plus_fifteen_requires_complete_overlap():
    data = two_source_payload("overlap_unknown")
    for source in data["sources"]:
        source["actual_active_minutes"] = 15
    row = result(data)
    pair = row["simultaneity"]["pairwise_overlap"][0]
    assert pair["minimum_overlap_minutes"] == pair["maximum_overlap_minutes"] == 15
    assert row["simultaneity"]["minimum_feasible_concurrent_source_count"] == 2


def test_exact_intervals_report_actual_overlap_and_unknown_reports_range():
    exact = result(two_source_payload("exact", intervals=True, partial=True))
    unknown = result(two_source_payload("overlap_unknown"))
    assert exact["simultaneity"]["pairwise_overlap"][0]["actual_overlap_minutes"] == 5
    assert exact["continuous_new_project_exposure"] == {"minimum_minutes": 15.0, "maximum_minutes": 15.0, "interpretation": "explicit interval union"}
    assert "actual_overlap_minutes" not in unknown["simultaneity"]["pairwise_overlap"][0]


def test_three_source_capacity_reports_minimum_two_concurrent_sources():
    data = two_source_payload("overlap_unknown")
    third = deepcopy(data["sources"][0]); third["id"] = "roller-c"; third["equipment_category"] = "롤러"
    data["sources"].append(third)
    row = result(data)
    assert row["simultaneity"]["total_source_activity_minutes"] == 30
    assert row["simultaneity"]["minimum_feasible_concurrent_source_count"] == 2
    assert row["simultaneity"]["complete_sequential_feasible"] is False
    assert row["simultaneity"]["minimum_feasible_combined_level_db"] is None
    assert row["simultaneity"]["minimum_peak_lower_bound_db"] <= row["simultaneity"]["maximum_possible_combined_level_db"]


def test_slot_laeq_and_concurrent_combined_level_are_distinct_from_measured_lafmax():
    row = result(two_source_payload("complete_concurrent"))
    assert row["slot_laeq_dba"] == row["new_project_contribution_laeq_db"]
    assert row["maximum_concurrent_combined_level_db"] > row["slot_laeq_dba"]
    assert row["measured_lafmax_dba"] is None
    assert row["max_simultaneous_lp_db"] == row["maximum_concurrent_combined_level_db"]


def schedule_payload(position=True):
    point = {"x": 200000, "y": 550000, "z_m": 1, "crs": "EPSG:5186", "provenance": "assumed"} if position else None
    categories = {"cut": ("moving_work", "콘크리트 절단기", 113), "break": ("impulsive", "브레이커", 122), "excavate": ("moving_work", "굴삭기", 100), "compact": ("moving_work", "롤러", 102)}
    mappings = []
    for task_id, (source_type, category, lw) in categories.items():
        mappings.append({
            "task_id": task_id, "segment_id": "segment-yeonse-ro-2na-gil", "source_type": source_type,
            "equipment_category": category, "sound_power_level_db": lw, "lw_provenance": "assumed",
            "position": point, "active_ratio": 0.5, "activity_provenance": "assumed"
        })
    receptors = [
        {"id": rid, "position": {"x": 200000 + distance, "y": 550000, "z_m": 1.5, "crs": "EPSG:5186", "provenance": "assumed"}}
        for rid, distance in (("residential-1", 30), ("university-1", 50), ("school-1", 100))
    ]
    return {"scenario_id": "case-a", "analysis_date": "2026-10-26", "background_profile": "assumed_demo", "receptors": receptors, "task_mappings": mappings, "overlap_mode": "overlap_unknown"}


def test_existing_optimizer_feasible_candidates_can_be_evaluated_by_m1():
    response = evaluate_m1_schedule_candidates(M1ScheduleEvaluationRequest.model_validate(schedule_payload()))
    assert response["evaluation_status"] == "simulated"
    assert response["generated_candidate_count"] == response["feasible_candidate_count"] == 9
    assert response["pareto_candidates"] and response["recommended_candidate"]
    assert response["base_optimizer_unchanged"] is True
    energies = {x["objective_axes"]["new_project_energy_exposure"] for x in response["candidates"]}
    assert len(energies) == 1  # time shift alone does not alter construction-only energy
    assert response["recommendation_reasons"][1]["code"] == "lexicographic_reference_without_cross_unit_sum"


def test_official_missing_geometry_defers_candidate_evaluation():
    response = evaluate_m1_schedule_candidates(M1ScheduleEvaluationRequest.model_validate(schedule_payload(position=False)))
    assert response["evaluation_status"] == "deferred"
    assert response["candidates"] == []
    assert {x["field"] for x in response["missing_required_inputs"]} == {"position"}


def test_assumed_candidate_inputs_remain_marked_simulated():
    response = TestClient(app).post("/api/noise/evaluate-m1-candidates", json=schedule_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["evaluation_status"] == "simulated"
    assert body["recommended_candidate"]["input_provenance"] == {"positions": ["assumed"], "activities": ["assumed"]}


def test_field_validation_without_observations_is_not_evaluable():
    result_data = evaluate_field_validation(FieldValidationRequest())
    assert result_data["validation_status"] == "not_evaluable"
    assert result_data["mae"] is result_data["rmse"] is result_data["bias"] is None


def test_field_loader_and_alignment_require_same_time_position_and_metric(tmp_path):
    path = tmp_path / "observations.json"
    path.write_text('''[{"id":"obs-1","receptor_id":"r1","physical_location_id":"site-r1-v1","receptor_position":{"x":200010,"y":550000,"z_m":1,"crs":"EPSG:5186","provenance":"field_verified"},"start":"2026-10-26T07:00:00+09:00","end":"2026-10-26T07:15:00+09:00","laeq_dba":65,"measurement_duration_minutes":15,"equipment_active":{"excavator-a":true},"instrument":"Class 1 meter","calibration_before":"verified","calibration_after":"verified","weather":{"wind_mps":1.2},"source":"field campaign"}]''', encoding="utf-8")
    observations = load_field_observations(path)
    request = FieldValidationRequest.model_validate({"observations": [x.model_dump(mode="json") for x in observations], "predictions": [{
        "receptor_id": "r1", "physical_location_id": "site-r1-v1", "receptor_position": {"x": 200010, "y": 550000, "z_m": 1, "crs": "EPSG:5186", "provenance": "assumed"},
        "start": START.isoformat(), "end": END.isoformat(), "predicted_laeq_dba": 66, "acoustic_scope": "total_environment", "equipment_ids": ["excavator-a"], "metric": "LAeq_dBA"
    }]})
    evaluated = evaluate_field_validation(request)
    assert evaluated["validation_status"] == "evaluated"
    assert evaluated["mae"] == evaluated["rmse"] == evaluated["bias"] == 1
    assert evaluated["equipment_errors"][0]["equipment_id"] == "excavator-a"


def test_m0_default_api_result_remains_unchanged():
    response = TestClient(app).post("/api/noise/predict", json={"scenario_id": "case-a", "analysis_date": "2026-10-26"})
    assert response.status_code == 200
    assert response.json()["model_version"] == "poc-0.1.0"
    assert response.json()["scoring_version"] == "legacy_v1"
