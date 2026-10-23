import csv
import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.optimizer import optimize
from app.services.prediction import predict
from app.services.public_data import acoustic_public_events, is_exam_period, public_catalog
from scripts.collect_public_data.common import CollectionResult, VALID_STATUSES
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
