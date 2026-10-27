from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

from app.models.domain import ConstructionNotice, Equipment, Receptor, ScheduleCandidate, ScheduleMetrics, TaskAssignment


class ResponseModel(BaseModel):
    """Typed known fields while preserving branch-specific fields verbatim."""

    model_config = ConfigDict(extra="allow")


class JsonObject(RootModel[dict[str, Any]]):
    pass


class HealthResponse(ResponseModel):
    status: Literal["ok"]
    model_version: str
    extractor_mode: str


class ScenarioSummary(ResponseModel):
    id: str
    title: str
    expected_feasibility: bool


class ScenarioListResponse(RootModel[list[ScenarioSummary]]):
    pass


class ScenarioDetailResponse(ResponseModel):
    id: str
    title: str
    expected_feasibility: bool
    settings: dict[str, Any]
    notice: ConstructionNotice
    equipment: list[Equipment]
    receptors: list[Receptor]


class MockNoticeExtractResponse(ResponseModel):
    mode: Literal["mock"]
    is_actual_ai: Literal[False]
    notice: ConstructionNotice
    field_evidence: dict[str, Any]
    warnings: list[str]


class LLMNoticeExtractResponse(ResponseModel):
    mode: Literal["llm"]
    is_actual_ai: Literal[True]
    provider: str
    model: str
    notice: ConstructionNotice
    field_evidence: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, int] = Field(default_factory=dict)
    warnings: list[str]


NoticeExtractResponse = MockNoticeExtractResponse | LLMNoticeExtractResponse


class M0PredictionRow(ResponseModel):
    receptor_id: str
    slot_start: datetime
    slot_end: datetime
    active_task_ids: list[str]
    construction_lp_db: float | None
    new_project_contribution_db: float | None
    background_laeq_db: float
    background_only_db: float
    existing_noise_lp_db: float | None
    existing_environment_db: float
    existing_event_ids: list[str]
    total_estimated_db: float | None
    with_new_project_db: float | None
    delta_total_db: float
    total_impact: int | float
    baseline_impact: int | float
    incremental_impact: int | float
    impact_saturation: dict[str, Any]
    sensitivity: dict[str, Any]
    source_metadata: dict[str, Any]


class NoisePredictResponse(ResponseModel):
    scenario_id: str
    analysis_date: date
    model_version: str
    scoring_version: str
    timezone: str
    slot_minutes: int
    background_profile: str
    public_data_calendar_institution: str | None
    calendar_overlaps: list[dict[str, Any]]
    existing_event_acoustic_policy: dict[str, Any]
    predictions: list[M0PredictionRow]
    warnings: list[str]
    legal_assessment: None
    disclaimer: str


class BackgroundProfile(ResponseModel):
    id: str
    label: str
    calculation_eligible: bool
    metric: str
    observation_period: str | dict[str, Any] | None
    hourly_values: list[dict[str, Any]]
    source_metadata: dict[str, Any]
    quality_warnings: list[str]


class BackgroundProfilesResponse(ResponseModel):
    profiles: list[BackgroundProfile]
    default: str


class M1SourceResult(ResponseModel):
    id: str
    segment_id: str
    equipment_category: str
    source_type: str
    equipment_model: str | None
    simultaneous_group: str | None
    count: int
    lw_db: float
    distance_3d_m: float
    active_minutes: float
    activity_ratio: float
    activity_basis: str
    activity_provenance: str
    source_position: dict[str, Any]
    receptor_position: dict[str, Any]
    measurement_condition_verified: bool
    lw_source: dict[str, Any]


class M1PredictionRow(ResponseModel):
    receptor_id: str
    slot_start: datetime
    slot_end: datetime
    new_project_contribution_laeq_db: float | None
    slot_laeq_dba: float | None
    total_laeq_db: float | None
    delta_total_db: float | None
    new_project_energy_exposure_65db_ref_minutes: float | None
    incremental_impact_legacy_v1: float | None
    max_simultaneous_lp_db: float | None
    maximum_concurrent_combined_level_db: float | None
    measured_lafmax_dba: None
    simultaneity: dict[str, Any]
    continuous_new_project_exposure: dict[str, Any]
    sources: list[M1SourceResult]


class MissingInput(ResponseModel):
    field: str
    status: str
    source_id: str | None = None
    receptor_id: str | None = None
    task_id: str | None = None
    reason: str | None = None


class M1PredictResponse(ResponseModel):
    model_version: str
    calculation_status: Literal["calculated", "simulated", "deferred"]
    validation_status: Literal["not_evaluable", "evaluated"]
    slot_minutes: int | None = None
    overlap_mode: str | None = None
    background: dict[str, Any] | None = None
    corrections: dict[str, Any] | None = None
    results: list[M1PredictionRow] | None = None
    missing_required_inputs: list[MissingInput]
    accuracy_claim: None = None
    disclaimer: str


class M0M1ComparisonRow(ResponseModel):
    receptor_id: str
    m0_new_project_laeq_db: float | None
    m1_new_project_laeq_db: float | None
    m0_total_laeq_db: float | None
    m1_total_laeq_db: float | None
    m0_delta_total_db: float | None
    m1_delta_total_db: float | None
    m0_energy_exposure: float | None
    m1_energy_exposure: float | None
    m0_incremental_impact: float | None
    m1_incremental_impact: float | None


class M0M1CompareResponse(ResponseModel):
    comparison_status: Literal["simulated", "deferred"]
    validation_status: Literal["not_evaluable"]
    m0_characterization: str | None = None
    m1_characterization: str | None = None
    comparisons: list[M0M1ComparisonRow] | None = None
    m0: M1PredictResponse | None = None
    m1: M1PredictResponse
    accuracy_improvement_claimed: bool | None = None


class M1UncertaintyCaseResult(ResponseModel):
    id: str
    varied_variable: str
    prediction: M1PredictResponse


class M1UncertaintyResponse(ResponseModel):
    analysis_type: str
    probability_distribution: None
    confidence_interval: None
    validation_status: Literal["not_evaluable"]
    cases: list[M1UncertaintyCaseResult]
    ranges: list[dict[str, Any]]
    note: str


class M1EvaluatedCandidate(ResponseModel):
    id: str
    feasibility: bool
    evaluation_status: Literal["simulated", "deferred"]
    task_assignments: list[TaskAssignment] | None = None
    objective_axes: dict[str, int | float] | None = None
    slot_results: list[dict[str, Any]] | None = None
    input_provenance: dict[str, Any] | None = None
    missing_required_inputs: list[MissingInput] | None = None


class M1CandidateEvaluationResponse(ResponseModel):
    evaluation_status: Literal["simulated", "deferred"]
    validation_status: Literal["not_evaluable"]
    scenario_id: str | None = None
    base_optimizer_unchanged: bool | None = None
    generated_candidate_count: int | None = None
    feasible_candidate_count: int | None = None
    candidates: list[M1EvaluatedCandidate]
    pareto_axes: list[str] | None = None
    pareto_candidates: list[M1EvaluatedCandidate]
    recommended_candidate: M1EvaluatedCandidate | None = None
    recommendation_reasons: list[dict[str, Any]] | None = None
    missing_required_inputs: list[MissingInput] | None = None
    note: str | None = None


class FieldMetric(ResponseModel):
    validation_status: Literal["evaluated", "not_evaluable"]
    sample_count: int | None = None
    mae: float | None
    rmse: float | None
    bias: float | None


class FieldValidationResponse(FieldMetric):
    reason: str | None = None
    aligned_sample_count: int | None = None
    receptor_errors: list[dict[str, Any]]
    equipment_errors: list[dict[str, Any]]
    alignment_failures: list[dict[str, Any]]
    alignment_requirements: list[str] | None = None
    coordinate_tolerance_note: str | None = None


class DesignSimulationCatalogResponse(ResponseModel):
    data_version: str
    simulation_version: str
    official_design_data: dict[str, Any]
    official_reference_noise: dict[str, dict[str, Any]]
    excavator_capacity_match: dict[str, Any]
    missing_required_inputs: list[str]
    official_prediction_status: Literal["deferred"]
    validation_status: Literal["not_evaluable"]


class DesignCandidate(ResponseModel):
    id: str
    method: str
    feasible: bool
    pareto_included: bool
    assignments: list[dict[str, Any]] | None = None
    slot_results: list[dict[str, Any]] | None = None
    metrics: dict[str, Any] | None = None
    acoustic_completeness: Literal["partial", "complete"] | None = None
    missing_noise_equipment: list[str] | None = None
    infeasibility_reasons: list[str] | None = None


class DesignSimulationResponse(ResponseModel):
    simulation_version: str
    result_type: Literal["design_based_simulation"]
    official_field_prediction_status: Literal["deferred"]
    simulation_status: Literal["simulated"]
    validation_status: Literal["not_evaluable"]
    segment: dict[str, Any]
    simulation_geometry: dict[str, Any]
    background_profile: dict[str, Any]
    data_quality: dict[str, list[str]]
    quantity_allocation: str
    process_assumptions: list[dict[str, Any]]
    candidate_count: int
    feasible_candidate_count: int
    pareto_axes: list[str]
    candidates: list[DesignCandidate]
    pareto_candidates: list[DesignCandidate]
    recommended_candidate: DesignCandidate
    recommendation_reasons: list[dict[str, Any]]
    accuracy_claim: None


class ImpactResponse(ResponseModel):
    score: float
    components: dict[str, float]
    weights: dict[str, float]
    classification: str
    baseline_score: float | None = None
    incremental_score: float | None = None
    saturation: dict[str, bool] | None = None


class OptimizationDiagnostics(ResponseModel):
    generated_candidate_count: int
    feasible_candidate_count: int
    infeasible_candidate_count: int
    pareto_candidate_count: int
    pareto_axes: list[str]
    candidate_metrics: list[dict[str, Any]]
    sensitivity_enabled: bool
    background_profile: str
    objective_mode: str
    objective_field: str | None
    objective_unit: str | None
    default_objective_unchanged: bool
    balanced_selection: str | None
    policy_overlap_cost_included_in_pareto: bool


class RecommendedOption(ResponseModel):
    character: list[str]
    candidate: ScheduleCandidate
    recommendation_reasons: list[dict[str, Any]]


class OptimizeSuccessResponse(ResponseModel):
    scenario_id: str
    analysis_date: date
    optimization_status: Literal["optimal_enumeration"]
    scoring_version: str
    metrics_version: str
    valid_candidates: list[ScheduleCandidate]
    pareto_candidates: list[ScheduleCandidate]
    recommended_options: list[RecommendedOption]
    solver: str
    note: str
    diagnostics: OptimizationDiagnostics


class OptimizeInfeasibleResponse(ResponseModel):
    scenario_id: str
    analysis_date: date
    optimization_status: Literal["infeasible"]
    scoring_version: str
    metrics_version: str
    valid_candidates: list[ScheduleCandidate]
    pareto_candidates: list[ScheduleCandidate]
    recommended_options: list[RecommendedOption]
    infeasible_result: ScheduleCandidate
    relaxation_guidance: list[str]
    solver: str
    diagnostics: OptimizationDiagnostics


OptimizeResponse = OptimizeSuccessResponse | OptimizeInfeasibleResponse


class CompareResponse(ResponseModel):
    before: ScheduleMetrics
    after: ScheduleMetrics
    delta: dict[str, int | float]
    schedule_change_details: dict[str, Any]
    comparison_basis: dict[str, Any]


class DiagnosticsResponse(OptimizationDiagnostics):
    scenario_id: str
    analysis_date: date


class ExperimentResponse(ResponseModel):
    scenario_id: str
    analysis_date: date
    objective_mode: str
    experiment_a: dict[str, Any]
    experiment_b: dict[str, Any]
    experiment_c: list[dict[str, Any]]
    disclaimer: str


class PublicDataCatalogResponse(ResponseModel):
    manifest: dict[str, Any]
    equipment_noise: list[dict[str, Any]]
    construction_events: list[dict[str, Any]]
    cultural_events: list[dict[str, Any]]
    receptors: list[dict[str, Any]]
    official_facilities: list[dict[str, Any]]
    receptor_distances: list[dict[str, Any]]
    official_equipment_noise: list[dict[str, Any]]
    official_construction_design: dict[str, Any]
    academic_calendar: list[dict[str, Any]]
    waste_collection: list[dict[str, Any]]
    land_use: list[dict[str, Any]]
    policy: dict[str, bool]


class ConstructionDesignResponse(ResponseModel):
    data_version: str
    notice_id: str
    project_name: str
    dataset_provenance: str
    provenance_policy: dict[str, Any]
    source_documents: dict[str, dict[str, Any]]
    segments: list[dict[str, Any]]
    route_length_total_m: dict[str, Any]
    work_packages: list[dict[str, Any]]
    equipment_reference_matching: list[dict[str, Any]]
    schedule_metadata: dict[str, Any]
    assumed_demo_schedule_reference: dict[str, Any]
    calculation_readiness: dict[str, Any]
