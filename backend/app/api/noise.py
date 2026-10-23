from fastapi import APIRouter, HTTPException

from app.models.domain import PredictRequest
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
