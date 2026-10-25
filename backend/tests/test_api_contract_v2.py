from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import Settings


ROOT = Path(__file__).parents[2]
EXAMPLES = ROOT / "frontend-contract" / "examples"
client = TestClient(app)


def success_examples():
    return sorted(EXAMPLES.glob("[0-9][0-9]-*.json"))


@pytest.mark.parametrize("example_path", success_examples(), ids=lambda path: path.stem)
def test_all_21_responses_match_pre_response_model_json(example_path: Path):
    capture = json.loads(example_path.read_text(encoding="utf-8"))
    request = capture["request"]
    path = urlsplit(request["url"]).path
    query = urlsplit(request["url"]).query
    url = f"{path}?{query}" if query else path
    if "multipart" in request:
        item = request["multipart"]["file"]
        files = {"file": (item["filename"], item.get("text", "abc").encode(), item["content-type"])}
        response = client.request(request["method"], url, files=files)
    else:
        response = client.request(request["method"], url, json=request.get("body"))
    assert response.status_code == 200
    def assert_same_json_type(actual, expected, path="$"):
        assert type(actual) is type(expected), (path, type(actual), type(expected))
        if isinstance(expected, dict):
            assert actual.keys() == expected.keys(), path
            for key in expected:
                assert_same_json_type(actual[key], expected[key], f"{path}.{key}")
        elif isinstance(expected, list):
            assert len(actual) == len(expected), path
            for index, (actual_item, expected_item) in enumerate(zip(actual, expected)):
                assert_same_json_type(actual_item, expected_item, f"{path}[{index}]")
        else:
            assert actual == expected, path

    assert_same_json_type(response.json(), capture["response"]["body"])


def test_every_business_operation_has_explicit_success_response_schema():
    routes = [route for route in app.routes if isinstance(route, APIRoute) and route.path.startswith("/api/")]
    assert len(routes) == 27
    assert {"/api/prd/planning/from-notice", "/api/prd/recommendations/constraint-filtered"} <= {route.path for route in routes}
    captured_paths = {urlsplit(json.loads(path.read_text())["request"]["url"]).path for path in success_examples()}
    assert len({path for path in captured_paths if not path.startswith("/api/prd/")}) == 21
    assert len(captured_paths) == 27
    assert all(route.response_model is not None for route in routes)
    schema = app.openapi()
    for route in routes:
        method = next(iter(route.methods - {"HEAD", "OPTIONS"})).lower()
        success = schema["paths"][route.path][method]["responses"]["200"]["content"]["application/json"]["schema"]
        assert success, (method, route.path)
        assert success != {}, (method, route.path)


def test_status_and_null_branches_are_response_model_validated():
    m1 = json.loads((EXAMPLES / "08-noise-predict-m1.json").read_text(encoding="utf-8"))["request"]["body"]
    m1["sources"][0]["position"] = None
    m1["sources"][0]["actual_active_minutes"] = None
    m1["sources"][0]["activity_provenance"] = "unknown"
    deferred = client.post("/api/noise/predict-m1", json=m1)
    assert deferred.status_code == 200
    assert deferred.json()["calculation_status"] == "deferred"
    assert deferred.json()["validation_status"] == "not_evaluable"

    simulated = client.post(
        "/api/noise/evaluate-m1-candidates",
        json=json.loads((EXAMPLES / "11-evaluate-m1-candidates.json").read_text(encoding="utf-8"))["request"]["body"],
    )
    assert simulated.status_code == 200
    assert simulated.json()["evaluation_status"] == "simulated"

    partial = client.post(
        "/api/noise/design-simulation/reschedule",
        json=json.loads((EXAMPLES / "14-design-simulation-reschedule.json").read_text(encoding="utf-8"))["request"]["body"],
    )
    assert partial.status_code == 200
    assert partial.json()["recommended_candidate"]["acoustic_completeness"] == "partial"

    not_evaluable = client.post("/api/noise/validate-m1-field", json={"observations": [], "predictions": []})
    assert not_evaluable.status_code == 200
    assert not_evaluable.json()["validation_status"] == "not_evaluable"
    assert not_evaluable.json()["mae"] is None


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_allowed_cors_json_and_multipart_preflight(origin: str):
    for path, method, headers in (
        ("/api/noise/predict", "POST", "content-type"),
        ("/api/notices/extract-file", "POST", "content-type"),
        ("/api/health", "GET", "accept"),
    ):
        response = client.options(path, headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": headers,
        })
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
        assert "true" not in response.headers.get("access-control-allow-credentials", "").lower()


def test_disallowed_cors_origin_has_no_access_permission():
    origin = "https://untrusted.example"
    preflight = client.options("/api/noise/predict", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in preflight.headers
    simple = client.get("/api/health", headers={"Origin": origin})
    assert simple.status_code == 200
    assert "access-control-allow-origin" not in simple.headers


def test_cors_origins_can_be_supplied_by_environment(monkeypatch):
    monkeypatch.setenv("SHH_CORS_ALLOWED_ORIGINS", '["https://frontend.example"]')
    assert Settings().cors_allowed_origins == ["https://frontend.example"]


def test_checked_in_openapi_and_types_are_response_typed():
    checked_in = json.loads((ROOT / "docs" / "openapi.json").read_text(encoding="utf-8"))
    assert checked_in == app.openapi()
    declaration = (ROOT / "frontend-contract" / "types" / "api.d.ts").read_text(encoding="utf-8")
    assert "HealthResponse" in declaration
    assert "NoisePredictResponse" in declaration
    assert "OptimizeSuccessResponse" in declaration
    assert "OptimizeInfeasibleResponse" in declaration
