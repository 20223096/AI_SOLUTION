from fastapi import APIRouter, HTTPException

from app.models.domain import M1PredictRequest, M1UncertaintyRequest, PredictRequest
from app.services.m1_acoustics import analyze_uncertainty, compare_m0_m1, predict_m1
from app.services.prediction import predict
from app.services.background_profiles import list_profiles

router = APIRouter(prefix="/api/noise", tags=["noise"])


@router.post("/predict")
def noise_predict(request: PredictRequest):
    try:
        return predict(request.scenario_id, request.analysis_date, request.assignments, request.sensitivity_enabled, request.background_profile)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/background-profiles")
def background_profiles():
    return {"profiles": list_profiles(), "default": "assumed_demo"}


@router.post("/predict-m1")
def noise_predict_m1(request: M1PredictRequest):
    try:
        return predict_m1(request)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/compare-m0-m1")
def noise_compare_m0_m1(request: M1PredictRequest):
    try:
        return compare_m0_m1(request)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/m1-uncertainty")
def noise_m1_uncertainty(request: M1UncertaintyRequest):
    try:
        return analyze_uncertainty(request)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
