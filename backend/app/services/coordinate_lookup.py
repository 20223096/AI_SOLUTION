from __future__ import annotations

import re
from typing import Any

import httpx
from pydantic import ValidationError

from app.models.coordinates import (
    AddressCandidate,
    AddressCoordinateResponse,
    CoordinateSource,
    MapCoordinate,
    SourceCoordinate,
)
from app.services.official_address import JUSO_COORD_URL, JUSO_SEARCH_URL, epsg5179_to_wgs84, normalize_service_key

SOURCE = CoordinateSource(
    provider="행정안전부 주소기반산업지원서비스",
    api="좌표제공 검색 API",
    point_semantics="도로명주소 건물 출입구 대표점",
    retrieved_live=True,
)
ADDRESS_CODE_FIELDS = ("admCd", "rnMgtSn", "udrtYn", "buldMnnm", "buldSlno")
AUTH_CODES = {"E0001"}


def _comparable(value: str) -> str:
    value = value.split(" (", 1)[0]
    return re.sub(r"\s+", "", value).strip()


def _candidate(row: dict[str, Any]) -> AddressCandidate:
    return AddressCandidate(
        address_id=str(row.get("bdMgtSn") or ""),
        road_address=str(row.get("roadAddr") or row.get("roadAddrPart1") or ""),
        parcel_address=row.get("jibunAddr") or None,
        building_name=row.get("bdNm") or None,
    )


def _base(status: str, address: str, **values: Any) -> AddressCoordinateResponse:
    return AddressCoordinateResponse(
        status=status,
        original_address=address,
        address_match_status=values.pop("address_match_status", "not_evaluated"),
        user_confirmation_required=values.pop("user_confirmation_required", status != "resolved"),
        **values,
    )


class JusoCoordinateClient:
    """Server-side JUSO adapter. Keys are POST body values and are never logged."""

    def __init__(
        self,
        search_key: str | None,
        coordinate_key: str | None,
        timeout_seconds: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.search_key = normalize_service_key(search_key) if search_key else None
        self.coordinate_key = normalize_service_key(coordinate_key) if coordinate_key else None
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def _post(self, url: str, data: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
            response = client.post(url, data=data, headers={"Accept": "application/json"})
            response.raise_for_status()
            payload = response.json()
        results = payload.get("results")
        if not isinstance(results, dict) or not isinstance(results.get("common"), dict):
            raise ValueError("invalid JUSO response envelope")
        return results

    @staticmethod
    def _provider_failure(address: str, common: dict[str, Any]) -> tuple[AddressCoordinateResponse, int]:
        code = str(common.get("errorCode", ""))
        if code in AUTH_CODES:
            return _base("provider_auth_error", address, failure_reason=f"JUSO authentication failed ({code})"), 503
        return _base("provider_error", address, failure_reason=f"JUSO provider error ({code or 'unknown'})"), 502

    def lookup(self, address: str, selected_address_id: str | None = None) -> tuple[AddressCoordinateResponse, int]:
        address = address.strip()
        if not self.search_key or not self.coordinate_key:
            return _base("configuration_error", address, failure_reason="Required JUSO API key is not configured"), 503
        try:
            search = self._post(JUSO_SEARCH_URL, {
                "confmKey": self.search_key,
                "currentPage": "1",
                "countPerPage": "10",
                "keyword": address,
                "resultType": "json",
            })
            common = search["common"]
            if str(common.get("errorCode")) != "0":
                return self._provider_failure(address, common)
            rows = search.get("juso") or []
            if not rows:
                return _base("not_found", address, address_match_status="no_match", failure_reason="No official road-address result"), 200

            candidates = [_candidate(row) for row in rows]
            chosen = next((row for row in rows if selected_address_id and str(row.get("bdMgtSn")) == selected_address_id), None)
            match_status = "user_selected" if chosen else "normalized"
            if selected_address_id and chosen is None:
                return _base("invalid_selection", address, address_match_status="multiple_candidates", candidates=candidates, failure_reason="selected_address_id is not in the current result set"), 200
            if chosen is None:
                exact = [row for row in rows if _comparable(str(row.get("roadAddrPart1") or row.get("roadAddr") or "")) == _comparable(address)]
                if len(exact) == 1:
                    chosen = exact[0]
                    match_status = "exact" if str(chosen.get("roadAddrPart1") or chosen.get("roadAddr")) == address else "normalized"
                elif len(rows) == 1:
                    chosen = rows[0]
                else:
                    return _base("selection_required", address, address_match_status="multiple_candidates", candidates=candidates, failure_reason="Multiple official addresses matched"), 200

            missing = [key for key in ADDRESS_CODE_FIELDS if chosen.get(key) in (None, "")]
            if missing:
                return _base("provider_error", address, failure_reason="JUSO search response omitted required address codes"), 502
            coord = self._post(JUSO_COORD_URL, {
                "confmKey": self.coordinate_key,
                "resultType": "json",
                **{key: chosen[key] for key in ADDRESS_CODE_FIELDS},
            })
            if str(coord["common"].get("errorCode")) != "0":
                return self._provider_failure(address, coord["common"])
            points = coord.get("juso") or []
            if len(points) != 1:
                return _base("provider_error", address, failure_reason="JUSO coordinate response did not contain exactly one point"), 502
            try:
                source = SourceCoordinate(x=float(points[0]["entX"]), y=float(points[0]["entY"]), crs="EPSG:5179")
                longitude, latitude = epsg5179_to_wgs84(source.x, source.y)
                target = MapCoordinate(longitude=longitude, latitude=latitude, crs="EPSG:4326")
            except (KeyError, TypeError, ValueError, ValidationError, OverflowError):
                return _base("invalid_provider_coordinate", address, failure_reason="JUSO returned an invalid EPSG:5179 coordinate"), 502
            official = _candidate(chosen)
            return _base(
                "resolved",
                address,
                normalized_official_address=official.road_address,
                source_coordinate=source,
                map_coordinate=target,
                official_address_coordinate=target,
                coordinate_source=SOURCE,
                address_match_status=match_status,
                user_confirmation_required=match_status != "exact",
                candidates=[official],
            ), 200
        except httpx.TimeoutException:
            return _base("provider_timeout", address, failure_reason="JUSO request timed out"), 503
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                return _base("provider_rate_limited", address, failure_reason="JUSO request limit reached (HTTP 429)"), 503
            if exc.response.status_code in {401, 403}:
                return _base("provider_auth_error", address, failure_reason=f"JUSO authentication failed (HTTP {exc.response.status_code})"), 503
            return _base("provider_error", address, failure_reason=f"JUSO HTTP error ({exc.response.status_code})"), 502
        except (httpx.HTTPError, ValueError, TypeError):
            return _base("provider_error", address, failure_reason="JUSO request or response failed"), 502
