import csv
import json
import math
from pathlib import Path

import pytest

from app.services.public_data import official_construction_design
from app.services.receptor_data import residential_receptor_dataset
from scripts.process_residential_receptors import ANCHORS, _polygon_distance, _xy, exact_road_address, is_residential_tag

ROOT = Path(__file__).resolve().parents[2]


def test_two_address_anchors_are_independent_and_not_shared():
    a, b = ANCHORS["segment-yeonse-ro-2na-gil"], ANCHORS["segment-chungjeong-ro"]
    assert (a["lat"], a["lon"]) == (37.5569953, 126.9384393)
    assert b["lat"] is b["lon"] is None
    assert a["quality"] != b["quality"]


def test_osm_polygon_output_parses_and_is_validly_closed():
    geojson = json.loads((ROOT / "data/processed/residential_buildings.geojson").read_text())
    assert geojson["features"]
    for feature in geojson["features"]:
        ring = feature["geometry"]["coordinates"][0]
        assert feature["geometry"]["type"] == "Polygon"
        assert len(ring) >= 4 and ring[0] == ring[-1]


def test_residential_use_matching_does_not_promote_generic_building():
    assert is_residential_tag({"building": "apartments"})
    assert is_residential_tag({"building": "house"})
    assert not is_residential_tag({"building": "yes"})
    assert not is_residential_tag({"building": "commercial"})


def test_wrong_address_join_is_rejected_by_exact_components():
    tags = {"addr:street": "연세로2나길", "addr:housenumber": "20"}
    assert exact_road_address(tags, "연세로2나길", "20")
    assert not exact_road_address(tags, "충정로", "35-17")
    assert not exact_road_address(tags, "연세로2나길", "2")


def test_candidates_are_not_assigned_to_unresolved_chungjeong_segment():
    data = residential_receptor_dataset()
    assert data["candidates"]
    assert {row["segment_id"] for row in data["candidates"]} == {"segment-yeonse-ro-2na-gil"}
    assert data["report"]["segments"]["segment-chungjeong-ro"]["residential_tagged_candidates"] == 0


def test_local_metric_distance_is_in_metres():
    x, y = _xy(37.5579953, 126.9384393, 37.5569953, 126.9384393)
    assert x == pytest.approx(0, abs=0.01)
    assert y == pytest.approx(111.2, abs=0.2)
    assert _polygon_distance([(10, -5), (20, -5), (20, 5), (10, 5), (10, -5)]) == pytest.approx(10)


def test_receptor_point_is_distinct_from_building_centroid():
    with (ROOT / "data/processed/receptor_candidates.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))
    assert row["building_centroid_distance_m"]
    assert row["receptor_lat"] == row["receptor_lon"] == row["receptor_height_m"] == ""
    assert row["receptor_point_status"] == "deferred_no_construction_alignment"


def test_geojson_crs_and_seoul_bounds_are_validated():
    data = json.loads((ROOT / "data/processed/residential_buildings.geojson").read_text())
    assert data["crs"]["properties"]["name"] == "EPSG:4326"
    for feature in data["features"]:
        for lon, lat in feature["geometry"]["coordinates"][0]:
            assert 126.7 < lon < 127.3 and 37.4 < lat < 37.8


def test_official_construction_geometry_remains_null():
    assert all(segment["geometry"] is None and segment["representative_point"] is None for segment in official_construction_design()["segments"])


def test_source_and_classification_limit_are_preserved():
    data = residential_receptor_dataset()
    assert data["report"]["source_license"] == "OpenStreetMap contributors, ODbL 1.0"
    assert data["report"]["official_polygon_count"] == 0
    assert data["report"]["receptor_wall_points_verified"] == 0
    assert data["official_construction_prediction_status"] == "deferred"
