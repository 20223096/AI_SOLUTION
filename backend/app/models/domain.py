from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ProvenanceStatus(str, Enum):
    verified_public = "verified_public"
    user_provided = "user_provided"
    assumed = "assumed"
    derived = "derived"
    missing = "missing"


class SourceMetadata(BaseModel):
    status: ProvenanceStatus
    source: str | None = None
    note: str | None = None
    unit: str | None = None


class TimeWindow(BaseModel):
    start: time
    end: time

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("end must be after start within one day")
        return self


class ConstructionPeriod(BaseModel):
    start: date | None = None
    end: date | None = None
    raw_text: str | None = None


class Equipment(BaseModel):
    id: str
    category: str
    model_name: str | None = None
    count: int = Field(ge=1)
    sound_power_level_db: float | None = None
    acoustic_unit_type: Literal["Lw_dBA", "Lp_dBA", "missing"]
    source_metadata: SourceMetadata


class ConstructionTask(BaseModel):
    id: str
    name: str
    equipment_id: str | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    permitted_time_windows: list[TimeWindow] = Field(default_factory=list)
    predecessors: list[str] = Field(default_factory=list)
    is_movable: bool = True
    required_resources: list[str] = Field(default_factory=list)


class ConstructionNotice(BaseModel):
    id: str
    name: str | None = None
    location: str | None = None
    construction_period: ConstructionPeriod
    original_work_window: TimeWindow | None = None
    tasks: list[ConstructionTask]
    constraints: dict[str, Any] = Field(default_factory=dict)
    source_provenance: dict[str, SourceMetadata]


class SensitivityProfile(BaseModel):
    receptor_id: str
    time_period: str
    base_weight: float = Field(gt=0)
    situational_adjustments: dict[str, float] = Field(default_factory=dict)
    calculation_notes: str


class Receptor(BaseModel):
    id: str
    name: str
    type: Literal["residential", "school", "hospital", "university", "commercial"]
    location: str
    distance_to_source_m: float = Field(gt=0)
    sensitivity_profile: list[SensitivityProfile] = Field(default_factory=list)
    noise_limit_profile: dict[str, Any] | None = None


class BackgroundNoise(BaseModel):
    receptor_id: str
    time_slot: datetime
    laeq_db: float
    source_metadata: SourceMetadata


class ExistingNoiseEvent(BaseModel):
    id: str
    category: Literal["construction", "event", "waste_collection"]
    location: str
    start: datetime
    end: datetime
    source_noise_data: dict[str, Any] | None = None
    is_fixed: bool = True
    provenance: SourceMetadata


class TaskAssignment(BaseModel):
    task_id: str
    start: datetime
    end: datetime


class ScheduleMetrics(BaseModel):
    max_continuous_high_noise_minutes: int = 0
    longest_quiet_window_minutes: int = 0
    sensitive_high_noise_minutes: int = 0
    max_impact_score: float = 0
    total_impact_score: float = 0
    absolute_impact_cost: float = 0
    incremental_impact_cost: float = 0
    new_project_additional_high_noise_minutes: int = 0
    sensitive_new_project_exposure_minutes: int = 0
    saturation_slot_count: int = 0
    schedule_change_minutes: int = 0


class ScheduleCandidate(BaseModel):
    id: str
    task_assignments: list[TaskAssignment] = Field(default_factory=list)
    feasibility: bool
    infeasibility_reasons: list[str] = Field(default_factory=list)
    needs_confirmation: list[str] = Field(default_factory=list)
    metrics: ScheduleMetrics = Field(default_factory=ScheduleMetrics)
    objective_values: dict[str, float] = Field(default_factory=dict)
    provenance: SourceMetadata


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1)


class PredictRequest(BaseModel):
    scenario_id: str = "case-a"
    analysis_date: date = date(2026, 10, 26)
    assignments: list[TaskAssignment] | None = None
    sensitivity_enabled: bool = True
    background_profile: str = "assumed_demo"


class ImpactRequest(BaseModel):
    total_noise_db: float
    threshold_db: float = 65.0
    duration_minutes: int = Field(ge=0)
    continuous_minutes: int = Field(ge=0)
    sensitivity_weight: float = Field(gt=0)
    cumulative_burden: float = Field(default=0, ge=0)
    baseline_noise_db: float | None = None


class OptimizeRequest(BaseModel):
    scenario_id: str = "case-a"
    analysis_date: date = date(2026, 10, 26)
    sensitivity_enabled: bool = True
    background_profile: str = "assumed_demo"
    objective_mode: Literal["incremental_impact", "absolute_impact"] = "incremental_impact"


class CompareRequest(BaseModel):
    scenario_id: str = "case-a"
    analysis_date: date = date(2026, 10, 26)
    before: list[TaskAssignment]
    after: list[TaskAssignment]
    background_profile: str = "assumed_demo"


class ExperimentRequest(BaseModel):
    scenario_id: str = "case-a"
    analysis_date: date = date(2026, 10, 26)
    background_profile: str = "assumed_demo"
    objective_mode: Literal["incremental_impact", "absolute_impact"] = "incremental_impact"
