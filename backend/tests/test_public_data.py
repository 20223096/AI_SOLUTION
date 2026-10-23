import csv
import json
from datetime import date
from pathlib import Path

import pytest
import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.services.optimizer import optimize
from app.services.prediction import predict
from app.services.public_data import acoustic_public_events, is_exam_period, public_catalog
from scripts.collect_public_data.common import CollectionResult, VALID_STATUSES, load_project_env
from scripts.collect_public_data.sources import _event_times
from scripts.collect_public_data.data_go_kr import authentication_result, normalized_service_key, request_with_service_key
from scripts.collect_public_data.validation import collection_time, deduplicate_events, geodesic_distance_m, pagination_ranges, require_seoul_response_shape, split_event_date_and_time, split_project_and_work_time, validate_acoustic_unit


def test_collection_manifest_has_supported_status_and_provenance():
    catalog = public_catalog()
    assert catalog["manifest"]["results"]
    assert all(x["status"] in VALID_STATUSES and x["source_url"] and x["fetched_at"] for x in catalog["manifest"]["results"])


def test_api_catalog_shape_and_backward_compatibility():
    client = TestClient(app)
    response = client.get("/api/public-data/catalog")
    assert response.status_code == 200
    assert {"manifest", "receptors", "academic_calendar", "policy"} <= response.json().keys()
    assert client.post("/api/noise/predict", json={"scenario_id": "case-a", "analysis_date": "2026-10-26"}).status_code == 200


def test_schedule_only_events_are_never_acoustically_integrated():
    assert acoustic_public_events() == []
    assert public_catalog()["policy"]["schedule_only_events_are_energy_summed"] is False


def test_exam_calendar_is_school_specific_and_drives_integrated_scenario():
    assert is_exam_period(date(2026, 10, 20), "sogang")
    assert not is_exam_period(date(2026, 10, 20), "yonsei")
    during = predict("sinchon-public-2026-10", date(2026, 10, 20))
    outside = predict("sinchon-public-2026-10", date(2026, 11, 2))
    d = next(x for x in during["predictions"] if x["receptor_id"] == "university-1" and x["slot_start"].hour == 8)
    o = next(x for x in outside["predictions"] if x["receptor_id"] == "university-1" and x["slot_start"].hour == 8)
    assert d["sensitivity"]["weight"] > o["sensitivity"]["weight"]


def test_integrated_scenario_is_deterministic_and_optimizable():
    first = optimize("sinchon-public-2026-10", date(2026, 10, 20))
    second = optimize("sinchon-public-2026-10", date(2026, 10, 20))
    assert first == second


def test_project_period_is_not_daily_work_time():
    result = split_project_and_work_time({"project_start_date": "2026-01-01", "project_end_date": "2026-12-31"})
    assert result["work_start_time"] is None and result["work_end_time"] is None


def test_event_date_and_time_are_separate():
    assert split_event_date_and_time("2026-10-20") == ("2026-10-20", None)
    assert split_event_date_and_time("2026-10-20 19:30:00") == ("2026-10-20", "19:30")


def test_lw_lp_validation_prevents_unit_mixing():
    assert validate_acoustic_unit("Lw_dBA") == "Lw_dBA"
    assert validate_acoustic_unit("Lp_dBA") == "Lp_dBA"
    with pytest.raises(ValueError):
        validate_acoustic_unit("dBA")


def test_wgs84_distance_and_missing_coordinates():
    assert 105 < geodesic_distance_m(37.0, 127.0, 37.001, 127.0) < 115
    rows = public_catalog()["receptors"]
    assert all(not row["latitude"] and not row["longitude"] for row in rows)


def test_resident_disposal_is_not_vehicle_collection():
    assert collection_time({"disposal_start_time": "20:00", "disposal_end_time": "24:00"}) is None


def test_existing_noise_etl_was_not_reprocessed():
    policy = public_catalog()["manifest"]["integration_policy"]
    assert policy["sdot_reprocessed"] is False and policy["road_traffic_reprocessed"] is False


def test_seoul_api_shape_pagination_and_event_duplicates():
    assert pagination_ranges(2001) == [(1, 1000), (1001, 2000), (2001, 2001)]
    payload = {"culturalEventInfo": {"list_total_count": 2, "row": [{"TITLE": "A"}]}}
    assert require_seoul_response_shape(payload, "culturalEventInfo") == [{"TITLE": "A"}]
    with pytest.raises(ValueError):
        require_seoul_response_shape({}, "culturalEventInfo")
    row = {"name": "행사", "event_start": "2026-10-20", "event_end": "2026-10-20", "location": "신촌"}
    assert deduplicate_events([row, dict(row)]) == [row]


def test_project_env_loader_does_not_override_explicit_environment(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("SEOUL_OPEN_DATA_API_KEY=file-value\n", encoding="utf-8")
    monkeypatch.setenv("SEOUL_OPEN_DATA_API_KEY", "explicit-value")
    load_project_env(path)
    assert __import__("os").environ["SEOUL_OPEN_DATA_API_KEY"] == "explicit-value"


def test_event_time_parser_does_not_flatten_multi_day_schedules():
    assert _event_times("13:00 ~ 18:00") == ("13:00", "18:00")
    assert _event_times("[9.11] 17:30~20:00, [9.12] 10:00~19:00") == ("", "")


def test_live_collection_manifest_records_verified_seoul_responses():
    results = {x["dataset"]: x for x in public_catalog()["manifest"]["results"]}
    assert results["construction"]["status"] == "processed"
    assert results["events"]["status"] == "processed"
    assert results["construction"]["api_result_code"] == "INFO-000"
    assert results["events"]["api_result_code"] == "INFO-000"
    assert results["construction"]["source_total_count"] >= results["construction"]["row_count"]
    assert results["events"]["source_total_count"] >= results["events"]["row_count"]


def test_data_go_kr_key_is_encoded_exactly_once_with_params():
    captured = {}
    def handler(request):
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"response": {"header": {"resultCode": "00", "resultMsg": "OK"}}})
    response = request_with_service_key(
        "https://apis.data.go.kr/example",
        "abc%2Bdef%2Fghi%3D%3D",
        {"pageNo": 1},
        transport=httpx.MockTransport(handler),
    )
    assert "serviceKey=abc%2Bdef%2Fghi%3D%3D" in captured["url"]
    assert "%252B" not in captured["url"]
    assert authentication_result(response).authenticated is True


def test_data_go_kr_authentication_error_is_classified():
    response = httpx.Response(403, json={"OpenAPI_ServiceResponse": {"cmmMsgHeader": {"errMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR", "returnReasonCode": "30"}}})
    result = authentication_result(response)
    assert result.authenticated is False
    assert result.result_code == "30"


def test_approved_official_facilities_are_exposed_without_changing_scenarios():
    catalog = public_catalog()
    facilities = {row["name"]: row for row in catalog["official_facilities"]}
    assert {"서울창서초등학교", "창천중학교", "연세대학교의과대학세브란스병원"} <= facilities.keys()
    assert all(row["crs"] == "EPSG:4326" for row in facilities.values())
    assert facilities["서울창서초등학교"]["reference_date"] == "2026-10-01"
    assert facilities["연세대학교의과대학세브란스병원"]["reference_date"] == ""
    assert predict("case-a", date(2026, 10, 26))["scenario_id"] == "case-a"
