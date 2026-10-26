from __future__ import annotations

import hashlib
import json
import os
import threading
from functools import wraps
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from app.models.resident_notices import (
    NoiseLevelPolicy,
    NoiseLevelSlot,
    NoticeInterval,
    ResidentNoticeConfirmRequest,
    ResidentNoticeDraftCreateRequest,
    ResidentNoticeDraftResponse,
    ResidentNoticeDraftUpdateRequest,
    ResidentPublicNotice,
    ResidentPublicResponse,
    SelectedNoticeSchedule,
)
from app.services.recommendation_snapshots import RecommendationSnapshotRepository

QUIET_LIMITATION = "확정 일정에서 시끄러운 작업이 배정되지 않은 최장 연속 시간이며 실제 환경의 정숙이나 현장 소음 부재를 보장하지 않습니다."
NOISE_POLICY_BASIS = "확정 일정에서 high_noise=true인 작업과 겹치면 loud, 그 밖의 예정 작업과 겹치면 moderate, 예정 작업이 없으면 quiet. dB 또는 법정 기준이 아닙니다."


class NoticeWorkflowError(Exception):
    def __init__(self, status: str, message: str, http_status: int, missing_fields: list[str] | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.http_status = http_status
        self.missing_fields = missing_fields or []


class JsonNoticeRepository:
    """Small atomic JSON repository matching the project's existing JSON storage style."""

    _lock = threading.RLock()

    def __init__(self, path: Path):
        self.path = path

    def read(self) -> dict[str, Any]:
        with self._lock:
            if not self.path.exists():
                return {"schema_version": 1, "projects": {}}
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("schema_version") != 1 or not isinstance(data.get("projects"), dict):
                raise RuntimeError("unsupported resident notice store schema")
            return data

    def write(self, data: dict[str, Any]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, self.path)


def _synchronized(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self.repository._lock:
            return method(self, *args, **kwargs)
    return wrapped


def _fingerprint(schedule: SelectedNoticeSchedule) -> str:
    canonical = schedule.model_dump(mode="json")
    return hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _merged_intervals(assignments: list[dict[str, Any]], start: datetime, end: datetime, high_noise_only: bool = False) -> list[tuple[datetime, datetime]]:
    intervals = []
    for item in assignments:
        if high_noise_only and not item["high_noise"]:
            continue
        item_start, item_end = datetime.fromisoformat(item["start"]), datetime.fromisoformat(item["end"])
        if item_end > start and item_start < end:
            intervals.append((max(item_start, start), min(item_end, end)))
    merged: list[list[datetime]] = []
    for item_start, item_end in sorted(intervals):
        if merged and item_start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], item_end)
        else:
            merged.append([item_start, item_end])
    return [(item[0], item[1]) for item in merged]


def _complement(intervals: list[tuple[datetime, datetime]], start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    result, cursor = [], start
    for item_start, item_end in intervals:
        if cursor < item_start:
            result.append((cursor, item_start))
        cursor = max(cursor, item_end)
    if cursor < end:
        result.append((cursor, end))
    return result


def _serialized_intervals(intervals: list[tuple[datetime, datetime]]) -> list[dict[str, str]]:
    return [{"start": start.isoformat(), "end": end.isoformat()} for start, end in intervals]


def _missing(record: dict[str, Any]) -> list[str]:
    missing = []
    for field in ("project_name", "public_location", "public_contact", "headline", "body"):
        if not str(record.get(field) or "").strip():
            missing.append(field)
    schedule = record["schedule"]
    if not schedule.get("candidate_valid"):
        missing.append("valid_selected_schedule")
    if record.get("recommendation_snapshot_status") not in {"verified", "not_required"}:
        missing.append("verified_recommendation_snapshot")
    if not schedule.get("assignments"):
        missing.append("schedule.assignments")
    return missing


def _template(request: ResidentNoticeDraftCreateRequest) -> tuple[str, str]:
    headline = f"{request.construction_date.isoformat()} 공사 일정 안내" if request.project_name else ""
    if not request.project_name or not request.public_location or not request.public_contact:
        return headline, ""
    items = sorted(request.schedule.assignments, key=lambda item: item.start)
    work = ", ".join(f"{item.start:%H:%M}~{item.end:%H:%M} {item.task_name}" for item in items)
    noisy = ", ".join(f"{item.start:%H:%M}~{item.end:%H:%M}" for item in items if item.high_noise) or "없음"
    all_intervals = _merged_intervals([item.model_dump(mode="json") for item in items], request.public_window_start, request.public_window_end)
    no_work = _complement(all_intervals, request.public_window_start, request.public_window_end)
    no_work_text = ", ".join(f"{start:%H:%M}~{end:%H:%M}" for start, end in no_work) or "없음"
    body = (
        f"{request.public_location}에서 {request.project_name} 공사가 예정되어 있습니다. "
        f"예정 작업은 {work}입니다. 시끄러운 작업 예정 시간은 {noisy}이며, "
        f"공사가 예정되지 않은 시간은 {no_work_text}입니다. 문의: {request.public_contact}. "
        "일정은 현장 상황에 따라 달라질 수 있습니다."
    )
    return headline, body


def _draft_response(record: dict[str, Any], *, idempotent: bool = False) -> ResidentNoticeDraftResponse:
    schedule = record["schedule"]
    start, end = datetime.fromisoformat(record["public_window_start"]), datetime.fromisoformat(record["public_window_end"])
    all_intervals = _merged_intervals(schedule["assignments"], start, end)
    noisy = _merged_intervals(schedule["assignments"], start, end, high_noise_only=True)
    return ResidentNoticeDraftResponse.model_validate({
        "status": record["status"],
        "publication_status": "published" if record.get("publication") else "private",
        "project_id": record["project_id"],
        "project_name": record.get("project_name"),
        "public_location": record.get("public_location"),
        "construction_date": record["construction_date"],
        "public_window": {"start": start, "end": end},
        "public_contact": record.get("public_contact"),
        "schedule_id": schedule["schedule_id"],
        "schedule_version": schedule["schedule_version"],
        "schedule_fingerprint": record["schedule_fingerprint"],
        "candidate_id": schedule["candidate_id"],
        "candidate_valid": schedule["candidate_valid"],
        "recommendation_snapshot_status": record["recommendation_snapshot_status"],
        "schedule_summary": {
            "scheduled_work": schedule["assignments"],
            "noisy_work_intervals": _serialized_intervals(noisy),
            "no_scheduled_work_intervals": _serialized_intervals(_complement(all_intervals, start, end)),
        },
        "headline": record.get("headline", ""),
        "body": record.get("body", ""),
        "missing_fields": _missing(record),
        "provenance": record["provenance"],
        "data_classification": record["data_classification"],
        "revision": record["revision"],
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
        "confirmed_at": record.get("confirmed_at"),
        "publication_version": record.get("publication_version"),
        "previous_publication_invalidated": record.get("previous_publication_invalidated", False),
        "idempotent": idempotent,
    })


class ResidentNoticeService:
    def __init__(self, repository: JsonNoticeRepository, clock: Callable[[], datetime] | None = None, snapshot_repository: RecommendationSnapshotRepository | None = None):
        self.repository = repository
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.snapshot_repository = snapshot_repository

    def _snapshot_status(self, project_id: str, schedule: SelectedNoticeSchedule) -> str:
        if schedule.recommendation_source == "manual_confirmed_schedule":
            return "not_required"
        if self.snapshot_repository is None:
            return "missing"
        verified, reason = self.snapshot_repository.verify(
            schedule.schedule_snapshot_id, project_id, schedule.candidate_id, schedule.schedule_version, schedule.assignments,
        )
        if verified:
            return "verified"
        return "missing" if "required" in reason or "not found" in reason else "mismatch"

    @_synchronized
    def create(self, request: ResidentNoticeDraftCreateRequest) -> ResidentNoticeDraftResponse:
        data = self.repository.read()
        if request.project_id in data["projects"]:
            raise NoticeWorkflowError("invalid_state", "draft already exists; use update", 409)
        now = self.clock().isoformat()
        headline, body = _template(request)
        record = {
            **request.model_dump(mode="json", exclude={"schedule"}),
            "schedule": request.schedule.model_dump(mode="json"),
            "schedule_fingerprint": _fingerprint(request.schedule),
            "recommendation_snapshot_status": self._snapshot_status(request.project_id, request.schedule),
            "headline": headline,
            "body": body,
            "status": "draft",
            "revision": 1,
            "created_at": now,
            "updated_at": now,
            "confirmed_at": None,
            "publication_version": None,
            "publication": None,
            "publication_history": [],
            "previous_publication_invalidated": False,
        }
        data["projects"][request.project_id] = record
        self.repository.write(data)
        return _draft_response(record)

    @_synchronized
    def get_draft(self, project_id: str) -> ResidentNoticeDraftResponse:
        record = self.repository.read()["projects"].get(project_id)
        if not record:
            raise NoticeWorkflowError("not_found", "resident notice draft not found", 404)
        return _draft_response(record)

    @_synchronized
    def update(self, project_id: str, request: ResidentNoticeDraftUpdateRequest) -> ResidentNoticeDraftResponse:
        data = self.repository.read()
        record = data["projects"].get(project_id)
        if not record:
            raise NoticeWorkflowError("not_found", "resident notice draft not found", 404)
        if record["revision"] != request.expected_revision:
            raise NoticeWorkflowError("version_conflict", "draft revision does not match", 409)
        window_start, window_end = datetime.fromisoformat(record["public_window_start"]), datetime.fromisoformat(record["public_window_end"])
        if any(item.start.date().isoformat() != record["construction_date"] or item.start < window_start or item.end > window_end for item in request.schedule.assignments):
            raise NoticeWorkflowError("validation_failed", "updated schedule must fit the construction date and public window", 422)
        publication_invalidated = record.get("publication") is not None
        if publication_invalidated:
            record.setdefault("publication_history", []).append({
                "publication_version": record["publication_version"],
                "confirmed_at": record["confirmed_at"],
                "schedule_version": record["schedule"]["schedule_version"],
                "schedule_fingerprint": record["schedule_fingerprint"],
                "invalidated_at": self.clock().isoformat(),
                "reason": "draft_or_schedule_updated",
                "snapshot": record["publication"],
            })
        record.update({
            "project_name": request.project_name,
            "public_location": request.public_location,
            "public_contact": request.public_contact,
            "headline": request.headline.strip(),
            "body": request.body.strip(),
            "schedule": request.schedule.model_dump(mode="json"),
            "schedule_fingerprint": _fingerprint(request.schedule),
            "recommendation_snapshot_status": self._snapshot_status(project_id, request.schedule),
            "provenance": [item.model_dump(mode="json") for item in request.provenance],
            "status": "draft",
            "revision": record["revision"] + 1,
            "updated_at": self.clock().isoformat(),
            "confirmed_at": None,
            "publication": None,
            "previous_publication_invalidated": publication_invalidated,
        })
        data["projects"][project_id] = record
        self.repository.write(data)
        return _draft_response(record)

    @_synchronized
    def confirm(self, project_id: str, request: ResidentNoticeConfirmRequest) -> ResidentNoticeDraftResponse:
        data = self.repository.read()
        record = data["projects"].get(project_id)
        if not record:
            raise NoticeWorkflowError("not_found", "resident notice draft not found", 404)
        if record["revision"] != request.expected_revision:
            raise NoticeWorkflowError("version_conflict", "draft revision does not match", 409)
        if record["schedule"]["schedule_version"] != request.schedule_version:
            raise NoticeWorkflowError("version_conflict", "selected schedule version does not match", 409)
        if record.get("publication") and record["status"] == "confirmed":
            return _draft_response(record, idempotent=True)
        missing = _missing(record)
        if missing:
            raise NoticeWorkflowError("validation_failed", "required publication fields are missing", 422, missing)
        now = self.clock().isoformat()
        version = int(record.get("publication_version") or 0) + 1
        record.update({"status": "confirmed", "confirmed_at": now, "updated_at": now, "publication_version": version, "previous_publication_invalidated": False})
        record["publication"] = self._publication(record)
        data["projects"][project_id] = record
        self.repository.write(data)
        return _draft_response(record)

    def _publication(self, record: dict[str, Any]) -> dict[str, Any]:
        schedule = record["schedule"]
        start, end = datetime.fromisoformat(record["public_window_start"]), datetime.fromisoformat(record["public_window_end"])
        noisy = _merged_intervals(schedule["assignments"], start, end, high_noise_only=True)
        quiet = _complement(noisy, start, end)
        longest = max(quiet, key=lambda item: item[1] - item[0]) if quiet else None
        slots = []
        cursor = start
        while cursor < end:
            slot_end = min(cursor + timedelta(hours=1), end)
            overlaps = [item for item in schedule["assignments"] if datetime.fromisoformat(item["end"]) > cursor and datetime.fromisoformat(item["start"]) < slot_end]
            level = "loud" if any(item["high_noise"] for item in overlaps) else "moderate" if overlaps else "quiet"
            slots.append(NoiseLevelSlot(start=cursor, end=slot_end, level=level, label={"quiet": "조용", "moderate": "보통", "loud": "시끄러움"}[level]).model_dump(mode="json"))
            cursor = slot_end
        public = ResidentPublicNotice(
            today_schedule=[{"task_name": item["task_name"], "start": item["start"], "end": item["end"]} for item in schedule["assignments"]],
            noisy_work_intervals=_serialized_intervals(noisy),
            longest_quiet_interval=None if longest is None else NoticeInterval(start=longest[0], end=longest[1]),
            quiet_interval_limitation=QUIET_LIMITATION, confirmed_notice=f"{record['headline']}\n\n{record['body']}",
            public_contact=record["public_contact"], hourly_noise_levels=slots,
            noise_level_policy=NoiseLevelPolicy(basis=NOISE_POLICY_BASIS),
            publication_provenance={
                "publication_version": record["publication_version"], "confirmed_at": record["confirmed_at"],
                "schedule_version": schedule["schedule_version"], "data_classification": record["data_classification"],
            },
        )
        return public.model_dump(mode="json")

    @_synchronized
    def public_read(self, project_id: str) -> ResidentPublicResponse:
        record = self.repository.read()["projects"].get(project_id)
        if not record or record.get("status") != "confirmed" or not record.get("publication"):
            return ResidentPublicResponse(status="not_published", message="No confirmed resident notice is published")
        return ResidentPublicResponse(status="published", notice=ResidentPublicNotice.model_validate(record["publication"]))
