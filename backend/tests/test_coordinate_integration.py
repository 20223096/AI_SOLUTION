import json
import logging

import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.services.coordinate_lookup import JusoCoordinateClient

ADDRESS = "서울특별시 서대문구 연세로2나길 20"


def response(results, status=200):
    return httpx.Response(status, json={"results": results})


def search_row(address=ADDRESS, address_id="1141011700100430021007684"):
    return {
        "roadAddr": address,
        "roadAddrPart1": address,
        "jibunAddr": "서울특별시 서대문구 창천동 43-21",
        "bdNm": "",
        "bdMgtSn": address_id,
        "admCd": "1141011700",
        "rnMgtSn": "114104136366",
        "udrtYn": "0",
        "buldMnnm": "20",
        "buldSlno": "0",
    }


def lookup(handler, address=ADDRESS, selected=None):
    return JusoCoordinateClient("search-secret", "coord-secret", transport=httpx.MockTransport(handler)).lookup(address, selected)


def test_settings_load_project_root_env_and_secrets_are_redacted():
    settings = Settings()
    assert settings.juso_search_api_key is not None
    assert settings.juso_coord_api_key is not None
    assert "JUSO_COORD_API_KEY" not in repr(settings)
    assert settings.juso_coord_api_key.get_secret_value() not in repr(settings)


def test_resolved_coordinate_keeps_unverified_geometries_null_and_converts_crs():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return response({"common": {"errorCode": "0", "totalCount": "1"}, "juso": [search_row()]})
        return response({"common": {"errorCode": "0", "totalCount": "1"}, "juso": [{"entX": "947993.342", "entY": "1951502.118"}]})

    result, status = lookup(handler)
    assert status == 200 and result.status == "resolved"
    assert result.source_coordinate.crs == "EPSG:5179"
    assert result.map_coordinate.crs == "EPSG:4326"
    assert 126 < result.map_coordinate.longitude < 128
    assert 36 < result.map_coordinate.latitude < 39
    assert result.construction_geometry is result.demo_geometry is result.residential_facade_receptor is None
    assert result.site_accuracy_status == "not_validated"


def test_no_result_and_invalid_address_are_not_promoted_to_coordinates():
    def handler(request):
        return response({"common": {"errorCode": "0", "totalCount": "0"}, "juso": None})

    result, status = lookup(handler, "존재하지 않는 주소 문자열")
    assert status == 200 and result.status == "not_found"
    assert result.official_address_coordinate is None
    assert result.user_confirmation_required


def test_multiple_candidates_require_selection_then_selected_candidate_resolves():
    rows = [search_row("서울특별시 서대문구 연세로 1", "id-1"), search_row("서울특별시 서대문구 연세로 2", "id-2")]

    def ambiguous(request):
        return response({"common": {"errorCode": "0", "totalCount": "2"}, "juso": rows})

    result, _ = lookup(ambiguous, "서울 서대문구 연세로")
    assert result.status == "selection_required"
    assert len(result.candidates) == 2 and result.user_confirmation_required

    calls = 0

    def selected(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return response({"common": {"errorCode": "0", "totalCount": "2"}, "juso": rows})
        return response({"common": {"errorCode": "0", "totalCount": "1"}, "juso": [{"entX": 950000, "entY": 1950000}]})

    resolved, _ = lookup(selected, "서울 서대문구 연세로", "id-2")
    assert resolved.status == "resolved" and resolved.address_match_status == "user_selected"
    assert resolved.user_confirmation_required


def test_auth_api_error_timeout_rate_limit_and_invalid_coordinate():
    auth, status = lookup(lambda request: response({"common": {"errorCode": "E0001", "errorMessage": "secret must not be copied"}}))
    assert status == 503 and auth.status == "provider_auth_error" and "secret" not in auth.failure_reason

    api_error, status = lookup(lambda request: response({"common": {"errorCode": "-999", "errorMessage": "system"}}))
    assert status == 502 and api_error.status == "provider_error"

    def timeout(request):
        raise httpx.ReadTimeout("timeout", request=request)

    timed_out, status = lookup(timeout)
    assert status == 503 and timed_out.status == "provider_timeout"

    limited, status = lookup(lambda request: httpx.Response(429, request=request))
    assert status == 503 and limited.status == "provider_rate_limited"

    calls = 0

    def bad_coordinate(request):
        nonlocal calls
        calls += 1
        return response({"common": {"errorCode": "0"}, "juso": [search_row()]}) if calls == 1 else response({"common": {"errorCode": "0"}, "juso": [{"entX": "not-a-number", "entY": 1}]})

    invalid, status = lookup(bad_coordinate)
    assert status == 502 and invalid.status == "invalid_provider_coordinate"


def test_keys_do_not_appear_in_logs_or_http_url(caplog):
    seen_urls = []

    def handler(request):
        seen_urls.append(str(request.url))
        return response({"common": {"errorCode": "0", "totalCount": "0"}, "juso": []})

    with caplog.at_level(logging.DEBUG):
        lookup(handler)
    output = "\n".join(record.getMessage() for record in caplog.records)
    assert "search-secret" not in output and "coord-secret" not in output
    assert all("secret" not in url and "confmKey" not in url for url in seen_urls)


def test_http_contract_openapi_cors_and_validation(monkeypatch):
    def fake_lookup(self, address, selected_address_id=None):
        return ({
            "status": "not_found",
            "original_address": address,
            "address_match_status": "no_match",
            "user_confirmation_required": True,
            "failure_reason": "No official road-address result",
        }, 200)

    monkeypatch.setattr(JusoCoordinateClient, "lookup", fake_lookup)
    client = TestClient(app)
    response_value = client.post("/api/locations/address-coordinate", json={"address": "없는 주소"})
    assert response_value.status_code == 200 and response_value.json()["status"] == "not_found"
    assert client.post("/api/locations/address-coordinate", json={"address": " "}).status_code == 422
    preflight = client.options("/api/locations/address-coordinate", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
    assert preflight.status_code == 200 and preflight.headers["access-control-allow-origin"] == "http://localhost:5173"
    operation = app.openapi()["paths"]["/api/locations/address-coordinate"]["post"]
    assert {"200", "422", "502", "503"} <= set(operation["responses"])


def test_public_operation_count_is_28_and_existing_contract_stays_present():
    paths = app.openapi()["paths"]
    operations = sum(method in {"get", "post", "put", "patch", "delete"} for path in paths.values() for method in path)
    assert operations == 28
    assert "/api/noise/predict" in paths and "/api/prd/planning/from-notice" in paths
