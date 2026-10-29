from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from tests.test_prd_api import validation_payload


client = TestClient(app)
ROOT = Path(__file__).resolve().parents[2]


def integrated_payload() -> dict:
    source = {"status": "user_provided", "source": "confirmed form", "note": None, "unit": None}
    payload = validation_payload()
    planning = payload["planning"]
    planning.update({
        "notice_id": "integrated-demo",
        "construction_period": {"start": "2026-09-11", "end": "2026-09-11", "raw_text": "confirmed"},
        "total_work_window": {"start": "08:00", "end": "17:00"},
        "road_excavation": False,
        "road_occupancy_permit_window": None,
        "equipment_constraints": [
            {"equipment_id": equipment_id, "category": category, "specification": None, "model_name": None,
             "max_daily_count": 1, "required_usage_minutes": minutes,
             "permitted_time_windows": [{"start": "08:00", "end": "17:00"}], "source_metadata": source}
            for equipment_id, category, minutes in (
                ("cutter", "절단기", 60), ("breaker", "브레이커", 120),
                ("excavator", "굴착기", 180), ("roller", "롤러", 60),
            )
        ],
        "fixed_tasks": [],
        "same_day_restoration_required": False,
        "project_completion_date": "2026-09-11",
        "field_provenance": {
            name: source for name in ("construction_period", "total_work_window", "road_excavation", "equipment_constraints")
        },
    })
    return {
        "analysis_date": "2026-09-11",
        "planning": planning,
        "predecessors": {"break": ["cut"], "excavate": ["break"], "compact": ["excavate"]},
        "equipment_by_task": {"cut": "cutter", "break": "breaker", "excavate": "excavator", "compact": "roller"},
        "equipment_count_by_task": {"cut": 1, "break": 1, "excavate": 1, "compact": 1},
        "restoration_task_ids": [],
    }


def test_notice_extraction_maps_only_present_values_and_reports_missing_fields():
    extracted = client.post("/api/notices/extract", json={"text": "2026년 신촌 연세로 공사 07:00~18:00, 굴착기"})
    assert extracted.status_code == 200
    body = extracted.json()
    response = client.post("/api/prd/planning/from-notice", json={
        "notice": body["notice"], "extractor_mode": body["mode"], "is_actual_ai": body["is_actual_ai"],
        "field_evidence": body.get("field_evidence", {}),
    })
    assert response.status_code == 200
    draft = response.json()
    assert draft["status"] == "needs_confirmation"
    assert draft["planning_draft"]["road_excavation"] is None
    assert draft["planning_draft"]["road_occupancy_permit_window"] is None
    assert draft["planning_draft"]["equipment_constraints"][0]["max_daily_count"] is None
    assert "road_excavation" in draft["missing_fields"]
    assert draft["is_actual_ai"] is False


def test_notice_draft_with_required_information_missing_keeps_nulls():
    response = client.post("/api/prd/planning/from-notice", json={
        "extractor_mode": "manual", "is_actual_ai": False, "notice": {
            "id": "minimal", "name": None, "location": None,
            "construction_period": {"start": None, "end": None, "raw_text": None},
            "original_work_window": None, "tasks": [], "constraints": {},
            "source_provenance": {"document": {"status": "user_provided", "source": "request"}},
        },
    })
    assert response.status_code == 200
    body = response.json()
    assert body["planning_draft"]["project_name"] is None
    assert body["planning_draft"]["location"] is None
    assert {"project_name", "location", "construction_period", "total_work_window", "equipment_constraints"} <= set(body["missing_fields"])


def test_constraint_filtered_normal_input_preserves_9_11_result_and_marks_claim_scope():
    response = client.post("/api/prd/recommendations/constraint-filtered", json=integrated_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["recommendable_candidate_ids"] == ["offset-120"]
    assert body["original_schedule"]["prd_feasible"] is True
    assert body["optimization_claim"] == "constraint_filtered_candidate_set_not_global_optimum"
    assert body["candidate_generation_mode"] == "existing_optimizer_15_minute_offsets_0_to_120"
    legacy = client.get("/api/prd/recommendation-diagnostics", params={"analysis_date": "2026-09-11"}).json()
    assert legacy["recommended_candidate_ids"] == ["offset-120"]


def test_constraint_filter_can_leave_exactly_one_recommendable_candidate():
    payload = integrated_payload()
    payload["planning"]["total_work_window"] = {"start": "10:00", "end": "17:00"}
    for equipment in payload["planning"]["equipment_constraints"]:
        equipment["permitted_time_windows"] = [{"start": "10:00", "end": "17:00"}]
    response = client.post("/api/prd/recommendations/constraint-filtered", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["recommendable_candidate_ids"] == ["offset-120"]
    assert body["original_schedule"]["prd_feasible"] is False
    assert "outside_total_work_window" in {row["code"] for row in body["original_schedule"]["violations"]}


def test_constraint_filter_returns_no_recommendation_when_all_candidates_infeasible():
    payload = integrated_payload()
    payload["planning"]["fixed_tasks"] = [{
        "task_id": "cut", "fixed_start": "06:00", "fixed_end": "07:00", "reason": "confirmed fixed work",
        "source_metadata": {"status": "user_provided", "source": "confirmed form"},
    }]
    response = client.post("/api/prd/recommendations/constraint-filtered", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["recommendation_status"] == "none_feasible"
    assert body["recommendable_candidate_ids"] == []
    assert all(not row["recommendable"] for row in body["candidates"])
    assert all("fixed_task_start_changed" in {item["code"] for item in row["violations"]} for row in body["candidates"])


def test_validator_reports_equipment_time_daily_and_concurrent_violations():
    payload = validation_payload()
    payload["planning"]["equipment_constraints"][0]["required_usage_minutes"] = 120
    payload["assignments"].insert(1, {"task_id": "dig-2", "start": "2026-09-11T08:30:00+09:00", "end": "2026-09-11T09:30:00+09:00"})
    payload["equipment_by_task"]["dig-2"] = "excavator"
    payload["equipment_count_by_task"].update({"dig": 2, "dig-2": 1})
    response = client.post("/api/prd/schedules/validate", json=payload)
    codes = {row["code"] for row in response.json()["violations"]}
    assert response.status_code == 200
    assert {"equipment_daily_count_exceeded", "equipment_concurrent_count_exceeded"} <= codes


def test_validator_reports_road_fixed_predecessor_restoration_and_completion_violations():
    payload = validation_payload()
    payload["planning"]["project_completion_date"] = "2026-09-10"
    payload["assignments"] = [
        {"task_id": "dig", "start": "2026-09-11T07:00:00+09:00", "end": "2026-09-11T08:00:00+09:00"},
        {"task_id": "restore", "start": "2026-09-11T07:30:00+09:00", "end": "2026-09-12T00:30:00+09:00"},
    ]
    response = client.post("/api/prd/schedules/validate", json=payload)
    assert response.status_code == 200
    codes = {row["code"] for row in response.json()["violations"]}
    assert {"outside_road_occupancy_permit", "fixed_task_start_changed", "fixed_task_end_changed",
            "predecessor_violation", "same_day_restoration_violation", "project_completion_date_exceeded"} <= codes


def test_integrated_endpoint_http_validation_cors_and_openapi_response_model():
    invalid = integrated_payload()
    invalid["analysis_date"] = "2026-09-12"
    assert client.post("/api/prd/recommendations/constraint-filtered", json=invalid).status_code == 422
    preflight = client.options("/api/prd/recommendations/constraint-filtered", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert preflight.status_code == 200
    schema = app.openapi()
    for path in ("/api/prd/planning/from-notice", "/api/prd/recommendations/constraint-filtered"):
        assert schema["paths"][path]["post"]["responses"]["200"]["content"]["application/json"]["schema"]


def test_10_07_demo_has_no_overlap_and_recommends_original():
    payload = integrated_payload()
    payload["analysis_date"] = "2026-10-07"
    payload["planning"]["construction_period"] = {"start": "2026-10-07", "end": "2026-10-07", "raw_text": "confirmed"}
    payload["planning"]["project_completion_date"] = "2026-10-07"
    response = client.post("/api/prd/recommendations/constraint-filtered", json=payload)
    assert response.status_code == 200
    body = response.json()
    original = next(row for row in body["candidates"] if row["candidate_id"] == "offset-0")
    shifted = next(row for row in body["candidates"] if row["candidate_id"] == "offset-120")
    assert original["objective_values"]["existing_high_noise_overlap_minutes"] == 0
    assert shifted["objective_values"]["existing_high_noise_overlap_minutes"] == 0
    assert body["recommendable_candidate_ids"] == ["offset-0"]


def test_s1_to_s4_user_correction_partial_feasibility_and_comparison_flow():
    extraction = client.post("/api/notices/extract", json={
        "text": "2026년 신촌 연세로 공사 07:00~18:00, 절단기, 브레이커, 굴착기, 롤러"
    })
    assert extraction.status_code == 200
    extracted = extraction.json()
    draft_response = client.post("/api/prd/planning/from-notice", json={
        "notice": extracted["notice"], "extractor_mode": extracted["mode"],
        "is_actual_ai": extracted["is_actual_ai"], "field_evidence": extracted["field_evidence"],
    })
    assert draft_response.status_code == 200
    assert "road_excavation" in draft_response.json()["missing_fields"]

    request = integrated_payload()
    request["planning"]["total_work_window"] = {"start": "09:00", "end": "17:00"}
    for equipment in request["planning"]["equipment_constraints"]:
        equipment["permitted_time_windows"] = [{"start": "09:00", "end": "17:00"}]

    original_assignments = [
        {"task_id": "cut", "start": "2026-09-11T07:00:00+09:00", "end": "2026-09-11T08:00:00+09:00"},
        {"task_id": "break", "start": "2026-09-11T08:00:00+09:00", "end": "2026-09-11T10:00:00+09:00"},
        {"task_id": "excavate", "start": "2026-09-11T10:00:00+09:00", "end": "2026-09-11T15:00:00+09:00"},
        {"task_id": "compact", "start": "2026-09-11T15:00:00+09:00", "end": "2026-09-11T16:00:00+09:00"},
    ]
    validation = client.post("/api/prd/schedules/validate", json={
        **request, "assignments": original_assignments,
    })
    assert validation.status_code == 200
    assert validation.json()["feasible"] is False
    assert "outside_total_work_window" in {row["code"] for row in validation.json()["violations"]}

    recommendations = client.post("/api/prd/recommendations/constraint-filtered", json=request)
    assert recommendations.status_code == 200
    recommendation = recommendations.json()
    feasible = [row for row in recommendation["candidates"] if row["prd_feasible"]]
    infeasible = [row for row in recommendation["candidates"] if not row["prd_feasible"]]
    assert feasible and infeasible
    assert recommendation["recommendable_candidate_ids"] == ["offset-120"]

    selected = next(row for row in recommendation["candidates"] if row["candidate_id"] == "offset-120")
    comparison = client.post("/api/schedules/compare", json={
        "scenario_id": recommendation["scenario_id"], "analysis_date": request["analysis_date"],
        "background_profile": "road_traffic_observed_profile",
        "before": recommendation["original_schedule"]["assignments"], "after": selected["assignments"],
    })
    assert comparison.status_code == 200
    assert comparison.json()["before"]["schedule_change_minutes"] == 0
    assert recommendation["simulation_status"] == "simulated"


def test_v3_1_types_include_both_integrated_operations_and_models():
    declaration = (ROOT / "frontend-contract" / "types" / "api.d.ts").read_text(encoding="utf-8")
    for token in (
        '"/api/prd/planning/from-notice"',
        '"/api/prd/recommendations/constraint-filtered"',
        "PRDPlanningDraftRequest",
        "PRDPlanningDraftResponse",
        "PRDConstraintRecommendationRequest",
        "PRDConstraintRecommendationResponse",
    ):
        assert token in declaration
