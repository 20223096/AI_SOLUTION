from datetime import date

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def validation_payload() -> dict:
    return {
        "analysis_date": "2026-09-11",
        "planning": {
            "notice_id": "demo-notice",
            "project_name": "신촌 시연 공사",
            "location": "서울특별시 서대문구 신촌동",
            "construction_period": {"start": "2026-09-11", "end": "2026-09-11", "raw_text": "시연 입력"},
            "total_work_window": {"start": "07:00", "end": "18:00"},
            "road_excavation": True,
            "road_occupancy_permit_window": {"start": "08:00", "end": "17:00"},
            "equipment_constraints": [{
                "equipment_id": "excavator", "category": "굴착기", "specification": "06W", "model_name": None,
                "max_daily_count": 1, "required_usage_minutes": 60,
                "permitted_time_windows": [{"start": "08:00", "end": "17:00"}],
                "source_metadata": {"status": "user_provided", "source": "demo form", "note": None, "unit": None},
            }],
            "fixed_tasks": [{
                "task_id": "restore", "fixed_start": "16:00", "fixed_end": "17:00", "reason": "당일 복구",
                "source_metadata": {"status": "user_provided", "source": "demo form", "note": None, "unit": None},
            }],
            "same_day_restoration_required": True,
            "project_completion_date": "2026-09-11",
            "non_adjustable_conditions": ["restore fixed"],
            "source_evidence": {"page": "2"},
            "field_provenance": {"total_work_window": {"status": "user_provided", "source": "demo form", "note": "not an official permit", "unit": None}},
            "provenance": "user_provided",
        },
        "assignments": [
            {"task_id": "dig", "start": "2026-09-11T08:00:00+09:00", "end": "2026-09-11T09:00:00+09:00"},
            {"task_id": "restore", "start": "2026-09-11T16:00:00+09:00", "end": "2026-09-11T17:00:00+09:00"},
        ],
        "predecessors": {"restore": ["dig"]},
        "equipment_by_task": {"dig": "excavator", "restore": None},
        "equipment_count_by_task": {"dig": 1},
        "restoration_task_ids": ["restore"],
    }


def test_demo_fixture_http_keeps_official_observed_missing_and_assumed_values_distinct():
    response = client.get("/api/prd/demo/2026-09-11")
    assert response.status_code == 200
    body = response.json()
    assert body["provenance_summary"]["literature_reference_values"] == []
    assert body["provenance_summary"]["observed_values"]
    assert body["official_new_construction_design"]["status"] == "official_document"
    assert body["official_new_construction_design"]["daily_work_window"] is None
    assert body["demo_work_plan"]["status"] == "assumed"
    missing_sensor = next(item for item in body["sdot_daily_audit"]["days"][0]["sensors"] if item["sensor_serial"] == "V02Q1940585")
    assert missing_sensor["held_count"] == 24 and missing_sensor["noise_avg_mean"] is None
    waste = next(item for item in body["context_events"] if item["kind"] == "waste_collection")
    assert waste["status"] == "assumed" and waste["source"] is None


def test_prd_schedule_validation_success_and_constraint_failure_are_http_validated():
    success = client.post("/api/prd/schedules/validate", json=validation_payload())
    assert success.status_code == 200
    assert success.json()["feasible"] is True

    payload = validation_payload()
    payload["assignments"][0] = {"task_id": "dig", "start": "2026-09-11T07:00:00+09:00", "end": "2026-09-11T07:30:00+09:00"}
    payload["equipment_count_by_task"]["dig"] = 2
    failure = client.post("/api/prd/schedules/validate", json=payload)
    assert failure.status_code == 200
    assert failure.json()["feasible"] is False
    assert {row["code"] for row in failure.json()["violations"]} >= {"outside_equipment_time_window", "outside_road_occupancy_permit", "equipment_daily_count_exceeded", "equipment_required_usage_mismatch"}


def test_prd_schedule_validation_rejects_unzoned_datetime_with_422():
    payload = validation_payload()
    payload["assignments"][0]["start"] = "2026-09-11T08:00:00"
    response = client.post("/api/prd/schedules/validate", json=payload)
    assert response.status_code == 422


def test_9_11_diagnostics_report_overlap_improvement():
    response = client.get("/api/prd/recommendation-diagnostics", params={"analysis_date": "2026-09-11"})
    assert response.status_code == 200
    body = response.json()
    assert body["scenario_id"] == "final-demo-congestion"
    assert body["recommended_candidate_ids"] == ["offset-120"]
    assert body["improvement_over_original"] is True
    shifted = next(row for row in body["candidates"] if row["id"] == "offset-120")
    assert shifted["project_start_shift_minutes"] == 120
    assert shifted["existing_high_noise_overlap_minutes"] == 60


def test_10_07_diagnostics_excludes_9_11_overlay_and_keeps_original():
    response = client.get("/api/prd/recommendation-diagnostics", params={"analysis_date": "2026-10-07"})
    assert response.status_code == 200
    body = response.json()
    assert body["scenario_id"] == "final-demo-congestion"
    assert body["improvement_over_original"] is False
    assert body["recommended_candidate_ids"] == ["offset-0"]
    assert all(row["existing_noise_overlap_receptor_minutes"] == 0 for row in body["candidates"])
    original = next(row for row in body["candidates"] if row["id"] == "offset-0")
    shifted = next(row for row in body["candidates"] if row["id"] == "offset-120")
    assert shifted["existing_high_noise_overlap_minutes"] == original["existing_high_noise_overlap_minutes"] == 0
    assert shifted["total_task_start_shift_minutes"] == 480


def test_sensitivity_experiment_exposes_both_dates_all_factors_and_candidate_diagnostics():
    response = client.post("/api/prd/sensitivity/experiment", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["policy_version"] == "prd_max_v2_1_experimental"
    assert body["default_m0_m1_unchanged"] is True
    assert [row["analysis_date"] for row in body["experiments"]] == ["2026-09-11", "2026-10-07"]
    for experiment in body["experiments"]:
        assert [case["multiplier"] for case in experiment["cases"]] == [1.1, 1.3, 1.5]
        assert all(len(case["candidate_diagnostics"]) == 9 for case in experiment["cases"])
        assert all(case["infeasible_candidate_ids"] == [] for case in experiment["cases"])


def test_prd_date_validation_error_and_cors_preflight():
    unsupported = client.get("/api/prd/recommendation-diagnostics", params={"analysis_date": "2026-09-12"})
    assert unsupported.status_code == 422
    preflight = client.options("/api/prd/sensitivity/experiment", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"
