from app.models.domain import ImpactRequest


WEIGHTS = {"level": 0.45, "duration": 0.20, "continuous": 0.15, "sensitivity": 0.15, "cumulative": 0.05}


def calculate_impact(value: ImpactRequest) -> dict:
    # Configurable experimental score; every component is clipped to [0,1].
    components = {
        "level": min(1.0, max(0.0, (value.total_noise_db - value.threshold_db + 10) / 30)),
        "duration": min(1.0, value.duration_minutes / 480),
        "continuous": min(1.0, value.continuous_minutes / 180),
        # Sensitivity scales exposure; it does not create impact for a quiet/background-only slot.
        "sensitivity": min(1.0, max(0.0, (value.sensitivity_weight - 1) / 1.5)) * min(1.0, max(0.0, (value.total_noise_db - value.threshold_db + 10) / 30)),
        "cumulative": min(1.0, value.cumulative_burden / 100),
    }
    score = 100 * sum(WEIGHTS[k] * v for k, v in components.items())
    return {"score": round(min(100, max(0, score)), 2), "components": components, "weights": WEIGHTS, "classification": "experimental_impact_index_not_legal_compliance"}
