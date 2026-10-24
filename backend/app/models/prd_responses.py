from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.domain import ScheduleMetrics


class PRDResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OfficialDesignSummary(PRDResponse):
    notice_id: str
    project_name: str
    source: str
    status: Literal["official_document"]
    daily_work_window: None
    calendar_schedule: None
    acoustic_prediction_status: Literal["deferred"]
    note: str


class DemoWorkPlanSummary(PRDResponse):
    scenario_id: str
    analysis_date: date
    work_window: str
    status: Literal["assumed"]
    source: str
    task_duration_status: Literal["user_provided"]
    existing_congestion_overlay_status: Literal["assumed"]
    note: str


class DemoNoticeSummary(PRDResponse):
    scenario_id: str
    status: Literal["assumed"]
    note: str


class SDotSensorAudit(PRDResponse):
    sensor_serial: str
    valid_count: int
    held_count: int
    noise_avg_min: float | None
    noise_avg_max: float | None
    noise_avg_mean: float | None


class SDotDayAudit(PRDResponse):
    date: date
    row_count: int
    first_observed_at: datetime
    last_observed_at: datetime
    duplicate_count: int
    sensors: list[SDotSensorAudit]


class SDotDailyAudit(PRDResponse):
    source: str
    metric_caveat: str
    days: list[SDotDayAudit]


class DemoContextEvent(PRDResponse):
    kind: Literal["existing_construction", "cultural_event", "waste_collection"]
    event_id: str
    name: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    operation_time: str | None
    noise_db: float | None
    status: Literal["verified_public", "assumed"]
    source: str | None
    note: str


class AcousticOverlapPolicy(PRDResponse):
    official_events: str
    assumed_congestion_overlay: str
    claim_limit: str


class ProvenanceSummary(PRDResponse):
    official_values: list[str]
    observed_values: list[str]
    literature_reference_values: list[str]
    assumed_values: list[str]
    missing_values: list[str]


class DemoFixtureResponse(PRDResponse):
    fixture_version: str
    analysis_date: date
    comparison_date: date
    timezone: Literal["Asia/Seoul"]
    provenance_summary: ProvenanceSummary
    official_new_construction_design: OfficialDesignSummary
    demo_work_plan: DemoWorkPlanSummary
    new_demo_notice: DemoNoticeSummary
    sdot_daily_audit: SDotDailyAudit
    context_events: list[DemoContextEvent]
    acoustic_overlap_policy: AcousticOverlapPolicy


class ConstraintViolation(PRDResponse):
    code: str
    task_id: str | None = None
    equipment_id: str | None = None
    predecessor_id: str | None = None
    count: int | None = None
    maximum: int | None = None
    scheduled_minutes: int | None = None
    required_minutes: int | None = None
    detail: str | None = None


class PRDScheduleValidationResponse(PRDResponse):
    feasible: bool
    violations: list[ConstraintViolation]
    policy_version: Literal["prd_v2_1_explicit_input_only"]
    notice_id: str
    analysis_date: date


class DominatedReason(PRDResponse):
    dominated_by: str
    axes: list[str]
    reason: str


class CandidateDiagnostic(PRDResponse):
    id: str
    first_task_start: datetime | None
    project_start_shift_minutes: int
    total_task_start_shift_minutes: int
    feasibility: bool
    infeasibility_reasons: list[str]
    objective_values: dict[str, float]
    sensitive_time_exposure_minutes: int
    weighted_sensitive_exposure: float
    existing_noise_overlap_receptor_minutes: int
    existing_event_overlap_basis: Literal["assumed_simulation", "none"]
    metrics: ScheduleMetrics
    pareto_included: bool
    dominated_reason: DominatedReason | None


class RecommendationDiagnosticsResponse(PRDResponse):
    analysis_date: date
    scenario_id: str
    scenario_selection_reason: str
    comparison_data_role: Literal["demo_simulation", "comparison_day_simulation"]
    optimization_status: str
    objective_mode: str
    scoring_version: str
    solver: str
    recommended_candidate_ids: list[str]
    pareto_candidate_ids: list[str]
    improvement_over_original: bool
    improvement_summary: str
    candidates: list[CandidateDiagnostic]
    caveats: list[str]


class SensitivityCase(PRDResponse):
    multiplier: Literal[1.1, 1.3, 1.5]
    recommended_candidate_ids: list[str]
    recommendation_changed: bool
    pareto_candidate_ids: list[str]
    candidate_ranking: list[str]
    ranking_changed: bool
    recommended_metrics: list[ScheduleMetrics]
    comparison_to_legacy_recommendation: dict[str, int | float] | None
    infeasible_candidate_ids: list[str]
    candidate_diagnostics: list[CandidateDiagnostic]


class SensitivityDateExperiment(PRDResponse):
    analysis_date: date
    scenario_id: str
    scenario_selection_reason: str
    baseline_policy: Literal["legacy_v1_additive"]
    baseline_recommended_candidate_ids: list[str]
    baseline_candidate_ranking: list[str]
    cases: list[SensitivityCase]


class PRDSensitivityExperimentResponse(PRDResponse):
    policy_name: str
    policy_version: Literal["prd_max_v2_1_experimental"]
    overlap_rule: Literal["maximum_single_multiplier"]
    status: Literal["simulated"]
    background_profile: str
    experiments: list[SensitivityDateExperiment]
    default_m0_m1_unchanged: Literal[True]
    disclaimer: str
