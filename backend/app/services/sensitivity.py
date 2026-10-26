from datetime import datetime


def time_weight(moment: datetime) -> tuple[str, float]:
    minute = moment.hour * 60 + moment.minute
    if minute >= 22 * 60 or minute < 5 * 60:
        return "night", 2.0
    if minute < 7 * 60 or minute >= 18 * 60:
        return "evening_morning", 1.5
    return "day", 1.0


def sensitivity(moment: datetime, receptor_type: str, exam_period: bool = False, weekend_rest: bool = False, policy_version: str = "legacy_v1", experimental_context_multiplier: float | None = None) -> dict:
    period, base = time_weight(moment)
    adjustments = {}
    if exam_period and receptor_type == "university":
        adjustments["university_exam"] = 0.5
    if weekend_rest and receptor_type == "residential":
        adjustments["weekend_residential_rest"] = 0.3
    if receptor_type in {"hospital", "school"}:
        adjustments["hospital_or_school_within_assumed_300m"] = 0.5
    if policy_version == "legacy_v1":
        weight = base + sum(adjustments.values())
        return {"time_period": period, "base_weight": base, "adjustments": adjustments, "weight": weight, "is_sensitive_time": weight > 1, "weight_status": "assumed", "status": "assumed"}
    elif policy_version == "prd_max_v2_1_experimental":
        if experimental_context_multiplier not in {1.1, 1.3, 1.5}:
            raise ValueError("experimental_context_multiplier must be one of 1.1, 1.3, 1.5")
        context_applies = receptor_type in {"hospital", "school"} or (exam_period and receptor_type == "university") or (weekend_rest and receptor_type == "residential")
        weight = max(base, experimental_context_multiplier if context_applies else 1.0)
        adjustments = {"experimental_context_multiplier": experimental_context_multiplier} if context_applies else {}
        rule = "maximum_single_multiplier"
    else:
        raise ValueError(f"unknown sensitivity policy: {policy_version}")
    return {"time_period": period, "base_weight": base, "adjustments": adjustments, "weight": weight, "is_sensitive_time": weight > 1, "weight_status": "assumed", "status": "assumed", "policy_version": policy_version, "overlap_rule": rule}
