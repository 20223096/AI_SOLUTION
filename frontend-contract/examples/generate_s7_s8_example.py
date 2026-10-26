"""Generate the deterministic S7 -> S8 HTTP example without external services."""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.api import resident_notices as api  # noqa: E402
from app.main import app  # noqa: E402
from app.services.resident_notices import JsonNoticeRepository, ResidentNoticeService  # noqa: E402


CREATE = {
    "project_id": "sprint24-demo",
    "project_name": "연세로 하수관로 공사",
    "public_location": "서울특별시 서대문구 연세로2나길 20 인근",
    "construction_date": "2026-09-11",
    "public_window_start": "2026-09-11T07:00:00+09:00",
    "public_window_end": "2026-09-11T18:00:00+09:00",
    "public_contact": "서대문구 공사안내 02-0000-0000",
    "schedule": {
        "schedule_id": "schedule-sprint24-demo",
        "schedule_version": "schedule-sprint24-demo-v1",
        "candidate_id": "offset-60",
        "recommendation_source": "/api/prd/recommendations/constraint-filtered",
        "candidate_valid": True,
        "assignments": [
            {"task_id": "cut", "task_name": "콘크리트 절단", "start": "2026-09-11T08:00:00+09:00", "end": "2026-09-11T09:00:00+09:00", "high_noise": True, "classification_source": "demo"},
            {"task_id": "restore", "task_name": "포장 복구", "start": "2026-09-11T10:00:00+09:00", "end": "2026-09-11T11:00:00+09:00", "high_noise": False, "classification_source": "demo"},
        ],
    },
    "provenance": [{"field": "schedule", "status": "demo", "source": "Sprint 24 E2E fixture", "note": "실제 현장 일정 아님"}],
    "data_classification": "demo",
}


def capture(client: TestClient, method: str, path: str, body: dict | None = None) -> dict:
    response = client.request(method, path, json=body)
    return {"request": {"method": method, "path": path, "body": body}, "response": {"status": response.status_code, "body": response.json()}}


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        service = ResidentNoticeService(
            JsonNoticeRepository(Path(directory) / "notices.json"),
            clock=lambda: datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc),
        )
        api.notice_service = lambda: service
        client = TestClient(app)
        steps = [capture(client, "POST", "/api/staff/resident-notices/drafts", CREATE)]
        created = steps[-1]["response"]["body"]
        steps.append(capture(client, "GET", "/api/staff/resident-notices/drafts/sprint24-demo"))
        update = {
            "expected_revision": created["revision"],
            "project_name": created["project_name"],
            "public_location": created["public_location"],
            "public_contact": created["public_contact"],
            "headline": "수정된 주민 공사 안내",
            "body": "담당자가 확인한 일정입니다. 08:00~09:00에 시끄러운 작업이 예정되어 있습니다. 문의는 공개 문의처를 이용해 주세요.",
            "schedule": CREATE["schedule"],
            "provenance": CREATE["provenance"],
        }
        steps.append(capture(client, "PUT", "/api/staff/resident-notices/drafts/sprint24-demo", update))
        updated = steps[-1]["response"]["body"]
        steps.append(capture(client, "GET", "/api/public/construction/sprint24-demo/resident-notice"))
        steps.append(capture(client, "POST", "/api/staff/resident-notices/drafts/sprint24-demo/confirm", {
            "expected_revision": updated["revision"], "schedule_version": updated["schedule_version"],
        }))
        steps.append(capture(client, "GET", "/api/public/construction/sprint24-demo/resident-notice"))
    output = {"contract_version": "3.3", "classification": "demo", "steps": steps}
    (Path(__file__).with_name("s7-s8-resident-notice-workflow.json")).write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
