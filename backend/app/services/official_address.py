from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import unquote

JUSO_SEARCH_URL = "https://business.juso.go.kr/addrlink/addrLinkApi.do"
JUSO_COORD_URL = "https://business.juso.go.kr/addrlink/addrCoordApi.do"


def normalize_service_key(value: str) -> str:
    """Decode a portal-provided encoded key once; the HTTP client encodes params."""
    return unquote(value.strip())


def redact_key(value: str | None) -> str:
    if not value:
        return "missing"
    return f"present(length={len(value)},redacted)"


def juso_lookup(address: str, confm_key: str | None, get: Callable[..., Any]) -> dict:
    """Run the required address-code -> coordinate sequence without logging keys."""
    if not confm_key:
        return {"status": "deferred_missing_confm_key", "coordinate": None}
    common = {"confmKey": confm_key.strip(), "resultType": "json"}
    search = get(JUSO_SEARCH_URL, params={**common, "keyword": address, "currentPage": 1, "countPerPage": 10})
    search.raise_for_status()
    body = search.json()["results"]
    if body["common"]["errorCode"] != "0" or not body.get("juso"):
        return {"status": "address_not_resolved", "coordinate": None, "error_code": body["common"]["errorCode"]}
    matches = [row for row in body["juso"] if row.get("roadAddr") == address or row.get("roadAddrPart1") == address]
    if len(matches) != 1:
        return {"status": "deferred_ambiguous_address", "coordinate": None, "match_count": len(matches)}
    row = matches[0]
    keys = ("admCd", "rnMgtSn", "udrtYn", "buldMnnm", "buldSlno")
    coord = get(JUSO_COORD_URL, params={**common, **{key: row[key] for key in keys}})
    coord.raise_for_status()
    result = coord.json()["results"]
    points = result.get("juso") or []
    if result["common"]["errorCode"] != "0" or len(points) != 1:
        return {"status": "coordinate_not_resolved", "coordinate": None, "error_code": result["common"]["errorCode"]}
    point = points[0]
    lon, lat = epsg5179_to_wgs84(float(point["entX"]), float(point["entY"]))
    return {
        "status": "official_address_anchor_resolved",
        "address_codes": {key: row[key] for key in keys},
        "coordinate": {"source_x": float(point["entX"]), "source_y": float(point["entY"]), "source_crs": "EPSG:5179", "lon": lon, "lat": lat, "target_crs": "EPSG:4326"},
    }


def epsg5179_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """Inverse Transverse Mercator for Korea 2000 / Unified CS (EPSG:5179)."""
    a, inv_f, k0 = 6378137.0, 298.257222101, 0.9996
    lon0, lat0, false_e, false_n = math.radians(127.5), math.radians(38.0), 1_000_000.0, 2_000_000.0
    f = 1 / inv_f
    e2 = f * (2 - f)
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))

    def meridional(phi: float) -> float:
        return a * ((1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256) * phi
            - (3 * e2 / 8 + 3 * e2**2 / 32 + 45 * e2**3 / 1024) * math.sin(2 * phi)
            + (15 * e2**2 / 256 + 45 * e2**3 / 1024) * math.sin(4 * phi)
            - (35 * e2**3 / 3072) * math.sin(6 * phi))

    m = meridional(lat0) + (y - false_n) / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256))
    phi1 = mu + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu) + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu) + 151 * e1**3 / 96 * math.sin(6 * mu) + 1097 * e1**4 / 512 * math.sin(8 * mu)
    ep2 = e2 / (1 - e2)
    c1, t1 = ep2 * math.cos(phi1) ** 2, math.tan(phi1) ** 2
    n1 = a / math.sqrt(1 - e2 * math.sin(phi1) ** 2)
    r1 = a * (1 - e2) / (1 - e2 * math.sin(phi1) ** 2) ** 1.5
    d = (x - false_e) / (n1 * k0)
    lat = phi1 - n1 * math.tan(phi1) / r1 * (d**2 / 2 - (5 + 3*t1 + 10*c1 - 4*c1**2 - 9*ep2) * d**4 / 24 + (61 + 90*t1 + 298*c1 + 45*t1**2 - 252*ep2 - 3*c1**2) * d**6 / 720)
    lon = lon0 + (d - (1 + 2*t1 + c1) * d**3 / 6 + (5 - 2*c1 + 28*t1 - 3*c1**2 + 8*ep2 + 24*t1**2) * d**5 / 120) / math.cos(phi1)
    return round(math.degrees(lon), 8), round(math.degrees(lat), 8)


def validate_building_hub_response(status_code: int, payload: dict) -> dict:
    header = payload.get("response", {}).get("header", {})
    return {"http_status": status_code, "result_code": str(header.get("resultCode", "")), "authenticated": status_code == 200 and str(header.get("resultCode")) == "00"}
