import csv
import json
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings


@lru_cache
def profile_catalog() -> dict[str, dict]:
    path = get_settings().data_dir / "background_profiles.json"
    values = json.loads(path.read_text(encoding="utf-8"))
    return {value["id"]: value for value in values}


def list_profiles() -> list[dict]:
    return list(profile_catalog().values())


def profile_level(profile_id: str, moment) -> tuple[float | None, dict, list[str]]:
    try:
        profile = profile_catalog()[profile_id]
    except KeyError as exc:
        raise ValueError(f"unknown background profile: {profile_id}") from exc
    if not profile["calculation_eligible"]:
        raise ValueError(f"profile {profile_id} is analysis-only and cannot be used for acoustic synthesis")
    day_type = "weekend" if moment.weekday() >= 5 else "weekday"
    value = next((x for x in profile["hourly_values"] if x["day_type"] == day_type and x["hour"] == moment.hour), None)
    if value is None:
        return None, profile["source_metadata"], [f"{profile_id}: no representative value for {day_type} hour {moment.hour}"]
    metadata = profile["source_metadata"] | {"profile_id": profile_id, "observation_period": profile["observation_period"], "metric": profile["metric"], "representative_observation_count": value["observation_count"]}
    return float(value["representative_db"]), metadata, list(profile.get("quality_warnings", []))
