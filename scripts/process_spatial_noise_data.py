from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.collect_public_data.validation import geodesic_distance_m, validate_acoustic_unit

PROCESSED = ROOT / "data" / "processed"
RAW_EQUIPMENT = ROOT / "data" / "raw" / "equipment_noise" / "official_20260420"
SOURCE_URL = "https://www.data.go.kr/data/3038414/fileData.do"


def write_distances() -> None:
    project = (37.5569842, 126.9384049)
    with (PROCESSED / "official_facilities.csv").open(encoding="utf-8-sig", newline="") as handle:
        facilities = list(csv.DictReader(handle))
    selected = {"서울창서초등학교", "창천중학교", "연세대학교의과대학세브란스병원"}
    fields = ["project_id", "project_name", "project_location_text", "project_latitude", "project_longitude", "project_coordinate_source", "project_geometry_type", "receptor_id", "receptor_name", "receptor_type", "receptor_address", "receptor_latitude", "receptor_longitude", "receptor_coordinate_source", "crs", "distance_m", "distance_method", "status", "limitation"]
    rows = []
    for row in facilities:
        if row["name"] not in selected:
            continue
        distance = geodesic_distance_m(*project, float(row["latitude"]), float(row["longitude"]))
        rows.append({
            "project_id": "6132026083144", "project_name": "연세로2나길 20 일대 외 1개소 하수관로 개량공사",
            "project_location_text": "연세로2나길 20 일대 외 1개소", "project_latitude": project[0], "project_longitude": project[1],
            "project_coordinate_source": "Seoul Open Data pmisPjtList LAT/LNG", "project_geometry_type": "official_representative_point",
            "receptor_id": row["facility_id"], "receptor_name": row["name"], "receptor_type": row["type"], "receptor_address": row["address"],
            "receptor_latitude": row["latitude"], "receptor_longitude": row["longitude"], "receptor_coordinate_source": row["source_url"], "crs": "EPSG:4326",
            "distance_m": f"{distance:.1f}", "distance_method": "WGS84 haversine point-to-point", "status": "verified_public_coordinates",
            "limitation": "Horizontal straight-line distance between representative points; not facade receptor, route, terrain-aware, or acoustic propagation distance.",
        })
    with (PROCESSED / "receptor_distances.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def write_equipment() -> None:
    mapping = {"콘크리트절단기.csv": "콘크리트 절단기", "브레이커.csv": "브레이커", "굴착기.csv": "굴착기", "다짐기계.csv": "롤러/다짐기계"}
    fields = ["equipment_category", "manufacturer", "approval_number", "model_name", "noise_db", "acoustic_unit_type", "measurement_condition", "source_period", "source_url", "status"]
    rows = []
    for filename, category in mapping.items():
        path = RAW_EQUIPMENT / filename
        if not path.exists():
            continue
        with path.open(encoding="cp949", newline="") as handle:
            for row in csv.DictReader(handle):
                value = row.get("음향파워레벨(dBA)", "").strip()
                if not value:
                    continue
                float(value)
                rows.append({"equipment_category": category, "manufacturer": row.get("제작회사", "").strip(), "approval_number": row.get("승인번호", "").strip(), "model_name": row.get("모델명", "").strip(), "noise_db": value, "acoustic_unit_type": validate_acoustic_unit("Lw_dBA"), "measurement_condition": "Statutory construction-machinery noise inspection; row does not state operating mode or measurement geometry", "source_period": "2008-01 to 2025-07", "source_url": SOURCE_URL, "status": "verified_public_model_record"})
    with (PROCESSED / "official_equipment_noise.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


if __name__ == "__main__":
    write_distances()
    write_equipment()
