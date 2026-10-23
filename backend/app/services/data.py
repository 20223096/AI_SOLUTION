import json
import copy
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.models.domain import ConstructionNotice, Equipment, Receptor


def _load(name: str):
    return json.loads((get_settings().data_dir / name).read_text(encoding="utf-8"))


@lru_cache
def scenarios() -> dict:
    raw = _load("poc_scenario.json")
    result = {x["id"]: x for x in raw}
    experiment_path = get_settings().data_dir / "experiment_scenarios.json"
    if experiment_path.exists():
        for overlay in json.loads(experiment_path.read_text(encoding="utf-8")):
            merged = copy.deepcopy(result[overlay["base_scenario_id"]])
            merged["id"] = overlay["id"]
            merged["title"] = overlay["title"]
            merged["expected_feasibility"] = overlay["expected_feasibility"]
            merged["notice"]["id"] = f"{merged['notice']['id']}-{overlay['id']}"
            merged["notice"]["constraints"].update(overlay.get("constraints", {}))
            merged["settings"] = overlay.get("settings", {})
            merged["source_provenance"] = overlay.get("source_provenance", {})
            result[overlay["id"]] = merged
    return result


def get_scenario(scenario_id: str) -> dict:
    try:
        raw = scenarios()[scenario_id]
    except KeyError as exc:
        raise KeyError(f"unknown scenario: {scenario_id}") from exc
    result = dict(raw)
    result["notice"] = ConstructionNotice.model_validate(raw["notice"])
    result["equipment"] = [Equipment.model_validate(x) for x in raw["equipment"]]
    result["receptors"] = [Receptor.model_validate(x) for x in raw["receptors"]]
    return result


def load_json_rows(name: str) -> list[dict]:
    return _load(name)


def load_csv_rows(path: str | Path) -> list[dict]:
    import csv
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))
