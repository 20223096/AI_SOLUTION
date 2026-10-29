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

