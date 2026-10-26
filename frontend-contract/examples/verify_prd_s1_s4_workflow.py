"""Replay the S1-S4 PRD workflow against a running local API."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from generate_examples import prd_integrated_payload


BASE_URL = os.getenv("SHH_API_BASE_URL", "http://127.0.0.1:8765")
OUT = Path(os.getenv("SHH_WORKFLOW_OUT", Path(__file__).with_name("prd-s1-s4-workflow.json")))


def call(client: httpx.Client, method: str, path: str, body: dict) -> dict:
    response = client.request(method, path, json=body)
    response.raise_for_status()
    return {"method": method, "path": path, "request": body, "status": response.status_code, "response": response.json()}


def main() -> None:
    client = httpx.Client(base_url=BASE_URL, timeout=120)
    steps = []
    extraction = call(client, "POST", "/api/notices/extract", {
        "text": "2026년 신촌 연세로 공사 07:00~18:00, 절단기, 브레이커, 굴착기, 롤러"
    })
    steps.append({"step": 1, "screen": "S1", **extraction})
    extracted = extraction["response"]
    draft = call(client, "POST", "/api/prd/planning/from-notice", {
        "notice": extracted["notice"], "extractor_mode": extracted["mode"],
        "is_actual_ai": extracted["is_actual_ai"], "field_evidence": extracted["field_evidence"],
    })
    steps.append({"step": 2, "screen": "S2", **draft})

    request = prd_integrated_payload()
    request["planning"]["total_work_window"] = {"start": "08:00", "end": "18:00"}
    for equipment in request["planning"]["equipment_constraints"]:
        equipment["permitted_time_windows"] = [{"start": "08:00", "end": "18:00"}]
    original = [
        {"task_id": "cut", "start": "2026-09-11T07:00:00+09:00", "end": "2026-09-11T08:00:00+09:00"},
        {"task_id": "break", "start": "2026-09-11T08:00:00+09:00", "end": "2026-09-11T10:00:00+09:00"},
        {"task_id": "excavate", "start": "2026-09-11T10:00:00+09:00", "end": "2026-09-11T15:00:00+09:00"},
        {"task_id": "compact", "start": "2026-09-11T15:00:00+09:00", "end": "2026-09-11T16:00:00+09:00"},
    ]
    validation = call(client, "POST", "/api/prd/schedules/validate", {**request, "assignments": original})
    steps.append({"step": 3, "screen": "S3", **validation})
    recommendations = call(client, "POST", "/api/prd/recommendations/constraint-filtered", request)
    steps.append({"step": 4, "screen": "S4", **recommendations})
    result = recommendations["response"]
    selected_id = result["recommendable_candidate_ids"][0]
    selected = next(row for row in result["candidates"] if row["candidate_id"] == selected_id)
    comparison = call(client, "POST", "/api/schedules/compare", {
        "scenario_id": result["scenario_id"], "analysis_date": request["analysis_date"],
        "background_profile": "road_traffic_observed_profile",
        "before": result["original_schedule"]["assignments"], "after": selected["assignments"],
    })
    steps.append({"step": 5, "screen": "S4", "selected_candidate_id": selected_id, **comparison})
    summary = {
        "base_url": BASE_URL,
        "workflow": "S1-S4 notice extraction, confirmation, validation, constrained recommendation, comparison",
        "step_count": len(steps),
        "recommendation_status": result["recommendation_status"],
        "recommendable_candidate_ids": result["recommendable_candidate_ids"],
        "prd_feasible_candidate_ids": [row["candidate_id"] for row in result["candidates"] if row["prd_feasible"]],
        "prd_infeasible_candidate_ids": [row["candidate_id"] for row in result["candidates"] if not row["prd_feasible"]],
        "simulation_status": result["simulation_status"],
        "steps": steps,
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"verified {len(steps)} S1-S4 HTTP steps; selected {selected_id}; wrote {OUT}")


if __name__ == "__main__":
    main()
