from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/building_footprints"
PROCESSED = ROOT / "data/processed"
OSM_URL = "https://www.openstreetmap.org/copyright"
RESIDENTIAL = {"apartments", "residential", "house", "detached", "terrace", "semidetached_house", "dormitory"}
ANCHORS = {
    "segment-yeonse-ro-2na-gil": {
        "address": "서울특별시 서대문구 연세로2나길 20", "lat": 37.5569953, "lon": 126.9384393,
        "quality": "exact_road_address_osm_building_match", "source_id": "way/1499237143",
    },
    "segment-chungjeong-ro": {
        "address": "서울특별시 서대문구 충정로 35-17", "lat": None, "lon": None,
        "quality": "unresolved_exact_address", "source_id": None,
    },
}


def is_residential_tag(tags: dict) -> bool:
    return tags.get("building", "") in RESIDENTIAL


def exact_road_address(tags: dict, expected_street: str, expected_number: str) -> bool:
    return tags.get("addr:street") == expected_street and tags.get("addr:housenumber") == expected_number


def _xy(lat: float, lon: float, lat0: float, lon0: float) -> tuple[float, float]:
    """Local equirectangular metres, adequate for the declared <=300 m filter."""
    radius = 6371008.8
    return (math.radians(lon - lon0) * radius * math.cos(math.radians(lat0)), math.radians(lat - lat0) * radius)


def _centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    ring = points[:-1] if len(points) > 1 and points[0] == points[-1] else points
    return sum(x for x, _ in ring) / len(ring), sum(y for _, y in ring) / len(ring)


def _segment_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _polygon_distance(points: list[tuple[float, float]]) -> float:
    ring = points if points[0] == points[-1] else points + [points[0]]
    return min(_segment_distance(0, 0, *ring[i], *ring[i + 1]) for i in range(len(ring) - 1))


def _address(tags: dict) -> str:
    street, number = tags.get("addr:street", ""), tags.get("addr:housenumber", "")
    return " ".join(x for x in ["서울특별시", tags.get("addr:district", ""), street, number] if x).strip()


def _raw_file_metadata() -> list[dict]:
    names = ["nominatim_yeonse_20261024.json", "nominatim_chungjeong_20261024.json", "osm_yeonse_300m_20261024.json", "osm_chungjeong_search_500m_20261024.json"]
    return [{"filename": name, "bytes": (RAW / name).stat().st_size, "sha256": hashlib.sha256((RAW / name).read_bytes()).hexdigest()} for name in names]


def build_outputs() -> dict:
    source = RAW / "osm_yeonse_300m_20261024.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    anchor = ANCHORS["segment-yeonse-ro-2na-gil"]
    buildings, candidates = [], []
    seen = set()
    for element in data["elements"]:
        source_id = f"osm-way-{element['id']}"
        if source_id in seen or not element.get("geometry"):
            continue
        seen.add(source_id)
        tags = element.get("tags", {})
        building_type = tags.get("building", "")
        if not is_residential_tag(tags):
            continue
        lat0, lon0 = anchor["lat"], anchor["lon"]
        projected = [_xy(p["lat"], p["lon"], lat0, lon0) for p in element["geometry"]]
        cx, cy = _centroid(projected)
        centroid_distance = math.hypot(cx, cy)
        boundary_distance = _polygon_distance(projected)
        if boundary_distance > 300:
            continue
        center_lat = element.get("center", {}).get("lat") or sum(p["lat"] for p in element["geometry"][:-1]) / max(1, len(element["geometry"]) - 1)
        center_lon = element.get("center", {}).get("lon") or sum(p["lon"] for p in element["geometry"][:-1]) / max(1, len(element["geometry"]) - 1)
        building_id = source_id
        buildings.append({
            "building_id": building_id, "source_building_id": f"way/{element['id']}",
            "road_address": _address(tags), "parcel_address": "", "building_name": tags.get("name", ""),
            "primary_use": building_type, "residential_type": building_type,
            "centroid_lat": round(float(center_lat), 7), "centroid_lon": round(float(center_lon), 7),
            "polygon_source": "OpenStreetMap", "attribute_source": "OpenStreetMap building tag",
            "geometry_crs": "EPSG:4326", "classification_status": "osm_residential_tag_only",
            "residential_classification_confidence": "low_not_building_register_verified",
            "source_url": OSM_URL, "source_date": data["osm3s"]["timestamp_osm_base"],
            "geometry": {"type": "Polygon", "coordinates": [[[p["lon"], p["lat"]] for p in element["geometry"]]]},
        })
        candidates.append({
            "candidate_id": f"segment-yeonse-ro-2na-gil:{building_id}", "segment_id": "segment-yeonse-ro-2na-gil",
            "building_id": building_id, "reference_address": anchor["address"],
            "address_anchor_distance_m": round(boundary_distance, 3),
            "building_centroid_distance_m": round(centroid_distance, 3),
            "receptor_lat": "", "receptor_lon": "", "receptor_height_m": "",
            "receptor_point_status": "deferred_no_construction_alignment",
            "distance_basis": "address anchor to nearest OSM polygon boundary; not construction-source distance",
            "provenance": "osm_odbl_exploratory", "calculation_status": "candidate_only",
        })
    buildings.sort(key=lambda x: x["building_id"])
    candidates.sort(key=lambda x: (x["address_anchor_distance_m"], x["candidate_id"]))

    building_fields = ["building_id", "source_building_id", "road_address", "parcel_address", "building_name", "primary_use", "residential_type", "centroid_lat", "centroid_lon", "polygon_source", "attribute_source", "geometry_crs", "classification_status", "residential_classification_confidence", "source_url", "source_date"]
    candidate_fields = ["candidate_id", "segment_id", "building_id", "reference_address", "address_anchor_distance_m", "building_centroid_distance_m", "receptor_lat", "receptor_lon", "receptor_height_m", "receptor_point_status", "distance_basis", "provenance", "calculation_status"]
    for path, rows, fields in ((PROCESSED / "residential_buildings.csv", buildings, building_fields), (PROCESSED / "receptor_candidates.csv", candidates, candidate_fields)):
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n"); writer.writeheader()
            writer.writerows({key: row.get(key, "") for key in fields} for row in rows)
    features = [{"type": "Feature", "id": row["building_id"], "properties": {k: v for k, v in row.items() if k != "geometry"}, "geometry": row["geometry"]} for row in buildings]
    (PROCESSED / "residential_buildings.geojson").write_text(json.dumps({"type": "FeatureCollection", "name": "OSM residential-tagged buildings; not building-register verified", "crs": {"type": "name", "properties": {"name": "EPSG:4326"}}, "features": features}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    radii = {str(radius): sum(row["address_anchor_distance_m"] <= radius for row in candidates) for radius in (100, 200, 300)}
    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "raw_files": _raw_file_metadata(),
        "anchors": ANCHORS, "source_license": "OpenStreetMap contributors, ODbL 1.0",
        "segments": {
            "segment-yeonse-ro-2na-gil": {"downloaded_building_polygons": len(data["elements"]), "residential_tagged_candidates": len(buildings), "officially_verified_residential": 0, "unclassified_or_nonresidential_osm_polygons": len(data["elements"]) - len(buildings), "counts_by_address_anchor_boundary_radius_m": radii},
            "segment-chungjeong-ro": {"downloaded_search_building_polygons": len(json.loads((RAW / "osm_chungjeong_search_500m_20261024.json").read_text())["elements"]), "residential_tagged_candidates": 0, "officially_verified_residential": 0, "counts_by_address_anchor_boundary_radius_m": {"100": 0, "200": 0, "300": 0}, "failure": "exact road-address anchor unresolved; search-area polygons were not promoted to candidates"},
        },
        "official_polygon_count": 0, "address_only_confirmed_buildings": 1,
        "receptor_wall_points_verified": 0, "official_construction_geometry_status": "null_unchanged",
        "field_prediction_status": "deferred", "validation_status": "not_evaluable",
        "limitations": ["VWorld GIS building download requires interactive access/login and no Seoul extract was acquired", "Building HUB API returned HTTP 403 for the approved project key", "OSM residential tags were not cross-verified against Building HUB", "Chungjeong-ro exact address geocoding did not resolve"],
    }
    (PROCESSED / "receptor_coverage_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(build_outputs(), ensure_ascii=False, indent=2))
