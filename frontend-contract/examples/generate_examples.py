"""Generate reproducible request/response captures against a running local API.

Run from the repository root while uvicorn serves backend/app/main.py:
    python3 frontend-contract/examples/generate_examples.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx


BASE_URL = os.getenv("SHH_API_BASE_URL", "http://127.0.0.1:8765")
OUT = Path(__file__).resolve().parent
START = "2026-10-26T07:00:00+09:00"
END = "2026-10-26T07:15:00+09:00"


def m1_payload(*, active_minutes: float = 15) -> dict[str, Any]:
    return {
        "slot_start": START,
        "slot_end": END,
        "background_laeq_db": 50,
        "background_provenance": "assumed",
        "overlap_mode": "complete_concurrent",
        "sources": [{
            "id": "excavator-a",
            "segment_id": "segment-yeonse-ro-2na-gil",
            "source_type": "moving_work",
            "equipment_category": "굴삭기",
            "count": 1,
            "sound_power_level_db": 100,
            "lw_provenance": "assumed",
            "position": {"x": 200000, "y": 550000, "z_m": 1, "crs": "EPSG:5186", "provenance": "assumed"},
            "deployment_start": START,
            "deployment_end": END,
            "actual_active_minutes": active_minutes,
            "activity_provenance": "assumed",
        }],
        "receptors": [{
            "id": "r1",
            "position": {"x": 200010, "y": 550000, "z_m": 1, "crs": "EPSG:5186", "provenance": "assumed"},
        }],
    }


def schedule_evaluation_payload() -> dict[str, Any]:
    categories = {
        "cut": ("moving_work", "콘크리트 절단기", 113),
        "break": ("impulsive", "브레이커", 122),
        "excavate": ("moving_work", "굴삭기", 100),
        "compact": ("moving_work", "롤러", 102),
    }
    mappings = [{
        "task_id": task_id,
        "segment_id": "segment-yeonse-ro-2na-gil",
        "source_type": source_type,
        "equipment_category": category,
        "sound_power_level_db": lw,
        "lw_provenance": "assumed",
        "position": {"x": 200000, "y": 550000, "z_m": 1, "crs": "EPSG:5186", "provenance": "assumed"},
        "active_ratio": 0.5,
        "activity_provenance": "assumed",
    } for task_id, (source_type, category, lw) in categories.items()]
    receptors = [{
        "id": receptor_id,
        "position": {"x": 200000 + distance, "y": 550000, "z_m": 1.5, "crs": "EPSG:5186", "provenance": "assumed"},
    } for receptor_id, distance in (("residential-1", 30), ("university-1", 50), ("school-1", 100))]
    return {
        "scenario_id": "case-a",
        "analysis_date": "2026-10-26",
        "background_profile": "assumed_demo",
        "receptors": receptors,
        "task_mappings": mappings,
        "overlap_mode": "overlap_unknown",
    }


def write_capture(name: str, request: dict[str, Any], response: httpx.Response) -> dict[str, Any]:
    try:
        body: Any = response.json()
    except ValueError:
        body = response.text
    record = {
        "request": request,
        "response": {
            "status": response.status_code,
            "headers": {"content-type": response.headers.get("content-type")},
            "body": body,
        },
    }
    (OUT / f"{name}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return record


def main() -> None:
    client = httpx.Client(base_url=BASE_URL, timeout=120)
    captures: list[tuple[str, str, str, dict[str, Any] | None]] = [
        ("01-health", "GET", "/api/health", None),
        ("02-scenarios", "GET", "/api/poc/scenarios", None),
        ("03-scenario-detail", "GET", "/api/poc/scenarios/case-a", None),
        ("04-notice-extract", "POST", "/api/notices/extract", {"text": "2026년 신촌 연세로 공사 07:00~18:00, 절단기, 브레이커, 굴착기, 롤러"}),
        ("06-noise-predict", "POST", "/api/noise/predict", {"scenario_id": "case-a", "analysis_date": "2026-10-26"}),
        ("07-background-profiles", "GET", "/api/noise/background-profiles", None),
        ("08-noise-predict-m1", "POST", "/api/noise/predict-m1", m1_payload()),
        ("09-noise-compare-m0-m1", "POST", "/api/noise/compare-m0-m1", m1_payload(active_minutes=7.5)),
        ("10-m1-uncertainty", "POST", "/api/noise/m1-uncertainty", {"cases": [
            {"id": "activity-50", "varied_variable": "activity_ratio", "request": m1_payload(active_minutes=7.5)},
            {"id": "activity-100", "varied_variable": "activity_ratio", "request": m1_payload(active_minutes=15)},
        ]}),
        ("11-evaluate-m1-candidates", "POST", "/api/noise/evaluate-m1-candidates", schedule_evaluation_payload()),
        ("12-validate-m1-field", "POST", "/api/noise/validate-m1-field", {"observations": [], "predictions": []}),
        ("13-design-simulation-catalog", "GET", "/api/noise/design-simulation/catalog", None),
        ("14-design-simulation-reschedule", "POST", "/api/noise/design-simulation/reschedule", {
            "segment_id": "segment-yeonse-ro-2na-gil", "receptor_id": "yeonse-sim-r1",
            "receptor_segment_id": "segment-yeonse-ro-2na-gil", "distance_m": 30,
        }),
        ("15-impact-calculate", "POST", "/api/impact/calculate", {
            "total_noise_db": 70, "baseline_noise_db": 60, "duration_minutes": 60,
            "continuous_minutes": 30, "sensitivity_weight": 1.5,
        }),
        ("16-schedule-optimize", "POST", "/api/schedules/optimize", {"scenario_id": "case-a", "analysis_date": "2026-10-26"}),
        ("18-optimization-diagnostics", "GET", "/api/schedules/optimize/case-a/diagnostics?analysis_date=2026-10-26", None),
        ("19-experiments-run", "POST", "/api/experiments/run", {"scenario_id": "case-a", "analysis_date": "2026-10-26"}),
        ("20-public-data-catalog", "GET", "/api/public-data/catalog", None),
        ("21-construction-design", "GET", "/api/public-data/construction-design", None),
    ]
    manifest: list[dict[str, Any]] = []
    for name, method, url, payload in captures:
        response = client.request(method, url, json=payload)
        request_record = {"method": method, "url": f"{BASE_URL}{url}", "headers": {"accept": "application/json"}}
        if payload is not None:
            request_record["headers"]["content-type"] = "application/json"
            request_record["body"] = payload
        record = write_capture(name, request_record, response)
        assert response.status_code == 200, (name, response.status_code, response.text)
        manifest.append({"name": name, "method": method, "path": url, "status": record["response"]["status"]})

    upload_response = client.post(
        "/api/notices/extract-file",
        files={"file": ("notice.txt", "신촌 공사, 시간 미정".encode(), "text/plain")},
    )
    upload_request = {
        "method": "POST", "url": f"{BASE_URL}/api/notices/extract-file",
        "headers": {"content-type": "multipart/form-data; boundary=<generated-by-client>"},
        "multipart": {"file": {"filename": "notice.txt", "content-type": "text/plain", "text": "신촌 공사, 시간 미정"}},
    }
    write_capture("05-notice-extract-file", upload_request, upload_response)
    assert upload_response.status_code == 200
    manifest.append({"name": "05-notice-extract-file", "method": "POST", "path": "/api/notices/extract-file", "status": 200})

    optimize = client.post("/api/schedules/optimize", json={"scenario_id": "case-a", "analysis_date": "2026-10-26"}).json()
    before = next(candidate for candidate in optimize["valid_candidates"] if candidate["id"] == "offset-0")["task_assignments"]
    after = optimize["recommended_options"][0]["candidate"]["task_assignments"]
    compare_payload = {"scenario_id": "case-a", "analysis_date": "2026-10-26", "before": before, "after": after}
    compare_response = client.post("/api/schedules/compare", json=compare_payload)
    compare_request = {
        "method": "POST", "url": f"{BASE_URL}/api/schedules/compare",
        "headers": {"accept": "application/json", "content-type": "application/json"}, "body": compare_payload,
    }
    write_capture("17-schedule-compare", compare_request, compare_response)
    assert compare_response.status_code == 200
    manifest.append({"name": "17-schedule-compare", "method": "POST", "path": "/api/schedules/compare", "status": 200})

    error_cases = [
        ("error-404-scenario", "POST", "/api/noise/predict", {"scenario_id": "missing"}, None, 404),
        ("error-422-validation", "POST", "/api/impact/calculate", {"total_noise_db": 70, "duration_minutes": -1, "continuous_minutes": 0, "sensitivity_weight": 1}, None, 422),
        ("error-422-domain", "POST", "/api/noise/predict", {"scenario_id": "case-a", "background_profile": "does-not-exist"}, None, 422),
        ("error-415-upload", "POST", "/api/notices/extract-file", None, {"file": ("notice.bin", b"abc", "application/octet-stream")}, 415),
    ]
    for name, method, url, payload, files, expected in error_cases:
        response = client.request(method, url, json=payload, files=files)
        request_record = {"method": method, "url": f"{BASE_URL}{url}", "headers": {}}
        if payload is not None:
            request_record["headers"]["content-type"] = "application/json"
            request_record["body"] = payload
        if files is not None:
            request_record["multipart"] = {"file": {"filename": files["file"][0], "content-type": files["file"][2]}}
        write_capture(name, request_record, response)
        assert response.status_code == expected, (name, response.status_code, response.text)

    manifest.sort(key=lambda row: row["path"])
    (OUT / "manifest.json").write_text(json.dumps({"base_url": BASE_URL, "success_count": len(manifest), "endpoints": manifest}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"captured {len(manifest)} successful endpoints and {len(error_cases)} error cases")


if __name__ == "__main__":
    main()
