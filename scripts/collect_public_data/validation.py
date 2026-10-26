from __future__ import annotations

from datetime import date, time
from math import asin, cos, hypot, radians, sin, sqrt


def pagination_ranges(total_count: int, page_size: int = 1000) -> list[tuple[int, int]]:
    if total_count < 0 or page_size < 1:
        raise ValueError("invalid pagination values")
    return [(start, min(start + page_size - 1, total_count)) for start in range(1, total_count + 1, page_size)]


def require_seoul_response_shape(payload: dict, service: str) -> list[dict]:
    block = payload.get(service)
    if not isinstance(block, dict) or not isinstance(block.get("row", []), list) or "list_total_count" not in block:
        raise ValueError(f"invalid Seoul Open Data response for {service}")
    return block.get("row", [])


def deduplicate_events(rows: list[dict]) -> list[dict]:
    output, seen = [], set()
    for row in rows:
        key = (row.get("name"), row.get("event_start"), row.get("event_end"), row.get("location"))
        if key not in seen:
            seen.add(key); output.append(row)
    return output


def validate_acoustic_unit(unit: str) -> str:
    if unit not in {"Lw_dBA", "Lp_dBA"}:
        raise ValueError("acoustic unit must explicitly be Lw_dBA or Lp_dBA")
    return unit


def split_project_and_work_time(row: dict) -> dict:
    """Preserve project dates separately; absent daily work times remain absent."""
    return {
        "project_start_date": row.get("project_start_date"),
        "project_end_date": row.get("project_end_date"),
        "work_start_time": row.get("work_start_time") or None,
        "work_end_time": row.get("work_end_time") or None,
    }


def split_event_date_and_time(value: str) -> tuple[str, str | None]:
    parts = value.strip().split()
    return (parts[0], parts[1][:5]) if len(parts) > 1 else (parts[0], None)


def geodesic_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    for lat, lon in ((lat1, lon1), (lat2, lon2)):
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError("coordinates must be WGS84 latitude/longitude")
    radius = 6_371_008.8
    p1, p2 = radians(lat1), radians(lat2)
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(p1) * cos(p2) * sin(dlon / 2) ** 2
    return 2 * radius * asin(sqrt(a))


def point_to_segment_distance_m(
    point_lat: float,
    point_lon: float,
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
) -> float:
    """Approximate WGS84 point-to-segment distance in a local tangent plane."""
    for lat, lon in ((point_lat, point_lon), (start_lat, start_lon), (end_lat, end_lon)):
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError("coordinates must be WGS84 latitude/longitude")
    origin_lat = radians((point_lat + start_lat + end_lat) / 3)
    radius = 6_371_008.8
    def xy(lat: float, lon: float) -> tuple[float, float]:
        return radius * radians(lon - point_lon) * cos(origin_lat), radius * radians(lat - point_lat)
    ax, ay = xy(start_lat, start_lon)
    bx, by = xy(end_lat, end_lon)
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return hypot(ax, ay)
    t = max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
    return hypot(ax + t * dx, ay + t * dy)


def collection_time(row: dict) -> tuple[str, str] | None:
    start, end = row.get("vehicle_collection_start_time"), row.get("vehicle_collection_end_time")
    return (start, end) if start and end else None
