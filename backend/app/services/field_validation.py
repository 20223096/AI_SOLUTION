from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from app.models.domain import FieldObservation, FieldValidationRequest
from app.services.m1_acoustics import distance_3d_m, validation_metrics


def load_field_observations(path: str | Path) -> list[FieldObservation]:
    """Load explicit JSON observations; synthetic fallback data are never created."""
    source = Path(path)
    if source.suffix.lower() != ".json":
        raise ValueError("field observation loader currently requires JSON")
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("field observation JSON must be a list")
    return [FieldObservation.model_validate(row) for row in payload]


def evaluate_field_validation(request: FieldValidationRequest) -> dict:
    if not request.observations:
        return {
            "validation_status": "not_evaluable", "reason": "no field observations",
            "mae": None, "rmse": None, "bias": None,
            "receptor_errors": [], "equipment_errors": [], "alignment_failures": [],
        }
    predictions = {(x.receptor_id, x.start, x.end): x for x in request.predictions}
    aligned, failures = [], []
    for observation in request.observations:
        prediction = predictions.get((observation.receptor_id, observation.start, observation.end))
        if prediction is None:
            failures.append({"observation_id": observation.id, "reason": "time_or_receptor_mismatch"})
            continue
        if prediction.acoustic_scope != observation.acoustic_scope:
            failures.append({"observation_id": observation.id, "reason": "acoustic_scope_mismatch"})
            continue
        try:
            separation = distance_3d_m(observation.receptor_position, prediction.receptor_position)
        except ValueError as exc:
            failures.append({"observation_id": observation.id, "reason": "crs_mismatch", "detail": str(exc)})
            continue
        if separation > 0.01:
            failures.append({"observation_id": observation.id, "reason": "receptor_position_mismatch", "distance_m": separation})
            continue
        aligned.append((observation, prediction))
    if not aligned:
        return {
            "validation_status": "not_evaluable", "reason": "no aligned observation/prediction pairs",
            "mae": None, "rmse": None, "bias": None,
            "receptor_errors": [], "equipment_errors": [], "alignment_failures": failures,
        }
    overall = validation_metrics([p.predicted_laeq_dba for _, p in aligned], [o.laeq_dba for o, _ in aligned])
    by_receptor = defaultdict(list)
    by_equipment = defaultdict(list)
    for observation, prediction in aligned:
        by_receptor[observation.receptor_id].append((prediction.predicted_laeq_dba, observation.laeq_dba))
        active = sorted(key for key, value in observation.equipment_active.items() if value)
        for equipment_id in active:
            if equipment_id in prediction.equipment_ids:
                by_equipment[equipment_id].append((prediction.predicted_laeq_dba, observation.laeq_dba))
    receptor_errors = [{"receptor_id": key, **validation_metrics([x[0] for x in values], [x[1] for x in values])} for key, values in sorted(by_receptor.items())]
    equipment_errors = [{"equipment_id": key, **validation_metrics([x[0] for x in values], [x[1] for x in values])} for key, values in sorted(by_equipment.items())]
    return {
        **overall, "aligned_sample_count": len(aligned),
        "receptor_errors": receptor_errors, "equipment_errors": equipment_errors,
        "alignment_failures": failures,
        "alignment_requirements": ["same receptor id", "same start/end", "same LAeq_dBA metric", "same acoustic scope", "same CRS and position within 0.01m"],
    }
