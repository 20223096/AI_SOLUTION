from __future__ import annotations

import csv
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from .common import load_project_env, write_json
from .data_go_kr import authentication_result, request_with_service_key

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORT = ROOT / "data" / "reports" / "data_go_kr_facility_auth.json"

SOURCES = {
    "school": {"dataset_id": "15021148", "url": "https://api.data.go.kr/openapi/tn_pubr_public_elesch_mskul_lc_api"},
    "hospital": {"dataset_id": "15001698", "url": "https://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList"},
    "building": {"dataset_id": "15134735", "url": "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"},
}


def _save(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(body); tmp.replace(path)


def _school_items(payload: dict) -> list[dict]:
    body = payload.get("body") or {}
    value = body.get("items", {}).get("item", []) if isinstance(body.get("items"), dict) else []
    return [value] if isinstance(value, dict) else value


def collect() -> dict:
    load_project_env(ROOT / ".env")
    key = os.environ.get("DATA_GO_KR_API_KEY", "")
    if not key:
        raise RuntimeError("DATA_GO_KR_API_KEY is missing")
    rows, results = [], []
    for name in ("서울창서초등학교", "창천중학교"):
        response = request_with_service_key(SOURCES["school"]["url"], key, {"pageNo": 1, "numOfRows": 10, "type": "json", "schoolNm": name}, timeout=60)
        payload = response.json(); header = payload.get("header", {})
        _save(RAW / "facilities" / f"school_{name}.json", response.content)
        items = _school_items(payload)
        results.append({"dataset_id": "15021148", "endpoint": SOURCES["school"]["url"], "query": {"schoolNm": name}, "http_status": response.status_code, "result_code": header.get("resultCode"), "result_message": header.get("resultMsg"), "approved": header.get("resultCode") in {"00", "03"}, "row_count": len(items)})
        for item in items:
            rows.append({"facility_id": item.get("schoolId"), "name": item.get("schoolNm"), "type": "school", "address": item.get("rdnmadr") or item.get("lnmadr"), "latitude": item.get("latitude"), "longitude": item.get("longitude"), "crs": "EPSG:4326", "reference_date": item.get("referenceDate"), "retrieved_at": datetime.now(timezone.utc).date().isoformat(), "source_dataset_id": "15021148", "source_url": "https://www.data.go.kr/data/15021148/standard.do", "status": "processed"})

    hospital = request_with_service_key(SOURCES["hospital"]["url"], key, {"pageNo": 1, "numOfRows": 10, "yadmNm": "세브란스병원"}, timeout=60)
    _save(RAW / "facilities" / "hospital_severance.xml", hospital.content)
    root = ET.fromstring(hospital.content); code = root.findtext(".//resultCode"); message = root.findtext(".//resultMsg")
    hospital_items = root.findall(".//item")
    results.append({"dataset_id": "15001698", "endpoint": SOURCES["hospital"]["url"], "query": {"yadmNm": "세브란스병원"}, "http_status": hospital.status_code, "result_code": code, "result_message": message, "approved": code == "00", "row_count": len(hospital_items)})
    for item in hospital_items:
        address = item.findtext("addr") or ""
        if "서대문구" not in address or "신촌동" not in address:
            continue
        rows.append({"facility_id": item.findtext("ykiho"), "name": item.findtext("yadmNm"), "type": "hospital", "address": address, "latitude": item.findtext("YPos"), "longitude": item.findtext("XPos"), "crs": "EPSG:4326", "reference_date": "", "retrieved_at": datetime.now(timezone.utc).date().isoformat(), "source_dataset_id": "15001698", "source_url": "https://www.data.go.kr/data/15001698/openapi.do", "status": "processed"})

    building = request_with_service_key(SOURCES["building"]["url"], key, {"sigunguCd": "11410", "bjdongCd": "11400", "platGbCd": "0", "bun": "0134", "ji": "0000", "numOfRows": 1, "pageNo": 1, "_type": "json"}, timeout=60)
    _save(RAW / "geographic" / "building_hub_auth_sample.json", building.content)
    auth = authentication_result(building)
    results.append({"dataset_id": "15134735", "endpoint": SOURCES["building"]["url"], "query": {"scope": "approval_check_sample", "sigunguCd": "11410", "bjdongCd": "11400"}, "http_status": auth.http_status, "result_code": auth.result_code, "result_message": auth.result_message, "approved": auth.authenticated, "row_count": 0, "integration": "not_used_for_receptor_location"})

    path = PROCESSED / "official_facilities.csv"; path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["facility_id", "name", "type", "address", "latitude", "longitude", "crs", "reference_date", "retrieved_at", "source_dataset_id", "source_url", "status"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
    report = {"checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "key_logged": False, "client_parameter_mode": "httpx.params", "results": results, "processed_facility_count": len(rows)}
    write_json(REPORT, report)
    return report


if __name__ == "__main__":
    collect()
