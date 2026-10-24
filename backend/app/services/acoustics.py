import math
from collections.abc import Iterable


def sound_power_to_pressure(lw_db: float, distance_m: float, correction_db: float = 0.0) -> float:
    """Free-field point source: Lp=Lw-10log10(4πr²)+C; C defaults to 0 dB."""
    if distance_m <= 0:
        raise ValueError("distance_m must be greater than zero")
    return lw_db - 10 * math.log10(4 * math.pi * distance_m**2) + correction_db


def energy_sum(levels_db: Iterable[float]) -> float | None:
    values = list(levels_db)
    if not values:
        return None
    return 10 * math.log10(sum(10 ** (x / 10) for x in values))


def reference_energy_exposure(level_db: float, duration_minutes: float, reference_db: float = 65.0) -> float:
    """Linear sound-exposure ratio integrated over minutes relative to reference_db."""
    if duration_minutes < 0:
        raise ValueError("duration_minutes must be non-negative")
    return 10 ** ((level_db - reference_db) / 10) * duration_minutes


def source_noise(equipment: dict, catalog: list[dict]) -> tuple[float | None, dict]:
    model = equipment.get("model_name")
    category = equipment["category"]
    for status, predicate in (
        ("verified model", lambda x: model and x.get("model_name") == model and x["source_metadata"]["status"] == "verified_public"),
        ("verified category", lambda x: x["category"] == category and x["source_metadata"]["status"] == "verified_public"),
    ):
        hit = next((x for x in catalog if predicate(x)), None)
        if hit:
            return hit.get("sound_power_level_db"), hit["source_metadata"] | {"selection": status}
    if equipment.get("sound_power_level_db") is not None:
        return equipment["sound_power_level_db"], equipment["source_metadata"] | {"selection": "explicit scenario value"}
    return None, {"status": "missing", "note": f"No acoustic value for {category}", "unit": None}
