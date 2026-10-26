from fastapi import APIRouter, HTTPException

from app.models.domain import DesignBasedSimulationRequest, FieldValidationRequest, M1PredictRequest, M1ScheduleEvaluationRequest, M1UncertaintyRequest, PredictRequest
from app.models.responses import (
    BackgroundProfilesResponse,
    DesignSimulationCatalogResponse,
    DesignSimulationResponse,
    FieldValidationResponse,
    M0M1CompareResponse,
    M1CandidateEvaluationResponse,
    M1PredictResponse,
    M1UncertaintyResponse,
    NoisePredictResponse,
)
from app.services.design_simulation import design_simulation_catalog, run_design_rescheduling
from app.services.field_validation import evaluate_field_validation
from app.services.m1_acoustics import analyze_uncertainty, compare_m0_m1, evaluate_m1_schedule_candidates, predict_m1
from app.services.prediction import predict
from app.services.background_profiles import list_profiles

router = APIRouter(prefix="/api/noise", tags=["noise"])


@router.post("/predict", response_model=NoisePredictResponse)
def noise_predict(request: PredictRequest):
    try:
        return predict(request.scenario_id, request.analysis_date, request.assignments, request.sensitivity_enabled, request.background_profile)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/background-profiles", response_model=BackgroundProfilesResponse)
def background_profiles():
    return {"profiles": list_profiles(), "default": "assumed_demo"}


@router.post("/predict-m1", response_model=M1PredictResponse, response_model_exclude_unset=True)
def noise_predict_m1(request: M1PredictRequest):
    try:
        return predict_m1(request)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/compare-m0-m1", response_model=M0M1CompareResponse, response_model_exclude_unset=True)
def noise_compare_m0_m1(request: M1PredictRequest):
    try:
        return compare_m0_m1(request)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/m1-uncertainty", response_model=M1UncertaintyResponse)
def noise_m1_uncertainty(request: M1UncertaintyRequest):
    try:
        return analyze_uncertainty(request)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/evaluate-m1-candidates", response_model=M1CandidateEvaluationResponse, response_model_exclude_unset=True)
def noise_evaluate_m1_candidates(request: M1ScheduleEvaluationRequest):
    try:
        return evaluate_m1_schedule_candidates(request)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/validate-m1-field", response_model=FieldValidationResponse, response_model_exclude_unset=True)
def noise_validate_m1_field(request: FieldValidationRequest):
    return evaluate_field_validation(request)


@router.get("/design-simulation/catalog", response_model=DesignSimulationCatalogResponse)
def noise_design_simulation_catalog():
    return design_simulation_catalog()


@router.post("/design-simulation/reschedule", response_model=DesignSimulationResponse, response_model_exclude_unset=True)
def noise_design_simulation_reschedule(request: DesignBasedSimulationRequest):
    try:
        return run_design_rescheduling(request)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
