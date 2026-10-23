from __future__ import annotations

import csv
import json
from datetime import date
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROCESSED = ROOT / "data" / "processed"
MANIFEST = ROOT / "data" / "reports" / "public_data_manifest.json"


def _csv(name: str) -> list[dict]:
    path = PROCESSED / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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
        "academic_calendar": _csv("academic_calendar.csv"),
        "waste_collection": _csv("waste_collection.csv"),
        "land_use": _csv("land_use.csv"),
        "policy": {
            "schedule_only_events_are_energy_summed": False,
            "coordinate_crs_required_for_distance": True,
            "unverified_values_used_for_acoustic_calculation": False,
            "official_equipment_requires_model_match": True,
            "spatial_distance_is_horizontal_not_propagation_path": True,
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
    return [row for row in rows if row.get("noise_db") and row.get("start_time") and row.get("end_time") and row.get("status") in {"processed", "integrated"}]
