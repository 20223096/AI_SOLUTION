from fastapi import APIRouter

from app.services.public_data import official_construction_design, public_catalog
from app.models.responses import ConstructionDesignResponse, PublicDataCatalogResponse

router = APIRouter(prefix="/api/public-data", tags=["public-data"])


@router.get("/catalog", response_model=PublicDataCatalogResponse)
def catalog():
    return public_catalog()


@router.get("/construction-design", response_model=ConstructionDesignResponse)
def construction_design():
    return official_construction_design()
