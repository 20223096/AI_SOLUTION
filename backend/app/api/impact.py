from fastapi import APIRouter

from app.models.domain import ImpactRequest
from app.services.impact import calculate_impact

router = APIRouter(prefix="/api/impact", tags=["impact"])


@router.post("/calculate")
def impact(request: ImpactRequest):
    return calculate_impact(request)
