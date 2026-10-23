from datetime import datetime


def time_weight(moment: datetime) -> tuple[str, float]:
    minute = moment.hour * 60 + moment.minute
    if minute >= 22 * 60 or minute < 5 * 60:
        return "night", 2.0
    if minute < 7 * 60 or minute >= 18 * 60:
        return "evening_morning", 1.5
    return "day", 1.0


def sensitivity(moment: datetime, receptor_type: str, exam_period: bool = False, weekend_rest: bool = False) -> dict:
    period, base = time_weight(moment)
    adjustments = {}
    if exam_period and receptor_type == "university":
        adjustments["university_exam"] = 0.5
    if weekend_rest and receptor_type == "residential":
        adjustments["weekend_residential_rest"] = 0.3
    if receptor_type in {"hospital", "school"}:
        adjustments["hospital_or_school_within_assumed_300m"] = 0.5
    return {"time_period": period, "base_weight": base, "adjustments": adjustments, "weight": base + sum(adjustments.values()), "status": "assumed"}
