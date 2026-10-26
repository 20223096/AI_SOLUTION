from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import resident_notices as api
from app.main import app
from app.models.resident_notices import (
    ResidentNoticeConfirmRequest,
    ResidentNoticeDraftCreateRequest,
    ResidentNoticeDraftUpdateRequest,
)
from app.services.resident_notices import JsonNoticeRepository, NoticeWorkflowError, ResidentNoticeService


def payload(project_id="project-a"):
    return {
        "project_id": project_id,
        "project_name": "연세로 하수관로 공사",
        "public_location": "서울특별시 서대문구 연세로2나길 20 인근",
        "construction_date": "2026-09-11",
        "public_window_start": "2026-09-11T07:00:00+09:00",
        "public_window_end": "2026-09-11T18:00:00+09:00",
        "public_contact": "서대문구 공사안내 02-0000-0000",
        "schedule": {
            "schedule_id": "schedule-a",
            "schedule_version": "schedule-a-v1",
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


def service(tmp_path):
    fixed = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
    return ResidentNoticeService(JsonNoticeRepository(tmp_path / "notices.json"), clock=lambda: fixed)


def create(svc, value=None):
    return svc.create(ResidentNoticeDraftCreateRequest.model_validate(value or payload()))


def confirm(svc, draft):
    return svc.confirm(draft.project_id, ResidentNoticeConfirmRequest(expected_revision=draft.revision, schedule_version=draft.schedule_version))


def test_deterministic_draft_generation_is_private_and_has_explicit_schedule(tmp_path):
    draft = create(service(tmp_path))
    assert draft.status == "draft" and draft.publication_status == "private"
    assert draft.schedule_id == "schedule-a" and draft.schedule_version == "schedule-a-v1"
    assert "08:00~09:00" in draft.body and "문의" in draft.body
    assert draft.missing_fields == []
    assert draft.schedule_summary.no_scheduled_work_intervals[0].start.hour == 7


def test_unconfirmed_draft_is_never_returned_to_resident(tmp_path):
    svc = service(tmp_path)
    create(svc)
    public = svc.public_read("project-a")
    assert public.status == "not_published" and public.notice is None


def test_update_revision_and_schedule_version_validation(tmp_path):
    svc = service(tmp_path)
    draft = create(svc)
    request = ResidentNoticeDraftUpdateRequest(
        expected_revision=1, project_name=draft.project_name, public_location=draft.public_location,
        public_contact=draft.public_contact, headline="수정된 안내", body="담당자가 수정한 주민 안내 본문",
        schedule=payload()["schedule"], provenance=payload()["provenance"],
    )
    updated = svc.update("project-a", request)
    assert updated.revision == 2 and updated.headline == "수정된 안내" and updated.status == "draft"
    try:
        svc.update("project-a", request)
        assert False, "stale revision must fail"
    except NoticeWorkflowError as exc:
        assert exc.status == "version_conflict"


def test_confirm_publishes_and_duplicate_confirm_is_idempotent(tmp_path):
    svc = service(tmp_path)
    draft = create(svc)
    first = confirm(svc, draft)
    second = confirm(svc, first)
    assert first.status == "confirmed" and first.publication_status == "published"
    assert first.publication_version == 1 and first.confirmed_at is not None
    assert second.idempotent and second.publication_version == 1
    public = svc.public_read("project-a")
    assert public.status == "published" and public.notice.confirmed_notice.startswith(draft.headline)


def test_missing_fields_and_invalid_candidate_block_confirmation(tmp_path):
    value = payload()
    value["project_name"] = None
    value["public_contact"] = None
    value["schedule"]["candidate_valid"] = False
    svc = service(tmp_path)
    draft = create(svc, value)
    assert {"project_name", "public_contact", "body", "valid_selected_schedule"} <= set(draft.missing_fields)
    try:
        confirm(svc, draft)
        assert False, "incomplete draft must fail"
    except NoticeWorkflowError as exc:
        assert exc.status == "validation_failed" and "public_contact" in exc.missing_fields


def test_schedule_or_notice_change_unpublishes_previous_snapshot(tmp_path):
    svc = service(tmp_path)
    confirmed = confirm(svc, create(svc))
    changed = payload()["schedule"]
    changed["schedule_version"] = "schedule-a-v2"
    changed["assignments"][0]["start"] = "2026-09-11T09:00:00+09:00"
    changed["assignments"][0]["end"] = "2026-09-11T10:00:00+09:00"
    updated = svc.update("project-a", ResidentNoticeDraftUpdateRequest(
        expected_revision=confirmed.revision, project_name=confirmed.project_name,
        public_location=confirmed.public_location, public_contact=confirmed.public_contact,
        headline=confirmed.headline, body=confirmed.body, schedule=changed, provenance=payload()["provenance"],
    ))
    assert updated.status == "draft" and updated.previous_publication_invalidated
    assert svc.public_read("project-a").status == "not_published"
    stored = svc.repository.read()["projects"]["project-a"]
    assert stored["publication_history"][0]["publication_version"] == 1
    assert stored["publication_history"][0]["confirmed_at"] is not None
    try:
        svc.confirm("project-a", ResidentNoticeConfirmRequest(expected_revision=updated.revision, schedule_version="schedule-a-v1"))
        assert False, "old schedule version must fail"
    except NoticeWorkflowError as exc:
        assert exc.status == "version_conflict"


def test_persistence_after_service_restart_and_project_isolation(tmp_path):
    path = tmp_path / "notices.json"
    first = ResidentNoticeService(JsonNoticeRepository(path))
    confirm(first, create(first))
    create(first, payload("project-b"))
    restarted = ResidentNoticeService(JsonNoticeRepository(path))
    assert restarted.public_read("project-a").status == "published"
    assert restarted.public_read("project-b").status == "not_published"
    assert restarted.public_read("missing").status == "not_published"


def test_quiet_interval_and_schedule_based_three_level_classification(tmp_path):
    svc = service(tmp_path)
    public = svc.public_read("project-a")
    assert public.status == "not_published"
    confirm(svc, create(svc))
    notice = svc.public_read("project-a").notice
    assert notice.longest_quiet_interval.start.hour == 9
    assert notice.longest_quiet_interval.end.hour == 18
    levels = {slot.start.hour: slot.level for slot in notice.hourly_noise_levels}
    assert levels[7] == "quiet" and levels[8] == "loud" and levels[10] == "moderate"
    assert notice.noise_level_policy.measurement_validated is False
    assert "dB" in notice.noise_level_policy.basis
    assert "보장하지" in notice.quiet_interval_limitation


def test_public_dto_has_no_sensitive_or_internal_fields(tmp_path):
    svc = service(tmp_path)
    confirm(svc, create(svc))
    serialized = svc.public_read("project-a").model_dump(mode="json")
    def keys(value):
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value)) if value else set()
        return set()
    public_keys = {item.lower() for item in keys(serialized)}
    for forbidden in ("predicted_db", "noise_impact", "sensitivity", "receptor", "constraint_violations", "internal_notes", "original_notice", "schedule_fingerprint"):
        assert forbidden not in public_keys


def test_invalid_create_transition_is_rejected(tmp_path):
    svc = service(tmp_path)
    create(svc)
    try:
        create(svc)
        assert False, "duplicate create must fail"
    except NoticeWorkflowError as exc:
        assert exc.status == "invalid_state"


def test_s7_to_s8_http_e2e_and_cors(tmp_path, monkeypatch):
    svc = service(tmp_path)
    monkeypatch.setattr(api, "notice_service", lambda: svc)
    client = TestClient(app)
    draft_response = client.post("/api/staff/resident-notices/drafts", json=payload())
    assert draft_response.status_code == 200 and draft_response.json()["publication_status"] == "private"
    assert client.get("/api/public/construction/project-a/resident-notice").json()["status"] == "not_published"
    revision = draft_response.json()["revision"]
    confirmed = client.post("/api/staff/resident-notices/drafts/project-a/confirm", json={"expected_revision": revision, "schedule_version": "schedule-a-v1"})
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "confirmed"
    resident = client.get("/api/public/construction/project-a/resident-notice")
    assert resident.status_code == 200 and resident.json()["status"] == "published"
    preflight = client.options("/api/public/construction/project-a/resident-notice", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "accept"})
    assert preflight.status_code == 200


def test_staff_api_rejects_non_allowed_client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "notice_service", lambda: service(tmp_path))
    remote = TestClient(app, client=("203.0.113.10", 50000))
    response = remote.post("/api/staff/resident-notices/drafts", json=payload())
    assert response.status_code == 403 and response.json()["status"] == "forbidden"


def test_openapi_has_five_typed_endpoints_and_total_33_operations():
    schema = app.openapi()
    paths = schema["paths"]
    expected = {
        "/api/staff/resident-notices/drafts",
        "/api/staff/resident-notices/drafts/{project_id}",
        "/api/staff/resident-notices/drafts/{project_id}/confirm",
        "/api/public/construction/{project_id}/resident-notice",
    }
    assert expected <= set(paths)
    operations = sum(method in {"get", "post", "put", "patch", "delete"} for path in paths.values() for method in path)
    assert operations == 33
    assert "ResidentPublicResponse" in schema["components"]["schemas"]
    declaration = (Path(__file__).parents[2] / "frontend-contract" / "types" / "api.d.ts").read_text(encoding="utf-8")
    for token in ('"/api/staff/resident-notices/drafts"', '"/api/public/construction/{project_id}/resident-notice"', "ResidentPublicResponse"):
        assert token in declaration
