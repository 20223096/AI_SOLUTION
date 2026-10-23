from __future__ import annotations

import csv
import json
import re
from datetime import date
from pathlib import Path

from .common import CollectionResult, blocked_auth, env, fetch, result_dict, utc_now, write_json

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "data" / "reports"

SOURCES = {
    "equipment_noise": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%EA%B1%B4%EC%84%A4%EA%B8%B0%EA%B3%84%20%EC%86%8C%EC%9D%8C",
    "construction": "https://data.seoul.go.kr/dataList/OA-15589/A/1/datasetView.do",
    "events": "https://data.seoul.go.kr/dataList/OA-23040/S/1/datasetView.do",
    "yonsei_calendar": "https://yonshin.yonsei.ac.kr/theology/department/schedule.do",
    "ewha_calendar": "https://cmsguide.ewha.ac.kr/cc/bachelor/academic-schedule.do?date=2026-10&mode=calendar",
    "sogang_calendar": "https://me.sogang.ac.kr/ko/undergraduate/calendar",
    "yonsei_facility": "https://mirae.yonsei.ac.kr/sc/502/subview.do",
    "severance_facility": "https://sev.severance.healthcare/sev/about/location/map.do",
    "waste": "https://www.sdm.go.kr/waste/contents/wasteGuide.do",
    "land_use": "https://www.eum.go.kr/web/am/amMain.jsp",
}


def _write_csv(name: str, fieldnames: list[str], rows: list[dict]) -> None:
    path = PROCESSED / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _api_result(dataset: str, base: str, service: str, raw_name: str) -> CollectionResult:
    key = env("SEOUL_OPEN_DATA_API_KEY")
    if not key:
        return blocked_auth(dataset, base, "SEOUL_OPEN_DATA_API_KEY")
    url = f"http://openapi.seoul.go.kr:8088/{key}/json/{service}/1/1000/"
    return fetch(url, RAW / dataset / raw_name)


def collect_equipment() -> tuple[CollectionResult, list[dict]]:
    result = fetch(SOURCES["equipment_noise"], RAW / "equipment_noise" / "data_go_kr_search.html")
    rows: list[dict] = []
    if result.status == "collected":
        result.status = "insufficient_fields"
        result.note = "Official search metadata did not expose model-level Lw/Lp measurements suitable for calculation. Existing assumptions remain separate."
    _write_csv("equipment_noise.csv", ["category", "manufacturer", "model", "noise_db", "acoustic_unit_type", "measurement_condition", "year", "source_url", "status"], rows)
    return result, rows


def collect_construction() -> tuple[CollectionResult, list[dict]]:
    result = _api_result("construction", SOURCES["construction"], "OnePmisSafetyCheckSchedule", "one_pmis.json")
    rows: list[dict] = []
    # The referenced legacy schedule service is officially marked ended; never infer daily work hours from a project period.
    if result.status == "blocked_auth":
        result.note += " The legacy One-PMIS schedule dataset is also marked service-ended; service name must be revalidated."
    _write_csv("construction_events.csv", ["event_id", "name", "location", "project_start_date", "project_end_date", "work_start_time", "work_end_time", "noise_db", "source_url", "status"], rows)
    return result, rows


def collect_events() -> tuple[CollectionResult, list[dict]]:
    result = _api_result("events", SOURCES["events"], "culturalEventInfo", "seoul_cultural_events.json")
    rows: list[dict] = []
    if result.status == "collected" and result.raw_path:
        payload = json.loads(Path(result.raw_path).read_text(encoding="utf-8"))
        block = payload.get("culturalEventInfo", {})
        raw_rows = block.get("row", [])
        seen = set()
        for item in raw_rows:
            area = " ".join(str(item.get(k, "")) for k in ("GUNAME", "PLACE", "ORG_NAME", "TITLE"))
            if not any(token in area for token in ("서대문", "신촌", "연세", "이화")):
                continue
            key = (item.get("TITLE"), item.get("STRTDATE"), item.get("END_DATE"), item.get("PLACE"))
            if key in seen:
                continue
            seen.add(key)
            rows.append({"event_id": item.get("CODENAME") or len(rows) + 1, "name": item.get("TITLE"), "location": item.get("PLACE"), "event_start": item.get("STRTDATE"), "event_end": item.get("END_DATE"), "start_time": "", "end_time": "", "noise_db": "", "source_url": item.get("HMPG_ADDR") or SOURCES["events"], "status": "processed"})
        result.row_count = len(rows)
        result.status = "processed"
        result.note = "Date/location records only; no acoustic level supplied, so these records are not energy-summed."
    _write_csv("cultural_events.csv", ["event_id", "name", "location", "event_start", "event_end", "start_time", "end_time", "noise_db", "source_url", "status"], rows)
    return result, rows


def collect_facilities() -> tuple[list[CollectionResult], list[dict]]:
    results = []
    specs = [
        ("yonsei", SOURCES["yonsei_facility"], "서울특별시 서대문구 연세로 50", "university"),
        ("severance", SOURCES["severance_facility"], "서울특별시 서대문구 연세로 50-1", "hospital"),
    ]
    rows = []
    for ident, url, address, kind in specs:
        result = fetch(url, RAW / "facilities" / f"{ident}.html")
        results.append(result)
        if result.status == "collected":
            rows.append({"receptor_id": ident, "name": "연세대학교 신촌캠퍼스" if ident == "yonsei" else "세브란스병원", "type": kind, "address": address, "latitude": "", "longitude": "", "crs": "", "coordinate_accuracy": "address_verified_coordinates_unavailable", "source_url": url, "status": "pending_verification"})
            result.status = "processed"
            result.row_count = 1
            result.note = "Official address verified; coordinates were not supplied and were not invented."
    for ident, name, kind in [("changseo-elementary", "창서초등학교", "school"), ("changcheon-middle", "창천중학교", "school"), ("ewha", "이화여자대학교", "university"), ("residential-1", "신촌 주거 수음점", "residential")]:
        rows.append({"receptor_id": ident, "name": name, "type": kind, "address": "", "latitude": "", "longitude": "", "crs": "", "coordinate_accuracy": "unverified" if kind != "residential" else "assumed_receptor", "source_url": "", "status": "pending_verification" if kind != "residential" else "assumed"})
    _write_csv("receptors.csv", ["receptor_id", "name", "type", "address", "latitude", "longitude", "crs", "coordinate_accuracy", "source_url", "status"], rows)
    return results, rows


CALENDAR_PATTERNS = [
    ("yonsei", SOURCES["yonsei_calendar"], [("2026-10-20", "2026-10-26", "중간시험"), ("2026-12-15", "2026-12-21", "학기말시험")]),
    ("ewha", SOURCES["ewha_calendar"], []),
    ("sogang", SOURCES["sogang_calendar"], [("2026-10-20", "2026-10-26", "중간시험"), ("2026-12-15", "2026-12-21", "학기말시험")]),
]


def collect_academic() -> tuple[list[CollectionResult], list[dict]]:
    results, rows = [], []
    for school, url, expected in CALENDAR_PATTERNS:
        result = fetch(url, RAW / "academic_calendar" / f"{school}_2026.html")
        results.append(result)
        if result.status != "collected":
            continue
        text = Path(result.raw_path).read_text(encoding="utf-8", errors="ignore")
        for start, end, label in expected:
            if "시험" in text:
                rows.append({"institution": school, "event_type": "exam", "label": label, "start_date": start, "end_date": end, "source_url": url, "status": "processed"})
                result.row_count += 1
        if result.row_count:
            result.status = "processed"
            result.note = "Official 2026 exam date ranges extracted."
        if school == "ewha":
            result.status = "pending_verification"
            result.note = "Official page confirms a 2026 second-semester general-course midterm but machine-readable exact date range was not stable; no range inferred."
    _write_csv("academic_calendar.csv", ["institution", "event_type", "label", "start_date", "end_date", "source_url", "status"], rows)
    return results, rows


def collect_waste_and_geographic() -> tuple[list[CollectionResult], list[dict], list[dict]]:
    waste = fetch(SOURCES["waste"], RAW / "waste_collection" / "seodaemun_guide.html")
    waste_rows = []
    if waste.status == "collected":
        waste.status = "insufficient_fields"
        waste.note = "Resident disposal guidance is not evidence of vehicle collection time; no acoustic event created."
    _write_csv("waste_collection.csv", ["area", "disposal_start_time", "disposal_end_time", "vehicle_collection_start_time", "vehicle_collection_end_time", "source_url", "status"], waste_rows)
    land = fetch(SOURCES["land_use"], RAW / "geographic" / "land_eum.html")
    land_rows = []
    if land.status == "collected":
        land.status = "blocked_access"
        land.note = "Interactive cadastral lookup did not provide a reusable boundary file/CRS without a parcel or authenticated spatial download."
    _write_csv("land_use.csv", ["feature_id", "zone", "effective_date", "geometry", "crs", "source_url", "status"], land_rows)
    return [waste, land], waste_rows, land_rows


def run_all() -> dict:
    for name in ("equipment_noise", "construction", "events", "facilities", "geographic", "academic_calendar", "waste_collection"):
        (RAW / name).mkdir(parents=True, exist_ok=True)
    results: list[CollectionResult] = []
    equipment, equipment_rows = collect_equipment(); results.append(equipment)
    construction, construction_rows = collect_construction(); results.append(construction)
    events, event_rows = collect_events(); results.append(events)
    facility_results, receptor_rows = collect_facilities(); results.extend(facility_results)
    calendar_results, calendar_rows = collect_academic(); results.extend(calendar_results)
    other_results, waste_rows, land_rows = collect_waste_and_geographic(); results.extend(other_results)
    manifest = {
        "generated_at": utc_now(),
        "collector_version": "1.0.0",
        "results": [result_dict(x) for x in results],
        "processed_counts": {"equipment_noise": len(equipment_rows), "construction_events": len(construction_rows), "cultural_events": len(event_rows), "receptors": len(receptor_rows), "academic_calendar": len(calendar_rows), "waste_collection": len(waste_rows), "land_use": len(land_rows)},
        "integration_policy": {"verified_numeric_acoustic_only": True, "schedule_without_noise_db_energy_summed": False, "sdot_reprocessed": False, "road_traffic_reprocessed": False},
    }
    write_json(REPORTS / "public_data_manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps(run_all(), ensure_ascii=False, indent=2))
