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
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    coordinate_crs: Literal["EPSG:4326"] | None = None
    coordinate_source: str | None = None
    distance_method: str | None = None
    spatial_status: Literal["verified_public", "assumed", "deferred"] | None = None


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
    sensitive_new_project_receptor_minutes: int = 0
    sensitivity_weighted_new_project_receptor_minutes: float = 0
    new_project_receptor_minutes: int = 0
    new_project_inactive_minutes: int = 0
    max_continuous_new_project_minutes: int = 0
    new_project_energy_exposure_65db_ref_minutes: float = 0
    cumulative_delta_db_minutes: float = 0
    existing_noise_overlap_receptor_minutes: int = 0
    max_total_estimated_db: float = 0
    max_new_project_contribution_db: float = 0
    saturation_slot_count: int = 0
    schedule_change_minutes: int = 0
    project_start_change_minutes: int = 0
    project_end_change_minutes: int = 0


class ScheduleCandidate(BaseModel):
    id: str
    task_assignments: list[TaskAssignment] = Field(default_factory=list)
    feasibility: bool
    infeasibility_reasons: list[str] = Field(default_factory=list)
    needs_confirmation: list[str] = Field(default_factory=list)
    metrics: ScheduleMetrics = Field(default_factory=ScheduleMetrics)
    objective_values: dict[str, float] = Field(default_factory=dict)
    schedule_change_details: dict[str, Any] = Field(default_factory=dict)
    provenance: SourceMetadata


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1)


class PredictRequest(BaseModel):
    scenario_id: str = "case-a"
    analysis_date: date = date(2026, 10, 26)
    assignments: list[TaskAssignment] | None = None
    sensitivity_enabled: bool = True
    background_profile: str = "assumed_demo"


class M1Point(BaseModel):
    x: float
    y: float
    z_m: float = 0.0
    crs: Literal["EPSG:4326", "EPSG:5179", "EPSG:5186"]
    provenance: Literal["official_design", "field_verified", "derived", "assumed", "unknown"]


class M1ActiveInterval(BaseModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("active interval end must be after start")
        return self


class M1PropagationCorrection(BaseModel):
    value_db: float | None = None
    status: Literal["field_verified", "derived", "assumed", "not_modelled"] = "not_modelled"
    source: str | None = None

    @model_validator(mode="after")
    def require_value_only_when_modelled(self):
        if self.status == "not_modelled" and self.value_db is not None:
            raise ValueError("not_modelled correction must not have a numeric value")
        if self.status != "not_modelled" and self.value_db is None:
            raise ValueError("modelled correction requires value_db")
        return self


class M1NoiseSource(BaseModel):
    id: str
    segment_id: Literal["segment-yeonse-ro-2na-gil", "segment-chungjeong-ro"]
    source_type: Literal["fixed", "moving_work", "moving_vehicle", "impulsive"]
    equipment_category: str
    equipment_model: str | None = None
    count: int = Field(default=1, ge=1)
    sound_power_level_db: float | None = None
    lw_provenance: Literal["official_reference", "field_verified", "assumed", "unknown"] = "unknown"
    reference_scenario: Literal["low", "median", "high"] | None = None
    position: M1Point | None = None
    deployment_start: datetime
    deployment_end: datetime
    actual_active_minutes: float | None = Field(default=None, ge=0, le=15)
    activity_provenance: Literal["field_verified", "derived", "assumed", "unknown"] = "unknown"
    active_intervals: list[M1ActiveInterval] = Field(default_factory=list)
    simultaneous_group: str | None = None
    measurement_condition_verified: bool = False

    @model_validator(mode="after")
    def valid_deployment(self):
        if self.deployment_end <= self.deployment_start:
            raise ValueError("deployment_end must be after deployment_start")
        if self.actual_active_minutes is not None and self.activity_provenance == "unknown":
            raise ValueError("numeric activity requires non-unknown activity_provenance")
        return self


class M1Receptor(BaseModel):
    id: str
    position: M1Point | None = None


class M1PredictRequest(BaseModel):
    slot_start: datetime
    slot_end: datetime
    sources: list[M1NoiseSource]
    receptors: list[M1Receptor]
    background_laeq_db: float | None = None
    background_provenance: Literal["official_reference", "field_verified", "derived", "assumed", "unknown"] = "unknown"
    overlap_mode: Literal["exact", "complete_concurrent", "sequential_possible", "overlap_unknown"] = "overlap_unknown"
    corrections: dict[Literal["ground", "atmospheric", "barrier", "building", "reflection", "meteorology"], M1PropagationCorrection] = Field(default_factory=dict)

    @model_validator(mode="after")
    def fifteen_minute_slot(self):
        if (self.slot_end - self.slot_start).total_seconds() != 900:
            raise ValueError("M1 currently requires exactly one 15-minute slot")
        if self.background_laeq_db is not None and self.background_provenance == "unknown":
            raise ValueError("numeric background requires non-unknown provenance")
        return self


class M1SensitivityCase(BaseModel):
    id: str
    varied_variable: Literal["equipment_lw", "activity_ratio", "simultaneous_operation", "source_position", "receptor_position_or_height", "background_profile", "propagation_correction_availability"]
    request: M1PredictRequest


class M1UncertaintyRequest(BaseModel):
    cases: list[M1SensitivityCase] = Field(min_length=1)


class M1TaskAcousticMapping(BaseModel):
    task_id: str
    segment_id: Literal["segment-yeonse-ro-2na-gil", "segment-chungjeong-ro"]
    source_type: Literal["fixed", "moving_work", "moving_vehicle", "impulsive"]
    equipment_category: str
    equipment_model: str | None = None
    count: int = Field(default=1, ge=1)
    sound_power_level_db: float | None = None
    lw_provenance: Literal["official_reference", "field_verified", "assumed", "unknown"] = "unknown"
    reference_scenario: Literal["low", "median", "high"] | None = None
    position: M1Point | None = None
    active_ratio: float | None = Field(default=None, ge=0, le=1)
    activity_provenance: Literal["field_verified", "derived", "assumed", "unknown"] = "unknown"
    simultaneous_group: str | None = None
    measurement_condition_verified: bool = False


class M1ScheduleEvaluationRequest(BaseModel):
    scenario_id: str
    analysis_date: date = date(2026, 10, 26)
    background_profile: str = "assumed_demo"
    receptors: list[M1Receptor]
    task_mappings: list[M1TaskAcousticMapping]
    overlap_mode: Literal["complete_concurrent", "sequential_possible", "overlap_unknown"] = "overlap_unknown"


class FieldObservation(BaseModel):
    id: str
    receptor_id: str
    receptor_position: M1Point
    start: datetime
    end: datetime
    laeq_dba: float
    acoustic_scope: Literal["total_environment", "new_project_contribution"] = "total_environment"
    measurement_duration_minutes: float = Field(gt=0)
    equipment_active: dict[str, bool]
    instrument: str = Field(min_length=1)
    calibration_before: str = Field(min_length=1)
    calibration_after: str = Field(min_length=1)
    weather: dict[str, float | str]
    source: str = Field(min_length=1)

    @model_validator(mode="after")
    def measurement_duration_matches_interval(self):
        actual = (self.end - self.start).total_seconds() / 60
        if actual <= 0 or abs(actual - self.measurement_duration_minutes) > 1e-6:
            raise ValueError("measurement duration must match start/end interval")
        if not self.weather:
            raise ValueError("weather conditions are required")
        return self


class FieldPredictionRecord(BaseModel):
    receptor_id: str
    receptor_position: M1Point
    start: datetime
    end: datetime
    predicted_laeq_dba: float
    acoustic_scope: Literal["total_environment", "new_project_contribution"] = "total_environment"
    equipment_ids: list[str] = Field(default_factory=list)
    metric: Literal["LAeq_dBA"] = "LAeq_dBA"


class FieldValidationRequest(BaseModel):
    observations: list[FieldObservation] = Field(default_factory=list)
    predictions: list[FieldPredictionRecord] = Field(default_factory=list)


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
    objective_mode: Literal["incremental_impact", "absolute_impact", "physical_energy", "sensitive_exposure", "continuous_burden", "multi_axis"] = "incremental_impact"


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
    objective_mode: Literal["incremental_impact", "absolute_impact", "physical_energy", "sensitive_exposure", "continuous_burden", "multi_axis"] = "incremental_impact"
