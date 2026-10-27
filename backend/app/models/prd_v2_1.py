from __future__ import annotations

from datetime import date, time
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.domain import ConstructionNotice, ConstructionPeriod, SourceMetadata, TaskAssignment, TimeWindow


class EquipmentPlanningConstraint(BaseModel):
    equipment_id: str
    category: str
    specification: str | None = None
    model_name: str | None = None
    max_daily_count: int | None = Field(default=None, ge=1)
    required_usage_minutes: int = Field(gt=0)
    permitted_time_windows: list[TimeWindow] = Field(default_factory=list)
    source_metadata: SourceMetadata


class FixedTaskConstraint(BaseModel):
    task_id: str
    fixed_start: time | None = None
    fixed_end: time | None = None
    reason: str
    source_metadata: SourceMetadata

    @model_validator(mode="after")
    def ordered(self):
        if self.fixed_start is not None and self.fixed_end is not None and self.fixed_end <= self.fixed_start:
            raise ValueError("fixed_end must be after fixed_start")
        return self


class PRDNoticePlanningInput(BaseModel):
    notice_id: str
    project_name: str
    location: str
    construction_period: ConstructionPeriod
    total_work_window: TimeWindow
    road_excavation: bool
    road_occupancy_permit_window: TimeWindow | None = None
    equipment_constraints: list[EquipmentPlanningConstraint] = Field(default_factory=list)
    fixed_tasks: list[FixedTaskConstraint] = Field(default_factory=list)
    same_day_restoration_required: bool = False
    project_completion_date: date | None = None
    non_adjustable_conditions: list[str] = Field(default_factory=list)
    source_evidence: dict[str, str] = Field(default_factory=dict)
    field_provenance: dict[str, SourceMetadata] = Field(default_factory=dict)
    provenance: Literal["field_measured", "official_document", "user_provided", "assumed"]

    @model_validator(mode="after")
    def road_permit_required_only_from_input(self):
        if self.road_occupancy_permit_window is not None and not self.road_excavation:
            raise ValueError("road occupancy permit window requires road_excavation=true")
        if (self.construction_period.start is None) != (self.construction_period.end is None):
            raise ValueError("construction_period start and end must be supplied together")
        if self.construction_period.start is not None and self.construction_period.end < self.construction_period.start:
            raise ValueError("construction_period end must not precede start")
        return self


class PRDScheduleValidationRequest(BaseModel):
    analysis_date: date
    planning: PRDNoticePlanningInput
    assignments: list[TaskAssignment]
    predecessors: dict[str, list[str]] = Field(default_factory=dict)
    equipment_by_task: dict[str, str | None] = Field(default_factory=dict)
    equipment_count_by_task: dict[str, int] = Field(default_factory=dict)
    task_duration_by_task: dict[str, int] = Field(default_factory=dict)
    restoration_task_ids: set[str] = Field(default_factory=set)

    @model_validator(mode="after")
    def validate_assignment_identity_and_time(self):
        task_ids = [item.task_id for item in self.assignments]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("assignments must contain unique task_id values")
        for item in self.assignments:
            if item.start.tzinfo is None or item.end.tzinfo is None:
                raise ValueError("assignment datetimes must include a timezone offset")
            if item.start.date() != self.analysis_date:
                raise ValueError("assignment start date must equal analysis_date")
        return self


class PRDSensitivityExperimentRequest(BaseModel):
    analysis_dates: list[date] = Field(default_factory=lambda: [date(2026, 9, 11), date(2026, 10, 7)], min_length=1)
    multipliers: list[Literal[1.1, 1.3, 1.5]] = Field(default_factory=lambda: [1.1, 1.3, 1.5], min_length=1)
    background_profile: str = "road_traffic_observed_profile"

    @model_validator(mode="after")
    def supported_demo_dates_only(self):
        supported = {date(2026, 9, 11), date(2026, 10, 7)}
        if not set(self.analysis_dates) <= supported:
            raise ValueError("analysis_dates must contain only 2026-09-11 or 2026-10-07")
        if len(self.analysis_dates) != len(set(self.analysis_dates)) or len(self.multipliers) != len(set(self.multipliers)):
            raise ValueError("analysis_dates and multipliers must not contain duplicates")
        return self


class PRDPlanningDraftRequest(BaseModel):
    notice: ConstructionNotice
    extractor_mode: Literal["mock", "llm", "manual"]
    is_actual_ai: bool
    field_evidence: dict[str, object] = Field(default_factory=dict)


class PRDConstraintRecommendationRequest(BaseModel):
    analysis_date: date
    planning: PRDNoticePlanningInput
    predecessors: dict[str, list[str]] = Field(default_factory=dict)
    equipment_by_task: dict[str, str | None] = Field(default_factory=dict)
    equipment_count_by_task: dict[str, int] = Field(default_factory=dict)
    task_duration_by_task: dict[str, int] = Field(default_factory=dict)
    restoration_task_ids: set[str] = Field(default_factory=set)
    background_profile: str = "road_traffic_observed_profile"
    objective_mode: Literal["incremental_impact", "absolute_impact", "physical_energy", "sensitive_exposure", "continuous_burden", "multi_axis"] = "incremental_impact"
    recommendation_engine: Literal["offset_v1", "cp_sat_v2"] = "offset_v1"

    @model_validator(mode="after")
    def supported_demo_dates_only(self):
        if self.analysis_date not in {date(2026, 9, 11), date(2026, 10, 7)}:
            raise ValueError("analysis_date must be 2026-09-11 or 2026-10-07")
        return self
