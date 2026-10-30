from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.services.data import get_scenario
from app.services.optimizer import _high_noise_overlap_minutes, optimize
from app.services.prediction import default_assignments


DEMO = "final-demo-congestion"
PROFILE = "road_traffic_observed_profile"


def _candidate(result, candidate_id):
    return next(item for item in result["valid_candidates"] if item.id == candidate_id)


def _times(candidate):
    return [(item.task_id, item.start.strftime("%H:%M"), item.end.strftime("%H:%M")) for item in candidate.task_assignments]


def test_9_11_lexicographic_overlap_recommendation_matches_demo_expectation():
    result = optimize(DEMO, date(2026, 9, 11), background_profile=PROFILE)
    original = _candidate(result, "offset-0")
    recommended = result["recommended_options"][0]["candidate"]

    assert [item["candidate"].id for item in result["recommended_options"]] == ["offset-120"]
    assert original.objective_values["existing_high_noise_overlap_minutes"] == 180
    assert recommended.objective_values["existing_high_noise_overlap_minutes"] == 60
    assert _times(original) == [
        ("cut", "08:00", "09:00"),
        ("break", "09:00", "11:00"),
        ("excavate", "11:00", "14:00"),
        ("compact", "14:00", "15:00"),
    ]
    assert _times(recommended) == [
        ("cut", "10:00", "11:00"),
        ("break", "11:00", "13:00"),
        ("excavate", "13:00", "16:00"),
        ("compact", "16:00", "17:00"),
    ]
    assert recommended.schedule_change_details["predecessor_order_preserved"] is True
    assert recommended.schedule_change_details["resource_conflicts"] == []
    assert result["diagnostics"]["representative_selection_order"] == [
        "existing_high_noise_overlap_minutes", "change_cost", "candidate_id"
    ]


def test_10_07_has_no_demolition_overlap_and_keeps_original_schedule():
    result = optimize(DEMO, date(2026, 10, 7), background_profile=PROFILE)
    assert [item["candidate"].id for item in result["recommended_options"]] == ["offset-0"]
    assert all(item.objective_values["existing_high_noise_overlap_minutes"] == 0 for item in result["valid_candidates"])
    assert result["recommended_options"][0]["candidate"].objective_values["change_cost"] == 0


def test_demo_window_durations_receptors_and_boundaries_are_preserved():
    scenario = get_scenario(DEMO)
    notice = scenario["notice"]
    assert (notice.original_work_window.start.strftime("%H:%M"), notice.original_work_window.end.strftime("%H:%M")) == ("08:00", "17:00")
    assert [(item.id, item.duration_minutes) for item in notice.tasks] == [
        ("cut", 60), ("break", 120), ("excavate", 180), ("compact", 60)
    ]
    receptor = next(item for item in scenario["receptors"] if item.id == "assumed-residential-25m")
    assert receptor.distance_to_source_m == 25
    assert receptor.spatial_status == "assumed"
    assert receptor.latitude is receptor.longitude is None
    assert {item.id for item in scenario["receptors"]} >= {"school-changseo", "school-changcheon", "hospital-severance"}

    result = optimize(DEMO, date(2026, 9, 11), background_profile=PROFILE)
    latest = _candidate(result, "offset-120")
    assert latest.task_assignments[0].start.strftime("%H:%M") == "10:00"
    assert latest.task_assignments[-1].end.strftime("%H:%M") == "17:00"
    assert _candidate(result, "offset-0").objective_values["existing_high_noise_overlap_minutes"] == 180


def test_demo_api_is_deterministic_and_exposes_actual_overlap_numbers():
    client = TestClient(app)
    first = client.get("/api/prd/recommendation-diagnostics", params={"analysis_date": "2026-09-11"})
    second = client.get("/api/prd/recommendation-diagnostics", params={"analysis_date": "2026-09-11"})
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    body = first.json()
    assert body["recommended_candidate_ids"] == ["offset-120"]
    original = next(item for item in body["candidates"] if item["id"] == "offset-0")
    recommended = next(item for item in body["candidates"] if item["id"] == "offset-120")
    assert (original["existing_high_noise_overlap_minutes"], recommended["existing_high_noise_overlap_minutes"]) == (180, 60)


def test_final_demo_notice_mock_extraction_preserves_general_and_equipment_windows():
    text = """연세로2나길 20 일대 외 1개소 하수관로 개량공사
    공사 기간: 2026.08.31 ~ 2026.12.18
    일반 공사시간 07:00~18:00, 특정 장비 허용시간 08:00~17:00
    콘크리트 절단기 1대, 브레이커 1대, 터파기 굴착기 1대, 롤러 1대, 당일 복구"""
    response = TestClient(app).post("/api/notices/extract", json={"text": text})
    assert response.status_code == 200
    notice = response.json()["notice"]
    assert notice["original_work_window"] == {"start": "07:00:00", "end": "18:00:00"}
    assert [(task["id"], task["duration_minutes"]) for task in notice["tasks"]] == [
        ("cut", 60), ("break", 120), ("excavate", 180), ("compact", 60)
    ]
    assert all(task["permitted_time_windows"] == [{"start": "08:00:00", "end": "17:00:00"}] for task in notice["tasks"])
    assert notice["constraints"] == {"road_excavation": True, "same_day": True, "equipment_count": 1}

    draft_response = TestClient(app).post("/api/prd/planning/from-notice", json={
        "notice": notice, "extractor_mode": "mock", "is_actual_ai": False,
        "field_evidence": response.json()["field_evidence"],
    })
    assert draft_response.status_code == 200
    planning = draft_response.json()["planning_draft"]
    assert planning["total_work_window"] == {"start": "07:00:00", "end": "18:00:00"}
    assert all(row["required_usage_minutes"] in {60, 120, 180} for row in planning["equipment_constraints"])
    assert all(row["permitted_time_windows"] == [{"start": "08:00:00", "end": "17:00:00"}] for row in planning["equipment_constraints"])
    planning["provenance"] = "user_provided"

    recommendation = TestClient(app).post("/api/prd/recommendations/constraint-filtered", json={
        "analysis_date": "2026-09-11", "planning": planning,
        "predecessors": planning["predecessors"],
        "equipment_by_task": {task["id"]: task["equipment_id"] for task in notice["tasks"]},
        "equipment_count_by_task": {task["id"]: 1 for task in notice["tasks"]},
        "restoration_task_ids": ["compact"],
        "background_profile": PROFILE, "objective_mode": "incremental_impact",
    })
    assert recommendation.status_code == 200
    assert recommendation.json()["recommendable_candidate_ids"] == ["offset-120"]


def test_overlap_uses_temporal_union_and_excludes_the_new_project_itself(monkeypatch):
    scenario = get_scenario(DEMO)
    assignments = default_assignments(scenario, date(2026, 9, 11))
    event = {
        "id": "assumed-nearby-construction-final-demo", "project_id": "other-project",
        "high_noise": True, "active_dates": ["2026-09-11"], "start_time": "08:00", "end_time": "11:00",
        "receptor_ids": ["assumed-residential-25m"],
    }
    monkeypatch.setattr("app.services.optimizer.load_json_rows", lambda _: [event, {**event, "id": "duplicate"}])
    scenario["settings"]["high_noise_event_ids"] = [event["id"], "duplicate"]
    assert _high_noise_overlap_minutes(scenario, date(2026, 9, 11), assignments) == 180

    scenario["settings"]["new_project_id"] = "other-project"
    assert _high_noise_overlap_minutes(scenario, date(2026, 9, 11), assignments) == 0

