from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class PublicSource(BaseModel):
    field: str
    status: Literal["official_document", "user_confirmed", "derived", "assumed", "demo"]
    source: str
    note: str | None = None


class NoticeScheduleItem(BaseModel):
    task_id: str = Field(min_length=1, max_length=100)
    task_name: str = Field(min_length=1, max_length=200)
    start: datetime
    end: datetime
    high_noise: bool
    classification_source: Literal["user_confirmed", "official_document", "assumed", "demo"]

    @model_validator(mode="after")
    def ordered_and_zoned(self):
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("schedule item datetimes must include a timezone offset")
        if self.end <= self.start:
            raise ValueError("schedule item end must be after start")
        return self


class SelectedNoticeSchedule(BaseModel):
    schedule_id: str = Field(min_length=1, max_length=100)
    schedule_version: str = Field(min_length=1, max_length=100)
    candidate_id: str = Field(min_length=1, max_length=100)
    recommendation_source: Literal[
        "/api/prd/recommendations/constraint-filtered",
        "/api/schedules/optimize",
        "manual_confirmed_schedule",
    ]
    candidate_valid: bool
    assignments: list[NoticeScheduleItem] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_tasks(self):
        ids = [item.task_id for item in self.assignments]
        if len(ids) != len(set(ids)):
            raise ValueError("schedule task_id values must be unique")
        return self


class ResidentNoticeDraftCreateRequest(BaseModel):
    project_id: str = Field(min_length=1, max_length=100)
    project_name: str | None = Field(default=None, max_length=200)
    public_location: str | None = Field(default=None, max_length=300)
    construction_date: date
    public_window_start: datetime
    public_window_end: datetime
    public_contact: str | None = Field(default=None, max_length=200)
    schedule: SelectedNoticeSchedule
    provenance: list[PublicSource] = Field(min_length=1)
    data_classification: Literal["actual", "demo"]

    @model_validator(mode="after")
    def consistent_window(self):
        if self.public_window_start.tzinfo is None or self.public_window_end.tzinfo is None:
            raise ValueError("public window datetimes must include a timezone offset")
        if self.public_window_end <= self.public_window_start:
            raise ValueError("public_window_end must be after public_window_start")
        if self.public_window_start.date() != self.construction_date:
            raise ValueError("public window must start on construction_date")
        for item in self.schedule.assignments:
            if item.start.date() != self.construction_date or item.start < self.public_window_start or item.end > self.public_window_end:
                raise ValueError("schedule assignments must fit the construction date and public window")
        return self


class ResidentNoticeDraftUpdateRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    project_name: str | None = Field(default=None, max_length=200)
    public_location: str | None = Field(default=None, max_length=300)
    public_contact: str | None = Field(default=None, max_length=200)
    headline: str = Field(max_length=300)
    body: str = Field(max_length=5000)
    schedule: SelectedNoticeSchedule
    provenance: list[PublicSource] = Field(min_length=1)


class ResidentNoticeConfirmRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    schedule_version: str = Field(min_length=1, max_length=100)


class NoticeInterval(BaseModel):
    start: datetime
    end: datetime


class DraftScheduleSummary(BaseModel):
    scheduled_work: list[NoticeScheduleItem]
    noisy_work_intervals: list[NoticeInterval]
    no_scheduled_work_intervals: list[NoticeInterval]


class ResidentNoticeDraftResponse(BaseModel):
    status: Literal["draft", "confirmed"]
    publication_status: Literal["private", "published"]
    project_id: str
    project_name: str | None
    public_location: str | None
    construction_date: date
    public_window: NoticeInterval
    public_contact: str | None
    schedule_id: str
    schedule_version: str
    schedule_fingerprint: str
    candidate_id: str
    candidate_valid: bool
    schedule_summary: DraftScheduleSummary
    headline: str
    body: str
    missing_fields: list[str]
    provenance: list[PublicSource]
    data_classification: Literal["actual", "demo"]
    revision: int
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None = None
    publication_version: int | None = None
    previous_publication_invalidated: bool = False
    idempotent: bool = False


class NoticeErrorResponse(BaseModel):
    status: Literal["not_found", "forbidden", "invalid_state", "version_conflict", "validation_failed"]
    message: str
    missing_fields: list[str] = Field(default_factory=list)


class NoiseLevelSlot(BaseModel):
    start: datetime
    end: datetime
    level: Literal["quiet", "moderate", "loud"]
    label: Literal["조용", "보통", "시끄러움"]


class NoiseLevelPolicy(BaseModel):
    version: Literal["schedule_activity_v1"] = "schedule_activity_v1"
    basis: str
    provenance: Literal["derived_from_confirmed_schedule"] = "derived_from_confirmed_schedule"
    measurement_validated: Literal[False] = False


class PublicScheduleItem(BaseModel):
    task_name: str
    start: datetime
    end: datetime


class PublicationProvenance(BaseModel):
    publication_version: int
    confirmed_at: datetime
    schedule_version: str
    data_classification: Literal["actual", "demo"]


class ResidentPublicNotice(BaseModel):
    today_schedule: list[PublicScheduleItem]
    noisy_work_intervals: list[NoticeInterval]
    longest_quiet_interval: NoticeInterval | None
    quiet_interval_limitation: str
    confirmed_notice: str
    public_contact: str
    hourly_noise_levels: list[NoiseLevelSlot]
    noise_level_policy: NoiseLevelPolicy
    publication_provenance: PublicationProvenance


class ResidentPublicResponse(BaseModel):
    status: Literal["published", "not_published"]
    notice: ResidentPublicNotice | None = None
    message: str | None = None
