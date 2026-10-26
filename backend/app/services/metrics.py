from datetime import date, time

from app.models.domain import ImpactRequest, ScheduleMetrics, TaskAssignment
from app.services.acoustics import reference_energy_exposure
from app.services.impact import calculate_impact
from app.services.prediction import predict


def schedule_metrics(scenario_id: str, day: date, assignments: list[TaskAssignment], threshold: float = 65.0, sensitivity_enabled: bool = True, background_profile: str = "assumed_demo", sensitivity_policy: str = "legacy_v1", experimental_context_multiplier: float | None = None) -> ScheduleMetrics:
    rows = predict(scenario_id, day, assignments, sensitivity_enabled=sensitivity_enabled, background_profile=background_profile, sensitivity_policy=sensitivity_policy, experimental_context_multiplier=experimental_context_multiplier)["predictions"]
    # Aggregate conservatively across receptors: one value per slot, taking maximum.
    by_slot = {}
    for row in rows:
        level = row["total_estimated_db"]
        if level is None:
            continue
        previous = by_slot.get(row["slot_start"], {"total":0,"baseline":0,"weight":1,"active":False})
        by_slot[row["slot_start"]] = {"total":max(previous["total"], level), "baseline":max(previous["baseline"], row["existing_environment_db"] or 0), "weight":max(previous["weight"], row["sensitivity"]["weight"]), "active":previous["active"] or bool(row["active_task_ids"])}
    high_runs, quiet_runs, project_runs, impacts = [], [], [], []
    current_high = current_quiet = current_project = 0
    sensitive_high = additional_high = sensitive_project = 0
    for values in by_slot.values():
        level, weight = values["total"], values["weight"]
        high = level >= threshold
        current_high = current_high + 15 if high else 0
        current_quiet = current_quiet + 15 if not high else 0
        current_project = current_project + 15 if values["active"] else 0
        high_runs.append(current_high); quiet_runs.append(current_quiet); project_runs.append(current_project)
        if high and weight > 1:
            sensitive_high += 15
        if high and values["baseline"] < threshold:
            additional_high += 15
        if values["active"] and weight > 1:
            sensitive_project += 15
        impacts.append(calculate_impact(ImpactRequest(total_noise_db=level, threshold_db=threshold, duration_minutes=15 if high else 0, continuous_minutes=current_high, sensitivity_weight=weight))["score"])
    # Resident cost sums every receptor-slot so receptor-specific sensitivity is retained.
    receptor_impacts, incremental_impacts = [], []
    sensitive_receptor_minutes = 0
    weighted_sensitive_receptor_minutes = 0.0
    project_receptor_minutes = 0
    energy_exposure = 0.0
    cumulative_delta_db_minutes = 0.0
    existing_overlap_receptor_minutes = 0
    saturation_count = 0
    for row in rows:
        level = row["total_estimated_db"]
        if level is None:
            continue
        receptor_impacts.append(row["total_impact"])
        incremental_impacts.append(row["incremental_impact"])
        if row["active_task_ids"] and row["sensitivity"]["weight"] > 1:
            sensitive_receptor_minutes += 15
            weighted_sensitive_receptor_minutes += 15 * row["sensitivity"]["weight"]
        if row["new_project_contribution_db"] is not None:
            # Linear construction-only energy relative to a 65 dB reference,
            # integrated over minutes. Background/event energy is not included.
            project_receptor_minutes += 15
            energy_exposure += reference_energy_exposure(row["new_project_contribution_db"], 15, threshold)
            cumulative_delta_db_minutes += row["delta_total_db"] * 15
        if row["active_task_ids"] and row["existing_event_ids"]:
            existing_overlap_receptor_minutes += 15
        saturation_count += int(row["impact_saturation"]["level_component_at_ceiling"] or row["impact_saturation"]["incremental_zero_despite_physical_increase"])
    absolute = round(sum(receptor_impacts), 2)
    incremental = round(sum(incremental_impacts), 2)
    active_minutes = sum(15 for values in by_slot.values() if values["active"])
    analysis_minutes = len(by_slot) * 15
    return ScheduleMetrics(max_continuous_high_noise_minutes=max(high_runs, default=0), longest_quiet_window_minutes=max(quiet_runs, default=0), sensitive_high_noise_minutes=sensitive_high, max_impact_score=max(receptor_impacts, default=0), total_impact_score=absolute, absolute_impact_cost=absolute, incremental_impact_cost=incremental, new_project_additional_high_noise_minutes=additional_high, sensitive_new_project_exposure_minutes=sensitive_project, sensitive_new_project_receptor_minutes=sensitive_receptor_minutes, sensitivity_weighted_new_project_receptor_minutes=round(weighted_sensitive_receptor_minutes, 2), new_project_receptor_minutes=project_receptor_minutes, new_project_inactive_minutes=analysis_minutes-active_minutes, max_continuous_new_project_minutes=max(project_runs, default=0), new_project_energy_exposure_65db_ref_minutes=round(energy_exposure, 6), cumulative_delta_db_minutes=round(cumulative_delta_db_minutes, 2), existing_noise_overlap_receptor_minutes=existing_overlap_receptor_minutes, max_total_estimated_db=max((row["total_estimated_db"] for row in rows if row["total_estimated_db"] is not None), default=0), max_new_project_contribution_db=max((row["new_project_contribution_db"] for row in rows if row["new_project_contribution_db"] is not None), default=0), saturation_slot_count=saturation_count)


def compare(scenario_id: str, day: date, before: list[TaskAssignment], after: list[TaskAssignment], sensitivity_enabled: bool = True, background_profile: str = "assumed_demo") -> dict:
    a, b = schedule_metrics(scenario_id, day, before, sensitivity_enabled=sensitivity_enabled, background_profile=background_profile), schedule_metrics(scenario_id, day, after, sensitivity_enabled=sensitivity_enabled, background_profile=background_profile)
    before_starts = {x.task_id: x.start for x in before}
    task_changes = {x.task_id: abs(int((x.start - before_starts[x.task_id]).total_seconds() / 60)) for x in after if x.task_id in before_starts}
    change = sum(task_changes.values())
    project_start_change = abs(int((min(x.start for x in after) - min(x.start for x in before)).total_seconds() / 60)) if before and after else 0
    project_end_change = abs(int((max(x.end for x in after) - max(x.end for x in before)).total_seconds() / 60)) if before and after else 0
    b.schedule_change_minutes = change
    b.project_start_change_minutes = project_start_change
    b.project_end_change_minutes = project_end_change
    return {"before": a, "after": b, "delta": {k: round(getattr(b, k) - getattr(a, k), 2) for k in ScheduleMetrics.model_fields}, "schedule_change_details": {"definition": "after relative to supplied before assignments", "task_start_shift_minutes": task_changes, "total_task_start_shift_minutes": change, "project_start_shift_minutes": project_start_change, "project_end_shift_minutes": project_end_change, "before_project_end": max((x.end for x in before), default=None), "after_project_end": max((x.end for x in after), default=None)}, "comparison_basis": {"date": day, "slot_minutes": 15, "threshold_db": 65.0, "background_profile": background_profile, "same_receptors_and_rules": True}}
