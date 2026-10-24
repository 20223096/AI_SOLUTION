from fastapi import APIRouter

from app.models.domain import ImpactRequest
from app.models.responses import ImpactResponse
from app.services.impact import calculate_impact

router = APIRouter(prefix="/api/impact", tags=["impact"])


@router.post("/calculate", response_model=ImpactResponse, response_model_exclude_unset=True)
def impact(request: ImpactRequest):
    return calculate_impact(request)
