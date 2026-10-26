from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AddressCoordinateRequest(BaseModel):
    address: str = Field(min_length=2, max_length=300, description="신고서 추출 또는 사용자가 입력한 공사 주소")
    selected_address_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
        description="selection_required 응답의 후보 ID. 동일 주소로 다시 요청할 때 사용",
    )

    @model_validator(mode="after")
    def non_blank_address(self):
        self.address = self.address.strip()
        if len(self.address) < 2:
            raise ValueError("address must contain at least two non-whitespace characters")
        return self


class AddressCandidate(BaseModel):
    address_id: str
    road_address: str
    parcel_address: str | None = None
    building_name: str | None = None


class SourceCoordinate(BaseModel):
    x: float
    y: float
    crs: Literal["EPSG:5179"]


class MapCoordinate(BaseModel):
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    crs: Literal["EPSG:4326"]


class CoordinateSource(BaseModel):
    provider: Literal["행정안전부 주소기반산업지원서비스"]
    api: Literal["좌표제공 검색 API"]
    point_semantics: Literal["도로명주소 건물 출입구 대표점"]
    retrieved_live: bool


class AddressCoordinateResponse(BaseModel):
    status: Literal[
        "resolved",
        "selection_required",
        "not_found",
        "invalid_selection",
        "configuration_error",
        "provider_auth_error",
        "provider_rate_limited",
        "provider_timeout",
        "provider_error",
        "invalid_provider_coordinate",
    ]
    original_address: str
    normalized_official_address: str | None = None
    source_coordinate: SourceCoordinate | None = None
    map_coordinate: MapCoordinate | None = None
    coordinate_source: CoordinateSource | None = None
    address_match_status: Literal[
        "exact",
        "normalized",
        "user_selected",
        "multiple_candidates",
        "no_match",
        "not_evaluated",
    ]
    user_confirmation_required: bool
    failure_reason: str | None = None
    candidates: list[AddressCandidate] = Field(default_factory=list)
    official_address_coordinate: MapCoordinate | None = None
    construction_geometry: None = None
    demo_geometry: None = None
    residential_facade_receptor: None = None
    site_accuracy_status: Literal["not_validated"] = "not_validated"
    limitation: str = "공식 주소 좌표는 도로명주소 건물 출입구 대표점이며 공사 중심점·공사 선형·수음점이 아닙니다."
