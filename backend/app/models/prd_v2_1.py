from __future__ import annotations

from datetime import date, time
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.domain import SourceMetadata, TimeWindow


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
    total_work_window: TimeWindow
    road_excavation: bool
    road_occupancy_permit_window: TimeWindow | None = None
    equipment_constraints: list[EquipmentPlanningConstraint] = Field(default_factory=list)
    fixed_tasks: list[FixedTaskConstraint] = Field(default_factory=list)
    same_day_restoration_required: bool = False
    project_completion_date: date | None = None
    non_adjustable_conditions: list[str] = Field(default_factory=list)
    source_evidence: dict[str, str] = Field(default_factory=dict)
    provenance: Literal["field_measured", "official_document", "user_provided", "assumed"]

    @model_validator(mode="after")
    def road_permit_required_only_from_input(self):
        if self.road_occupancy_permit_window is not None and not self.road_excavation:
            raise ValueError("road occupancy permit window requires road_excavation=true")
        return self
