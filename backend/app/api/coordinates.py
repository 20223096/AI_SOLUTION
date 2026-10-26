from fastapi import APIRouter, Response

from app.core.config import get_settings
from app.models.coordinates import AddressCoordinateRequest, AddressCoordinateResponse
from app.services.coordinate_lookup import JusoCoordinateClient

router = APIRouter(prefix="/api/locations", tags=["locations"])


@router.post(
    "/address-coordinate",
    response_model=AddressCoordinateResponse,
    responses={
        502: {"model": AddressCoordinateResponse, "description": "JUSO 공급자 오류 또는 잘못된 좌표"},
        503: {"model": AddressCoordinateResponse, "description": "키 설정·인증·호출 제한·타임아웃 오류"},
    },
)
def address_coordinate(request: AddressCoordinateRequest, response: Response):
    settings = get_settings()
    result, status_code = JusoCoordinateClient(
        search_key=settings.juso_search_api_key.get_secret_value() if settings.juso_search_api_key else None,
        coordinate_key=settings.juso_coord_api_key.get_secret_value() if settings.juso_coord_api_key else None,
        timeout_seconds=settings.juso_timeout_seconds,
    ).lookup(request.address, request.selected_address_id)
    response.status_code = status_code
    return result
