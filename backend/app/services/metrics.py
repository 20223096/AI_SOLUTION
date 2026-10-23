from datetime import date, time

from app.models.domain import ImpactRequest, ScheduleMetrics, TaskAssignment
from app.services.impact import calculate_impact
from app.services.prediction import predict


def schedule_metrics(scenario_id: str, day: date, assignments: list[TaskAssignment], threshold: float = 65.0, sensitivity_enabled: bool = True) -> ScheduleMetrics:
    rows = predict(scenario_id, day, assignments, sensitivity_enabled=sensitivity_enabled)["predictions"]
    # Aggregate conservatively across receptors: one value per slot, taking maximum.
    by_slot, total_impact = {}, 0.0
    for row in rows:
        level = row["total_estimated_db"]
        if level is None:
            continue
        by_slot[row["slot_start"]] = max(by_slot.get(row["slot_start"], (0, 1))[0], level), max(by_slot.get(row["slot_start"], (0, 1))[1], row["sensitivity"]["weight"])
    high_runs, quiet_runs, impacts = [], [], []
    current_high = current_quiet = 0
    sensitive_high = 0
    for level, weight in by_slot.values():
        high = level >= threshold
        current_high = current_high + 15 if high else 0
        current_quiet = current_quiet + 15 if not high else 0
        high_runs.append(current_high); quiet_runs.append(current_quiet)
        if high and weight > 1:
            sensitive_high += 15
        impacts.append(calculate_impact(ImpactRequest(total_noise_db=level, threshold_db=threshold, duration_minutes=15 if high else 0, continuous_minutes=current_high, sensitivity_weight=weight))["score"])
    # Resident cost sums every receptor-slot so receptor-specific sensitivity is retained.
    receptor_impacts = []
    for row in rows:
        level = row["total_estimated_db"]
        if level is None:
            continue
        receptor_impacts.append(calculate_impact(ImpactRequest(total_noise_db=level, threshold_db=threshold, duration_minutes=15 if level >= threshold else 0, continuous_minutes=15 if level >= threshold else 0, sensitivity_weight=row["sensitivity"]["weight"]))["score"])
    return ScheduleMetrics(max_continuous_high_noise_minutes=max(high_runs, default=0), longest_quiet_window_minutes=max(quiet_runs, default=0), sensitive_high_noise_minutes=sensitive_high, max_impact_score=max(receptor_impacts, default=0), total_impact_score=round(sum(receptor_impacts), 2))


def compare(scenario_id: str, day: date, before: list[TaskAssignment], after: list[TaskAssignment], sensitivity_enabled: bool = True) -> dict:
    a, b = schedule_metrics(scenario_id, day, before, sensitivity_enabled=sensitivity_enabled), schedule_metrics(scenario_id, day, after, sensitivity_enabled=sensitivity_enabled)
    before_starts = {x.task_id: x.start for x in before}
    change = sum(abs(int((x.start - before_starts[x.task_id]).total_seconds() / 60)) for x in after if x.task_id in before_starts)
    b.schedule_change_minutes = change
    return {"before": a, "after": b, "delta": {k: round(getattr(b, k) - getattr(a, k), 2) for k in ScheduleMetrics.model_fields}, "comparison_basis": {"date": day, "slot_minutes": 15, "threshold_db": 65.0, "same_receptors_and_rules": True}}
