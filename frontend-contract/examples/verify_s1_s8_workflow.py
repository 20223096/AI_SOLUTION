"""Replay one connected S1 -> S8 workflow against a running local server."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from generate_examples import prd_integrated_payload

BASE_URL = os.getenv("SHH_API_BASE_URL", "http://127.0.0.1:8765")
OUT = Path(os.getenv("SHH_WORKFLOW_OUT", Path(__file__).with_name("s1-s8-workflow.json")))


def call(client: httpx.Client, step: str, method: str, path: str, body: dict | None = None) -> dict:
    response = client.request(method, path, json=body)
    response.raise_for_status()
    return {"step": step, "method": method, "path": path, "request": body, "status": response.status_code, "response": response.json()}


def main() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=120) as client:
        steps = []
        extraction = call(client, "S1_extract", "POST", "/api/notices/extract", {
            "text": "2026년 신촌 연세로 공사 07:00~18:00, 절단기, 브레이커, 굴착기, 롤러"
        })
        steps.append(extraction)
        extracted = extraction["response"]
        planning_draft = call(client, "S2_planning_draft", "POST", "/api/prd/planning/from-notice", {
            "notice": extracted["notice"], "extractor_mode": extracted["mode"],
            "is_actual_ai": extracted["is_actual_ai"], "field_evidence": extracted["field_evidence"],
        })
        steps.append(planning_draft)

        request = prd_integrated_payload()
        request["planning"]["total_work_window"] = {"start": "08:00", "end": "18:00"}
        for equipment in request["planning"]["equipment_constraints"]:
            equipment["permitted_time_windows"] = [{"start": "08:00", "end": "18:00"}]
        steps.append({
            "step": "S3_staff_completion", "mode": "manual_input", "missing_before": planning_draft["response"]["missing_fields"],
            "completed_planning": request["planning"],
        })
        coordinate = call(client, "S2_address_coordinate", "POST", "/api/locations/address-coordinate", {
            "address": "서울특별시 서대문구 연세로2나길 20"
        })
        steps.append(coordinate)

        original = [
            {"task_id": "cut", "start": "2026-09-11T07:00:00+09:00", "end": "2026-09-11T08:00:00+09:00"},
            {"task_id": "break", "start": "2026-09-11T08:00:00+09:00", "end": "2026-09-11T10:00:00+09:00"},
            {"task_id": "excavate", "start": "2026-09-11T10:00:00+09:00", "end": "2026-09-11T15:00:00+09:00"},
            {"task_id": "compact", "start": "2026-09-11T15:00:00+09:00", "end": "2026-09-11T16:00:00+09:00"},
        ]
        validation = call(client, "S3_constraint_validation", "POST", "/api/prd/schedules/validate", {**request, "assignments": original})
        steps.append(validation)
        recommendations = call(client, "S4_recommendations", "POST", "/api/prd/recommendations/constraint-filtered", request)
        steps.append(recommendations)
        result = recommendations["response"]
        selected_id = result["recommendable_candidate_ids"][0]
        selected = next(row for row in result["candidates"] if row["candidate_id"] == selected_id)
        steps.append({"step": "S5_schedule_selection", "selected_candidate_id": selected_id, "server_snapshot_id": selected["schedule_snapshot_id"]})
        comparison = call(client, "S6_schedule_comparison", "POST", "/api/schedules/compare", {
            "scenario_id": result["scenario_id"], "analysis_date": request["analysis_date"],
            "background_profile": "road_traffic_observed_profile", "before": result["original_schedule"]["assignments"], "after": selected["assignments"],
        })
        steps.append(comparison)

        task_names = {"cut": "콘크리트 절단", "break": "포장 깨기", "excavate": "터파기", "compact": "되메우기 및 다짐"}
        high_noise = {"cut", "break"}
        selected_schedule = {
            "schedule_id": selected["schedule_snapshot_id"], "schedule_version": selected["schedule_version"],
            "candidate_id": selected_id, "recommendation_source": "/api/prd/recommendations/constraint-filtered",
            "candidate_valid": True, "schedule_snapshot_id": selected["schedule_snapshot_id"],
            "assignments": [{
                "task_id": item["task_id"], "task_name": task_names[item["task_id"]], "start": item["start"], "end": item["end"],
                "high_noise": item["task_id"] in high_noise, "classification_source": "demo",
            } for item in selected["assignments"]],
        }
        project_id = request["planning"]["notice_id"]
        draft = call(client, "S7_notice_draft", "POST", "/api/staff/resident-notices/drafts", {
            "project_id": project_id, "project_name": request["planning"]["project_name"],
            "public_location": coordinate["response"]["normalized_official_address"], "construction_date": request["analysis_date"],
            "public_window_start": "2026-09-11T07:00:00+09:00", "public_window_end": "2026-09-11T18:00:00+09:00",
            "public_contact": "서대문구 공사안내 02-0000-0000", "schedule": selected_schedule,
            "provenance": [{"field": "schedule", "status": "demo", "source": "server recommendation snapshot", "note": "실제 현장 일정 아님"}],
            "data_classification": "demo",
        })
        steps.append(draft)
        draft_body = draft["response"]
        update = call(client, "S7_staff_edit", "PUT", f"/api/staff/resident-notices/drafts/{project_id}", {
            "expected_revision": draft_body["revision"], "project_name": draft_body["project_name"],
            "public_location": draft_body["public_location"], "public_contact": draft_body["public_contact"],
            "headline": "주민 공사 일정 안내", "body": draft_body["body"] + " 담당자가 내용을 확인했습니다.",
            "schedule": selected_schedule, "provenance": [{"field": "schedule", "status": "demo", "source": "server recommendation snapshot"}],
        })
        steps.append(update)
        before_publish = call(client, "S8_before_confirm", "GET", f"/api/public/construction/{project_id}/resident-notice")
        steps.append(before_publish)
        edited = update["response"]
        confirm = call(client, "S7_confirm", "POST", f"/api/staff/resident-notices/drafts/{project_id}/confirm", {
            "expected_revision": edited["revision"], "schedule_version": edited["schedule_version"],
        })
        steps.append(confirm)
        public = call(client, "S8_public_read", "GET", f"/api/public/construction/{project_id}/resident-notice")
        steps.append(public)

    OUT.write_text(json.dumps({
        "contract_version": "3.4", "workflow": "connected S1-S8 HTTP replay", "base_url": BASE_URL,
        "manual_steps": ["S3 staff completion", "high-noise classification", "public contact", "notice edit and confirm"],
        "selected_candidate_id": selected_id, "schedule_snapshot_status": draft["response"]["recommendation_snapshot_status"],
        "step_count": len(steps), "steps": steps,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"verified connected S1-S8 HTTP workflow; selected {selected_id}; wrote {OUT}")


if __name__ == "__main__":
    main()
