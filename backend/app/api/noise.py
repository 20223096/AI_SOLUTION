from fastapi import APIRouter, HTTPException

from app.models.domain import PredictRequest
from app.services.prediction import predict

router = APIRouter(prefix="/api/noise", tags=["noise"])


@router.post("/predict")
def noise_predict(request: PredictRequest):
    try:
        return predict(request.scenario_id, request.analysis_date, request.assignments, request.sensitivity_enabled)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
