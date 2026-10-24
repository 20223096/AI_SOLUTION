from fastapi import APIRouter

from app.services.public_data import official_construction_design, public_catalog

router = APIRouter(prefix="/api/public-data", tags=["public-data"])


@router.get("/catalog")
def catalog():
    return public_catalog()


@router.get("/construction-design")
def construction_design():
    return official_construction_design()
