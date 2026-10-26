from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

from scripts.process_residential_receptors import ANCHORS, PROCESSED, RAW, RESIDENTIAL, _address, _centroid, _polygon_distance, _xy

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "segment-yeonse-ro-2na-gil": "osm_yeonse_300m_20261024.json",
    "segment-chungjeong-ro": "osm_chungjeong_search_500m_20261024.json",
}
KNOWN_NONRESIDENTIAL = {"commercial", "retail", "school", "church", "office", "government", "university", "civic", "parking", "roof", "bridge"}


def classify_osm_building(tags: dict) -> str:
    kind = tags.get("building", "")
    if kind in RESIDENTIAL:
        return "osm_residential_candidate"
    if kind in KNOWN_NONRESIDENTIAL:
        return "verified_non_residential"
    return "unknown_building_use"


def exact_official_match(records: list[dict], road_address: str, parcel_address: str = "") -> dict | None:
    """Never promote fuzzy address matches or ambiguous multi-building parcels."""
    matches = [r for r in records if (road_address and r.get("road_address") == road_address) or (parcel_address and r.get("parcel_address") == parcel_address)]
    return matches[0] if len(matches) == 1 else None


def _backup_v14() -> None:
    target = PROCESSED / "archive/v14"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("residential_buildings.csv", "residential_buildings.geojson", "receptor_candidates.csv", "receptor_coverage_report.json"):
        source = PROCESSED / name
        if source.exists() and not (target / name).exists():
            shutil.copy2(source, target / name)


def build() -> dict:
    _backup_v14()
    buildings, candidates, audit, segment_stats = [], [], [], {}
    seen: set[str] = set()
    for segment_id, filename in FILES.items():
        data = json.loads((RAW / filename).read_text(encoding="utf-8"))
        anchor = ANCHORS[segment_id]
        counts = {key: 0 for key in ("official_residential_verified", "osm_residential_candidate", "unknown_building_use", "verified_non_residential")}
        duplicates = 0
        for element in data["elements"]:
            source_id = f"way/{element['id']}"
            duplicate = source_id in seen
            if duplicate:
                duplicates += 1
            seen.add(source_id)
            tags = element.get("tags", {})
            status = classify_osm_building(tags)
            counts[status] += 1
            audit.append({"segment_id": segment_id, "source_building_id": source_id, "osm_building_tag": tags.get("building", ""), "osm_address": _address(tags), "classification_status": status, "official_building_id": "", "official_primary_use": "", "match_status": "not_matched_no_exact_official_identifier", "duplicate_across_extracts": str(duplicate).lower(), "basis": "OSM tag only; generic building=yes is not residential"})
            if status != "osm_residential_candidate" or duplicate or not element.get("geometry"):
                continue
            center_lat = element.get("center", {}).get("lat") or sum(p["lat"] for p in element["geometry"][:-1]) / max(1, len(element["geometry"]) - 1)
            center_lon = element.get("center", {}).get("lon") or sum(p["lon"] for p in element["geometry"][:-1]) / max(1, len(element["geometry"]) - 1)
            row = {"building_id": f"osm-way-{element['id']}", "source_building_id": source_id, "segment_id": segment_id, "road_address": _address(tags), "parcel_address": "", "building_name": tags.get("name", ""), "primary_use": tags.get("building", ""), "residential_type": tags.get("building", ""), "centroid_lat": round(float(center_lat), 7), "centroid_lon": round(float(center_lon), 7), "polygon_source": "OpenStreetMap", "attribute_source": "OpenStreetMap building tag", "geometry_crs": "EPSG:4326", "classification_status": status, "residential_classification_confidence": "candidate_not_building_register_verified", "source_url": "https://www.openstreetmap.org/copyright", "source_date": data["osm3s"]["timestamp_osm_base"], "geometry": {"type": "Polygon", "coordinates": [[[p["lon"], p["lat"]] for p in element["geometry"]]]}}
            buildings.append(row)
            if anchor["lat"] is not None:
                projected = [_xy(p["lat"], p["lon"], anchor["lat"], anchor["lon"]) for p in element["geometry"]]
                boundary = _polygon_distance(projected)
                cx, cy = _centroid(projected)
                if boundary <= 300:
                    candidates.append({"candidate_id": f"{segment_id}:{row['building_id']}", "segment_id": segment_id, "building_id": row["building_id"], "reference_address": anchor["address"], "address_anchor_distance_m": round(boundary, 3), "building_centroid_distance_m": round((cx*cx + cy*cy) ** .5, 3), "receptor_lat": "", "receptor_lon": "", "receptor_height_m": "", "receptor_point_status": "deferred_no_construction_alignment", "distance_basis": "official/OSM address building anchor to OSM boundary; not construction alignment", "provenance": "osm_odbl_exploratory", "calculation_status": "candidate_only"})
        segment_stats[segment_id] = {"downloaded_building_polygons": len(data["elements"]), "residential_tagged_candidates": counts["osm_residential_candidate"] if anchor["lat"] is not None else 0, "search_area_osm_residential_candidates": counts["osm_residential_candidate"], "officially_verified_residential": 0, "classification_counts": counts, "duplicate_ids": duplicates}

    # Exact Building-HUB title records identify the address buildings, not OSM polygons.
    audit.append({"segment_id": "segment-chungjeong-ro", "source_building_id": "", "osm_building_tag": "", "osm_address": "서울특별시 서대문구 충정로 35-17", "classification_status": "verified_non_residential", "official_building_id": "101411159", "official_primary_use": "제2종근린생활시설", "match_status": "official_address_building_identity_verified_not_polygon_joined", "duplicate_across_extracts": "false", "basis": "Building HUB exact parcel 충정로3가 120-1 and exact road address; general register title"})
    audit.append({"segment_id": "segment-yeonse-ro-2na-gil", "source_building_id": "", "osm_building_tag": "", "osm_address": "서울특별시 서대문구 연세로2나길 20", "classification_status": "verified_non_residential", "official_building_id": "1014112097", "official_primary_use": "숙박시설", "match_status": "official_address_building_identity_verified_not_polygon_joined", "duplicate_across_extracts": "false", "basis": "Building HUB exact parcel 창천동 13-68 and exact road address; general register title"})
    buildings.sort(key=lambda r: (r["segment_id"], r["building_id"]))
    candidates.sort(key=lambda r: (r["segment_id"], r["address_anchor_distance_m"], r["candidate_id"]))
    bfields = ["building_id", "source_building_id", "segment_id", "road_address", "parcel_address", "building_name", "primary_use", "residential_type", "centroid_lat", "centroid_lon", "polygon_source", "attribute_source", "geometry_crs", "classification_status", "residential_classification_confidence", "source_url", "source_date"]
    cfields = ["candidate_id", "segment_id", "building_id", "reference_address", "address_anchor_distance_m", "building_centroid_distance_m", "receptor_lat", "receptor_lon", "receptor_height_m", "receptor_point_status", "distance_basis", "provenance", "calculation_status"]
    afields = ["segment_id", "source_building_id", "osm_building_tag", "osm_address", "classification_status", "official_building_id", "official_primary_use", "match_status", "duplicate_across_extracts", "basis"]
    for path, rows, fields in ((PROCESSED/"residential_buildings.csv", buildings, bfields), (PROCESSED/"receptor_candidates.csv", candidates, cfields), (PROCESSED/"building_use_match_audit.csv", audit, afields)):
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fields, lineterminator="\n"); w.writeheader(); w.writerows({k:r.get(k,"") for k in fields} for r in rows)
    features = [{"type":"Feature", "id":r["building_id"], "properties":{k:v for k,v in r.items() if k!="geometry"}, "geometry":r["geometry"]} for r in buildings]
    (PROCESSED/"residential_buildings.geojson").write_text(json.dumps({"type":"FeatureCollection", "name":"OSM residential candidates; official use not verified", "crs":{"type":"name","properties":{"name":"EPSG:4326"}}, "features":features}, ensure_ascii=False, indent=2)+"\n")
    anchors = {"data_version":"official-address-anchors-v2", "official_construction_geometry_status":"null_unchanged", "coordinate_api_source":"https://business.juso.go.kr/addrlink/addrCoordApi.do", "anchors":[{"segment_id":"segment-yeonse-ro-2na-gil","address":ANCHORS["segment-yeonse-ro-2na-gil"]["address"],"parcel_address":"서울특별시 서대문구 창천동 13-68","official_building_id":"1014112097","official_primary_use":"숙박시설","official_coordinate":None,"exploratory_osm_address_building_coordinate":{"lat":ANCHORS["segment-yeonse-ro-2na-gil"]["lat"],"lon":ANCHORS["segment-yeonse-ro-2na-gil"]["lon"],"crs":"EPSG:4326"},"status":"official_juso_coordinate_deferred_missing_coordinate_key"},{"segment_id":"segment-chungjeong-ro","address":"서울특별시 서대문구 충정로 35-17","parcel_address":"서울특별시 서대문구 충정로3가 120-1","building_name":"충정로 제2빌딩","official_building_id":"101411159","official_primary_use":"제2종근린생활시설","official_coordinate":None,"status":"official_juso_coordinate_deferred_missing_coordinate_key"}]}
    (PROCESSED/"official_address_anchors.json").write_text(json.dumps(anchors,ensure_ascii=False,indent=2)+"\n")
    radius = {str(n):sum(float(r["address_anchor_distance_m"])<=n for r in candidates) for n in (100,200,300)}
    report={"data_version":"residential-receptor-verification-v2","source_license":"OpenStreetMap contributors, ODbL 1.0","raw_polygon_count":sum(x["downloaded_building_polygons"] for x in segment_stats.values()),"unique_osm_polygon_count":len(seen),"official_target_buildings_queried":2,"segments":segment_stats,"segment_a_address_anchor_counts_by_radius_m":radius,"segment_b_radius_counts_status":"deferred_missing_official_coordinate","official_residential_verified":0,"official_polygon_count":0,"osm_residential_candidates":len(buildings),"eligible_receptor_candidates":len(candidates),"official_non_residential_address_buildings_verified":2,"receptor_wall_points_verified":0,"official_construction_geometry_status":"null_unchanged","field_prediction_status":"deferred","validation_status":"not_evaluable","building_hub_diagnostic":{"http_status":200,"result_code":"00","authenticated":True,"queried_buildings":2,"secret_logged":False},"juso_search_status":"resolved_two_target_addresses","juso_coordinate_status":"deferred_missing_coordinate_key","seoul_recap_title":{"service":"aiVBigDjrRecapTitle","rows_scanned":19204,"exact_target_matches":0,"record_type":"총괄표제부"},"limitations":["JUSO_COORD_API_KEY is empty; the search key returned E0001 at the coordinate endpoint","OSM geometry is not an official building polygon","No fuzzy address join was accepted","Chungjeong search-area polygons have no official anchor distance","Building centroids are not facade receptors or construction source locations"]}
    (PROCESSED/"receptor_coverage_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    return report


if __name__ == "__main__":
    print(json.dumps(build(),ensure_ascii=False,indent=2))
