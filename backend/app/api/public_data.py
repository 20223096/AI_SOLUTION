from fastapi import APIRouter

from app.services.public_data import public_catalog

router = APIRouter(prefix="/api/public-data", tags=["public-data"])


@router.get("/catalog")
def catalog():
    return public_catalog()
