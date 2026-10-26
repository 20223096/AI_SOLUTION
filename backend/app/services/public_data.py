from __future__ import annotations

import csv
import json
from datetime import date
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROCESSED = ROOT / "data" / "processed"
MANIFEST = ROOT / "data" / "reports" / "public_data_manifest.json"
OFFICIAL_CONSTRUCTION_DESIGN = PROCESSED / "official_construction_design_v1.json"


def _csv(name: str) -> list[dict]:
    path = PROCESSED / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


@lru_cache
def official_construction_design() -> dict:
    """Load official design metadata without promoting it to an acoustic scenario."""
    if not OFFICIAL_CONSTRUCTION_DESIGN.exists():
        return {}
    return json.loads(OFFICIAL_CONSTRUCTION_DESIGN.read_text(encoding="utf-8"))


def construction_design_distance_ready(segment: dict) -> bool:
    """Distance needs an actual geometry/source point, not a nominal address."""
    return bool(segment.get("geometry") or segment.get("representative_point"))


def public_catalog() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {"results": [], "processed_counts": {}}
    return {
        "manifest": manifest,
        "equipment_noise": _csv("equipment_noise.csv"),
        "construction_events": _csv("construction_events.csv"),
        "cultural_events": _csv("cultural_events.csv"),
        "receptors": _csv("receptors.csv"),
        "official_facilities": _csv("official_facilities.csv"),
        "receptor_distances": _csv("receptor_distances.csv"),
        "official_equipment_noise": _csv("official_equipment_noise.csv"),
        "official_construction_design": official_construction_design(),
        "academic_calendar": _csv("academic_calendar.csv"),
        "waste_collection": _csv("waste_collection.csv"),
        "land_use": _csv("land_use.csv"),
        "policy": {
            "schedule_only_events_are_energy_summed": False,
            "coordinate_crs_required_for_distance": True,
            "unverified_values_used_for_acoustic_calculation": False,
            "official_equipment_requires_model_match": True,
            "spatial_distance_is_horizontal_not_propagation_path": True,
            "official_design_is_acoustic_scenario": False,
            "nominal_address_is_distance_source": False,
        },
    }


def is_exam_period(day: date, institution: str) -> bool:
    for row in _csv("academic_calendar.csv"):
        if row.get("institution") != institution or row.get("event_type") != "exam" or row.get("status") != "processed":
            continue
        if date.fromisoformat(row["start_date"]) <= day <= date.fromisoformat(row["end_date"]):
            return True
    return False


def acoustic_public_events() -> list[dict]:
    """Only return records with an explicit verified acoustic level and time range."""
    rows = _csv("construction_events.csv") + _csv("cultural_events.csv")
    return [row for row in rows if row.get("noise_db") and row.get("start_time") and row.get("end_time") and row.get("status") == "verified_public"]


def calendar_overlaps(day: date) -> list[dict]:
    """Date-level public schedule context; never implies acoustic eligibility."""
    result = []
    mappings = (
        ("construction", _csv("construction_events.csv"), "project_start_date", "project_end_date", "work_start_time", "work_end_time"),
        ("cultural_event", _csv("cultural_events.csv"), "event_start_date", "event_end_date", "start_time", "end_time"),
    )
    for category, rows, start_key, end_key, time_start_key, time_end_key in mappings:
        for row in rows:
            if not row.get(start_key) or not row.get(end_key):
                continue
            if not (date.fromisoformat(row[start_key]) <= day <= date.fromisoformat(row[end_key])):
                continue
            has_times = bool(row.get(time_start_key) and row.get(time_end_key))
            has_noise = bool(row.get("noise_db"))
            acoustic_eligible = has_times and has_noise and row.get("status") == "verified_public"
            result.append({
                "event_id": row.get("event_id"), "name": row.get("name"), "category": category,
                "date_overlap": True, "time_verified": has_times, "noise_level_verified": has_noise,
                "acoustic_synthesis_eligible": acoustic_eligible,
                "start_time": row.get(time_start_key) or None, "end_time": row.get(time_end_key) or None,
                "noise_db": float(row["noise_db"]) if has_noise else None,
                "status": row.get("status"), "source_url": row.get("source_url"),
                "note": "Calendar context only" if not acoustic_eligible else "Verified normalized time and acoustic value",
            })
    return result
