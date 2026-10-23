from __future__ import annotations

import csv
import hashlib
import json
import re
import ssl
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from .common import CollectionResult, blocked_auth, env, fetch, load_project_env, result_dict, utc_now, write_json

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "data" / "reports"

SOURCES = {
    "equipment_noise": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%EA%B1%B4%EC%84%A4%EA%B8%B0%EA%B3%84%20%EC%86%8C%EC%9D%8C",
    "construction": "https://data.seoul.go.kr/dataList/OA-15585/A/1/datasetView.do",
    "events": "https://data.seoul.go.kr/dataList/OA-15486/A/1/datasetView.do",
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


SEOUL_API_BASE = "http://openapi.seoul.go.kr:8088"
SINCHON_TERMS = ("신촌동", "창천동", "대현동", "신촌역", "연세로", "신촌", "연세대", "이화여대")


def _ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _seoul_page(key: str, response_type: str, service: str, start: int, end: int) -> bytes:
    url = f"{SEOUL_API_BASE}/{key}/{response_type}/{service}/{start}/{end}/"
    request = urllib.request.Request(url, headers={"User-Agent": "shh-schedule-poc/0.2 public-data-research"})
    with urllib.request.urlopen(request, timeout=60, context=_ssl_context()) as response:
        return response.read()


def _seoul_error(payload: bytes, response_type: str, service: str) -> tuple[str | None, str | None, int | None]:
    if response_type == "json":
        value = json.loads(payload)
        block = value.get(service)
        if not isinstance(block, dict):
            result = value.get("RESULT", {})
            return result.get("CODE"), result.get("MESSAGE"), None
        result = block.get("RESULT", {})
        return result.get("CODE"), result.get("MESSAGE"), block.get("list_total_count")
    root = ET.fromstring(payload)
    code = root.findtext("RESULT/CODE") or root.findtext("CODE")
    message = root.findtext("RESULT/MESSAGE") or root.findtext("MESSAGE")
    count = root.findtext("list_total_count")
    return code, message, int(count) if count and count.isdigit() else None


def _store_page(dataset: str, service: str, start: int, end: int, suffix: str, payload: bytes) -> Path:
    path = RAW / dataset / f"{service}_{start}_{end}.{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload); tmp.replace(path)
    return path


def _date8(value: str | None) -> str:
    text = (value or "").strip()
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10] if text else ""


def _date_time(value: str | None) -> tuple[str, str]:
    text = (value or "").strip()
    match = re.match(r"(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}))?", text)
    return (match.group(1), match.group(2) or "") if match else (text, "")


def _event_times(value: str | None) -> tuple[str, str]:
    text = (value or "").strip()
    times = re.findall(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)", text)
    values = [f"{int(h):02d}:{m}" for h, m in times]
    # Multiple daily schedules cannot be represented by one start/end pair.
    # Preserve the complete PRO_TIME text and leave normalized clocks empty.
    return (values[0], values[1]) if len(values) == 2 else ((values[0], "") if len(values) == 1 else ("", ""))


def collect_equipment() -> tuple[CollectionResult, list[dict]]:
    result = fetch(SOURCES["equipment_noise"], RAW / "equipment_noise" / "data_go_kr_search.html")
    rows: list[dict] = []
    if result.status == "collected":
        result.status = "insufficient_fields"
        result.note = "Official search metadata did not expose model-level Lw/Lp measurements suitable for calculation. Existing assumptions remain separate."
    _write_csv("equipment_noise.csv", ["category", "manufacturer", "model", "noise_db", "acoustic_unit_type", "measurement_condition", "year", "source_url", "status"], rows)
    return result, rows


def collect_construction() -> tuple[CollectionResult, list[dict]]:
    load_project_env(ROOT / ".env")
    key = env("SEOUL_OPEN_DATA_API_KEY")
    rows: list[dict] = []
    if not key:
        result = blocked_auth("construction", SOURCES["construction"], "SEOUL_OPEN_DATA_API_KEY")
    else:
        try:
            first = _seoul_page(key, "xml", "pmisPjtList", 1, 1000)
            code, message, total = _seoul_error(first, "xml", "pmisPjtList")
            if code != "INFO-000" or total is None:
                result = CollectionResult("construction", SOURCES["construction"], "source_unavailable", utc_now(), note=f"API {code or 'response_shape_error'}: {message or 'missing total count'}")
            else:
                pages, hashes = [], []
                for start in range(1, total + 1, 1000):
                    end = min(start + 999, total)
                    payload = first if start == 1 else _seoul_page(key, "xml", "pmisPjtList", start, end)
                    pages.append(_store_page("construction", "pmisPjtList", start, end, "xml", payload))
                    hashes.append(hashlib.sha256(payload).hexdigest())
                    for element in ET.fromstring(payload).findall("row"):
                        item = {child.tag: (child.text or "").strip() for child in element}
                        haystack = " ".join(item.get(field, "") for field in ("PJT_NAME", "OFFICE_ADDR", "PJT_SCALE", "GU_NAME"))
                        if not any(term in haystack for term in SINCHON_TERMS):
                            continue
                        rows.append({"event_id": item.get("PJT_CD"), "name": item.get("PJT_NAME"), "location": item.get("OFFICE_ADDR"), "district": item.get("GU_NAME"), "latitude": item.get("LAT"), "longitude": item.get("LNG"), "project_start_date": _date8(item.get("PJT_BGN1_DATE")), "project_end_date": _date8(item.get("PJT_COMPL_PREARR_DATE")), "work_start_time": "", "work_end_time": "", "noise_db": "", "source_url": SOURCES["construction"], "source_service": "pmisPjtList", "status": "processed"})
                result = CollectionResult("construction", SOURCES["construction"], "processed", utc_now(), str(RAW / "construction"), len(rows), f"API INFO-000; source_total_count={total}. Project dates are not daily work times; no acoustic level supplied.", hashlib.sha256("".join(hashes).encode()).hexdigest(), total, code, "pmisPjtList", "xml")
        except urllib.error.HTTPError as exc:
            result = CollectionResult("construction", SOURCES["construction"], "blocked_auth" if exc.code in {401, 403} else "source_unavailable", utc_now(), note=f"HTTP {exc.code}")
        except (ET.ParseError, json.JSONDecodeError) as exc:
            result = CollectionResult("construction", SOURCES["construction"], "source_unavailable", utc_now(), note=f"response_format_error: {type(exc).__name__}", service_name="pmisPjtList", response_type="xml")
        except (urllib.error.URLError, TimeoutError) as exc:
            result = CollectionResult("construction", SOURCES["construction"], "blocked_access", utc_now(), note=f"{type(exc).__name__}: response unavailable or invalid")
    _write_csv("construction_events.csv", ["event_id", "name", "location", "district", "latitude", "longitude", "project_start_date", "project_end_date", "work_start_time", "work_end_time", "noise_db", "source_url", "source_service", "status"], rows)
    return result, rows


def collect_events() -> tuple[CollectionResult, list[dict]]:
    load_project_env(ROOT / ".env")
    key = env("SEOUL_OPEN_DATA_API_KEY")
    rows: list[dict] = []
    if not key:
        result = blocked_auth("events", SOURCES["events"], "SEOUL_OPEN_DATA_API_KEY")
    else:
        try:
            first = _seoul_page(key, "json", "culturalEventInfo", 1, 1000)
            code, message, total = _seoul_error(first, "json", "culturalEventInfo")
            if code != "INFO-000" or total is None:
                result = CollectionResult("events", SOURCES["events"], "source_unavailable", utc_now(), note=f"API {code or 'response_shape_error'}: {message or 'missing total count'}")
            else:
                seen, hashes = set(), []
                for start in range(1, total + 1, 1000):
                    end = min(start + 999, total)
                    payload = first if start == 1 else _seoul_page(key, "json", "culturalEventInfo", start, end)
                    _store_page("events", "culturalEventInfo", start, end, "json", payload)
                    hashes.append(hashlib.sha256(payload).hexdigest())
                    for item in json.loads(payload).get("culturalEventInfo", {}).get("row", []):
                        area = " ".join(str(item.get(k, "")) for k in ("GUNAME", "PLACE", "ORG_NAME", "TITLE"))
                        if not (item.get("GUNAME") == "서대문구" and any(term in area for term in SINCHON_TERMS)):
                            continue
                        event_start, api_start_time = _date_time(item.get("STRTDATE")); event_end, api_end_time = _date_time(item.get("END_DATE"))
                        parsed_start, parsed_end = _event_times(item.get("PRO_TIME"))
                        identity = (item.get("TITLE"), event_start, event_end, item.get("PLACE"))
                        if identity in seen:
                            continue
                        seen.add(identity)
                        # STRTDATE/END_DATE commonly contain 00:00 as a date boundary,
                        # not an asserted performance time. Prefer PRO_TIME and do not
                        # turn midnight placeholders into actual event clocks.
                        api_start_time = "" if api_start_time == "00:00" else api_start_time
                        api_end_time = "" if api_end_time == "00:00" else api_end_time
                        rows.append({"event_id": item.get("HMPG_ADDR") or f"event-{len(rows)+1}", "name": item.get("TITLE"), "district": item.get("GUNAME"), "location": item.get("PLACE"), "event_start_date": event_start, "event_end_date": event_end, "start_time": parsed_start or api_start_time, "end_time": parsed_end or api_end_time, "time_text": item.get("PRO_TIME") or "", "latitude": item.get("LAT"), "longitude": item.get("LOT"), "noise_db": "", "source_url": item.get("HMPG_ADDR") or SOURCES["events"], "source_service": "culturalEventInfo", "status": "processed"})
                result = CollectionResult("events", SOURCES["events"], "processed", utc_now(), str(RAW / "events"), len(rows), f"API INFO-000; source_total_count={total}. PRO_TIME retained; only unambiguous clock tokens parsed. No acoustic level supplied.", hashlib.sha256("".join(hashes).encode()).hexdigest(), total, code, "culturalEventInfo", "json")
        except urllib.error.HTTPError as exc:
            result = CollectionResult("events", SOURCES["events"], "blocked_auth" if exc.code in {401, 403} else "source_unavailable", utc_now(), note=f"HTTP {exc.code}")
        except (ET.ParseError, json.JSONDecodeError) as exc:
            result = CollectionResult("events", SOURCES["events"], "source_unavailable", utc_now(), note=f"response_format_error: {type(exc).__name__}", service_name="culturalEventInfo", response_type="json")
        except (urllib.error.URLError, TimeoutError) as exc:
            result = CollectionResult("events", SOURCES["events"], "blocked_access", utc_now(), note=f"{type(exc).__name__}: response unavailable or invalid")
    _write_csv("cultural_events.csv", ["event_id", "name", "district", "location", "event_start_date", "event_end_date", "start_time", "end_time", "time_text", "latitude", "longitude", "noise_db", "source_url", "source_service", "status"], rows)
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
