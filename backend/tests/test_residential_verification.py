import csv
import json
from pathlib import Path

import pytest

from app.services.official_address import epsg5179_to_wgs84, juso_lookup, normalize_service_key, redact_key, validate_building_hub_response
from app.services.public_data import official_construction_design
from scripts.verify_residential_receptors import classify_osm_building, exact_official_match

ROOT = Path(__file__).resolve().parents[2]


def test_epsg5179_to_wgs84_known_seoul_control_point():
    lon, lat = epsg5179_to_wgs84(953900, 1952032)
    assert lon == pytest.approx(126.9779868, abs=1e-6)
    assert lat == pytest.approx(37.5664992, abs=1e-6)


def test_juso_missing_separate_key_is_deferred_without_request():
    assert juso_lookup("서울특별시 서대문구 충정로 35-17", None, lambda *a, **k: pytest.fail("called"))["status"] == "deferred_missing_confm_key"


def test_building_hub_auth_response_and_key_protection():
    payload = {"response": {"header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."}}}
    assert validate_building_hub_response(200, payload)["authenticated"] is True
    assert normalize_service_key("abc%2Bdef") == "abc+def"
    assert "abc" not in redact_key("abc+def")


def test_osm_classification_does_not_promote_generic_use():
    assert classify_osm_building({"building": "apartments"}) == "osm_residential_candidate"
    assert classify_osm_building({"building": "yes"}) == "unknown_building_use"
    assert classify_osm_building({"building": "commercial"}) == "verified_non_residential"


def test_ambiguous_official_match_is_blocked():
    records = [{"road_address": "A", "id": 1}, {"road_address": "A", "id": 2}]
    assert exact_official_match(records, "A") is None
    assert exact_official_match(records[:1], "A")["id"] == 1


def test_a_b_segments_and_duplicate_audit_are_preserved():
    with (ROOT / "data/processed/building_use_match_audit.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert {r["segment_id"] for r in rows} == {"segment-yeonse-ro-2na-gil", "segment-chungjeong-ro"}
    osm_ids = [r["source_building_id"] for r in rows if r["source_building_id"]]
    assert len(rows) == 1560
    assert len(set(osm_ids)) <= 1559


def test_chungjeong_official_identity_not_promoted_to_residential():
    anchors = json.loads((ROOT / "data/processed/official_address_anchors.json").read_text())
    b = next(x for x in anchors["anchors"] if x["segment_id"] == "segment-chungjeong-ro")
    assert b["parcel_address"].endswith("충정로3가 120-1")
    assert b["official_primary_use"] == "제2종근린생활시설"
    assert b["official_coordinate"] is None


def test_source_status_and_official_prediction_remain_deferred():
    report = json.loads((ROOT / "data/processed/receptor_coverage_report.json").read_text())
    assert report["raw_polygon_count"] == 1559
    assert report["official_residential_verified"] == 0
    assert report["field_prediction_status"] == "deferred"
    assert all(x["geometry"] is None for x in official_construction_design()["segments"])
