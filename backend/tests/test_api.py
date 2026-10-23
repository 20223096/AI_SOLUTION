from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_and_scenarios():
    assert client.get("/api/health").status_code == 200
    ids = {x["id"] for x in client.get("/api/poc/scenarios").json()}
    assert {"case-a", "case-b", "scenario-b-congestion", "scenario-c-exam", "scenario-d-restricted"} <= ids


def test_extract_schema_and_no_guessing():
    data = client.post("/api/notices/extract", json={"text":"신촌 공사, 시간 미정"}).json()
    assert data["mode"] == "mock" and data["is_actual_ai"] is False
    assert data["notice"]["original_work_window"] is None


def test_predict_optimize_compare_experiments():
    assert client.post("/api/noise/predict", json={"scenario_id":"case-a","analysis_date":"2026-10-26"}).status_code == 200
    opt = client.post("/api/schedules/optimize", json={"scenario_id":"case-a","analysis_date":"2026-10-26"})
    assert opt.status_code == 200 and opt.json()["valid_candidates"]
    exp = client.post("/api/experiments/run", json={"scenario_id":"case-a","analysis_date":"2026-10-26"})
    assert exp.status_code == 200


def test_invalid_input_422_and_unknown_404():
    assert client.post("/api/impact/calculate", json={"total_noise_db":70,"duration_minutes":-1,"continuous_minutes":0,"sensitivity_weight":1}).status_code == 422
    assert client.post("/api/noise/predict", json={"scenario_id":"missing"}).status_code == 404


def test_diagnostics_endpoint_and_experiment_b():
    response = client.get("/api/schedules/optimize/scenario-b-congestion/diagnostics?analysis_date=2026-10-26")
    assert response.status_code == 200
    assert response.json()["generated_candidate_count"] == 9
    experiment = client.post("/api/experiments/run", json={"scenario_id":"scenario-c-exam","analysis_date":"2026-10-26"}).json()
    assert experiment["experiment_b"]["recommendation_changed"] is True


def test_background_profile_api_and_incompatible_guard():
    catalog = client.get("/api/noise/background-profiles")
    assert catalog.status_code == 200
    assert catalog.json()["default"] == "assumed_demo"
    response = client.post("/api/noise/predict", json={"scenario_id":"case-a","background_profile":"sdot_observed_profile"})
    assert response.status_code == 422
