from __future__ import annotations

from datetime import date

from app.models.domain import TaskAssignment
from app.models.prd_v2_1 import PRDNoticePlanningInput
from app.services.optimizer import optimize
from app.services.timegrid import at as _at


def validate_prd_schedule(
    planning: PRDNoticePlanningInput,
    day: date,
    assignments: list[TaskAssignment],
    predecessors: dict[str, list[str]],
    equipment_by_task: dict[str, str | None],
    restoration_task_ids: set[str],
    equipment_count_by_task: dict[str, int] | None = None,
) -> dict:
    """Validate explicit PRD inputs without inventing universal work-hour rules."""
    violations: list[dict] = []
    by_task = {item.task_id: item for item in assignments}
    overall_start = _at(day, planning.total_work_window.start)
    overall_end = _at(day, planning.total_work_window.end)
    for item in assignments:
        if item.start < overall_start or item.end > overall_end:
            violations.append({"code": "outside_total_work_window", "task_id": item.task_id})

    equipment_constraints = {item.equipment_id: item for item in planning.equipment_constraints}
    equipment_count_by_task = equipment_count_by_task or {}
    scheduled_minutes_by_equipment: dict[str, int] = {}
    for task_id, equipment_id in equipment_by_task.items():
        assignment = by_task.get(task_id)
        constraint = equipment_constraints.get(equipment_id or "")
        if assignment is None or constraint is None or not constraint.permitted_time_windows:
            if assignment is None or constraint is None:
                continue
        if constraint.permitted_time_windows:
            allowed = any(
                assignment.start >= _at(day, window.start) and assignment.end <= _at(day, window.end)
                for window in constraint.permitted_time_windows
            )
            if not allowed:
                violations.append({"code": "outside_equipment_time_window", "task_id": task_id, "equipment_id": equipment_id})
        scheduled_minutes_by_equipment[equipment_id] = scheduled_minutes_by_equipment.get(equipment_id, 0) + int((assignment.end - assignment.start).total_seconds() / 60)
        count = equipment_count_by_task.get(task_id)
        if count is not None and constraint.max_daily_count is not None and count > constraint.max_daily_count:
            violations.append({"code": "equipment_daily_count_exceeded", "task_id": task_id, "equipment_id": equipment_id, "count": count, "maximum": constraint.max_daily_count})
    for equipment_id, constraint in equipment_constraints.items():
        actual = scheduled_minutes_by_equipment.get(equipment_id, 0)
        if actual != constraint.required_usage_minutes:
            violations.append({"code": "equipment_required_usage_mismatch", "equipment_id": equipment_id, "scheduled_minutes": actual, "required_minutes": constraint.required_usage_minutes})

    if planning.road_excavation and planning.road_occupancy_permit_window is not None:
        permit_start = _at(day, planning.road_occupancy_permit_window.start)
        permit_end = _at(day, planning.road_occupancy_permit_window.end)
        for item in assignments:
            if item.start < permit_start or item.end > permit_end:
                violations.append({"code": "outside_road_occupancy_permit", "task_id": item.task_id})

    for fixed in planning.fixed_tasks:
        assignment = by_task.get(fixed.task_id)
        if assignment is None:
            violations.append({"code": "fixed_task_missing", "task_id": fixed.task_id})
            continue
        if fixed.fixed_start is not None and assignment.start != _at(day, fixed.fixed_start):
            violations.append({"code": "fixed_task_start_changed", "task_id": fixed.task_id})
        if fixed.fixed_end is not None and assignment.end != _at(day, fixed.fixed_end):
            violations.append({"code": "fixed_task_end_changed", "task_id": fixed.task_id})

    for task_id, required in predecessors.items():
        assignment = by_task.get(task_id)
        if assignment is None:
            continue
        for predecessor_id in required:
            predecessor = by_task.get(predecessor_id)
            if predecessor is None or predecessor.end > assignment.start:
                violations.append({"code": "predecessor_violation", "task_id": task_id, "predecessor_id": predecessor_id})

    if planning.same_day_restoration_required:
        for task_id in sorted(restoration_task_ids):
            restoration = by_task.get(task_id)
            if restoration is None:
                violations.append({"code": "same_day_restoration_missing", "task_id": task_id})
            elif restoration.end.date() != day:
                violations.append({"code": "same_day_restoration_violation", "task_id": task_id})

    if planning.project_completion_date is not None and any(item.end.date() > planning.project_completion_date for item in assignments):
        violations.append({"code": "project_completion_date_exceeded"})
    return {"feasible": not violations, "violations": violations, "policy_version": "prd_v2_1_explicit_input_only"}


def sensitivity_policy_experiment(scenario_id: str, day: date, background_profile: str, multipliers=(1.1, 1.3, 1.5)) -> dict:
    baseline = optimize(scenario_id, day, background_profile=background_profile)
    baseline_ids = [item["candidate"].id for item in baseline.get("recommended_options", [])]
    baseline_ranking = [item.id for item in sorted(baseline.get("valid_candidates", []), key=lambda x: (x.objective_values["resident_cost"], x.objective_values["change_cost"], x.id))]
    baseline_metrics = baseline.get("recommended_options", [{}])[0].get("candidate")
    baseline_metrics = baseline_metrics.metrics if baseline_metrics is not None else None
    rows = []
    for multiplier in multipliers:
        result = optimize(
            scenario_id,
            day,
            background_profile=background_profile,
            sensitivity_policy="prd_max_v2_1_experimental",
            experimental_context_multiplier=multiplier,
        )
        recommended = result.get("recommended_options", [])
        recommended_ids = [item["candidate"].id for item in recommended]
        ranking = [item.id for item in sorted(result.get("valid_candidates", []), key=lambda x: (x.objective_values["resident_cost"], x.objective_values["change_cost"], x.id))]
        metrics = recommended[0]["candidate"].metrics if recommended else None
        rows.append({
            "multiplier": multiplier,
            "recommended_candidate_ids": recommended_ids,
            "recommendation_changed": recommended_ids != baseline_ids,
            "pareto_candidate_ids": [item.id for item in result.get("pareto_candidates", [])],
            "candidate_ranking": ranking,
            "ranking_changed": ranking != baseline_ranking,
            "recommended_metrics": [item["candidate"].metrics.model_dump(mode="json") for item in recommended],
            "comparison_to_legacy_recommendation": None if metrics is None or baseline_metrics is None else {
                "sensitive_exposure_minutes_delta": metrics.sensitive_new_project_receptor_minutes - baseline_metrics.sensitive_new_project_receptor_minutes,
                "weighted_sensitive_exposure_delta": round(metrics.sensitivity_weighted_new_project_receptor_minutes - baseline_metrics.sensitivity_weighted_new_project_receptor_minutes, 6),
                "schedule_change_minutes_delta": metrics.schedule_change_minutes - baseline_metrics.schedule_change_minutes,
                "incremental_impact_cost_delta": round(metrics.incremental_impact_cost - baseline_metrics.incremental_impact_cost, 6),
            },
        })
    return {
        "policy_version": "prd_max_v2_1_experimental",
        "status": "simulated",
        "scenario_id": scenario_id,
        "analysis_date": day,
        "background_profile": background_profile,
        "baseline_policy": "legacy_v1_additive",
        "baseline_recommended_candidate_ids": baseline_ids,
        "baseline_candidate_ranking": baseline_ranking,
        "cases": rows,
        "disclaimer": "Sensitivity multipliers are planning assumptions, not validated harm coefficients.",
    }
