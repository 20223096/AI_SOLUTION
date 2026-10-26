from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.models.prd_responses import DemoFixtureResponse, PRDConstraintRecommendationResponse, PRDPlanningDraftResponse, PRDScheduleValidationResponse, PRDSensitivityExperimentResponse, RecommendationDiagnosticsResponse
from app.models.prd_v2_1 import PRDConstraintRecommendationRequest, PRDPlanningDraftRequest, PRDScheduleValidationRequest, PRDSensitivityExperimentRequest
from app.services.prd_v2_1 import constraint_filtered_recommendations, demo_fixture, demo_sensitivity_policy_experiment, planning_draft_from_notice, recommendation_diagnostics, validate_prd_schedule
from app.services.recommendation_snapshots import RecommendationSnapshotRepository
from app.core.config import get_settings


router = APIRouter(prefix="/api/prd", tags=["prd-v2.1"])


@router.get("/demo/2026-09-11", response_model=DemoFixtureResponse)
def get_demo_fixture():
    return demo_fixture()


@router.post("/schedules/validate", response_model=PRDScheduleValidationResponse)
def validate_schedule(request: PRDScheduleValidationRequest):
    result = validate_prd_schedule(
        request.planning,
        request.analysis_date,
        request.assignments,
        request.predecessors,
        request.equipment_by_task,
        request.restoration_task_ids,
        request.equipment_count_by_task,
    )
    return {**result, "notice_id": request.planning.notice_id, "analysis_date": request.analysis_date}


@router.post("/planning/from-notice", response_model=PRDPlanningDraftResponse)
def create_planning_draft(request: PRDPlanningDraftRequest):
    return planning_draft_from_notice(request)


@router.post("/recommendations/constraint-filtered", response_model=PRDConstraintRecommendationResponse)
def get_constraint_filtered_recommendations(request: PRDConstraintRecommendationRequest):
    try:
        result = constraint_filtered_recommendations(request)
        metadata = RecommendationSnapshotRepository(get_settings().recommendation_snapshot_store_path).save_result(result)
        for candidate in result["candidates"]:
            candidate.update(metadata.get(candidate["candidate_id"], {}))
        if result["original_schedule"]:
            result["original_schedule"].update(metadata.get(result["original_schedule"]["candidate_id"], {}))
        return result
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/recommendation-diagnostics", response_model=RecommendationDiagnosticsResponse)
def get_recommendation_diagnostics(
    analysis_date: date = Query(date(2026, 9, 11)),
    background_profile: str = "road_traffic_observed_profile",
    objective_mode: str = "incremental_impact",
):
    try:
        return recommendation_diagnostics(analysis_date, background_profile, objective_mode)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/sensitivity/experiment", response_model=PRDSensitivityExperimentResponse)
def run_sensitivity_experiment(request: PRDSensitivityExperimentRequest):
    try:
        return demo_sensitivity_policy_experiment(request.analysis_dates, request.background_profile, request.multipliers)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
