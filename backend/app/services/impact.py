from app.models.domain import ImpactRequest


WEIGHTS = {"level": 0.45, "duration": 0.20, "continuous": 0.15, "sensitivity": 0.15, "cumulative": 0.05}


def _score(total_noise_db: float, threshold_db: float, duration_minutes: int, continuous_minutes: int, sensitivity_weight: float, cumulative_burden: float) -> dict:
    # Configurable experimental score; every component is clipped to [0,1].
    components = {
        "level": min(1.0, max(0.0, (total_noise_db - threshold_db + 10) / 30)),
        "duration": min(1.0, duration_minutes / 480),
        "continuous": min(1.0, continuous_minutes / 180),
        # Sensitivity scales exposure; it does not create impact for a quiet/background-only slot.
        "sensitivity": min(1.0, max(0.0, (sensitivity_weight - 1) / 1.5)) * min(1.0, max(0.0, (total_noise_db - threshold_db + 10) / 30)),
        "cumulative": min(1.0, cumulative_burden / 100),
    }
    score = 100 * sum(WEIGHTS[k] * v for k, v in components.items())
    return {"score": round(min(100, max(0, score)), 2), "components": components}


def calculate_impact(value: ImpactRequest) -> dict:
    total = _score(value.total_noise_db, value.threshold_db, value.duration_minutes, value.continuous_minutes, value.sensitivity_weight, value.cumulative_burden)
    result = {**total, "weights": WEIGHTS, "classification": "experimental_impact_index_not_legal_compliance"}
    if value.baseline_noise_db is not None:
        baseline = _score(value.baseline_noise_db, value.threshold_db, value.duration_minutes, value.continuous_minutes, value.sensitivity_weight, value.cumulative_burden)
        incremental = max(0.0, round(total["score"] - baseline["score"], 2))
        result.update({"baseline_score": baseline["score"], "incremental_score": incremental, "saturation": {"score_at_ceiling": total["score"] >= 100, "level_component_at_ceiling": total["components"]["level"] >= 1, "incremental_zero_despite_increase": value.total_noise_db > value.baseline_noise_db and incremental == 0}})
    return result
