from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ortools.sat.python import cp_model

from app.models.domain import ScheduleCandidate, SourceMetadata, TaskAssignment
from app.models.prd_v2_1 import PRDNoticePlanningInput
from app.services.data import get_scenario
from app.services.metrics import schedule_metrics
from app.services.pareto import non_dominated_multi
from app.services.prediction import default_assignments

GRID_MINUTES = 15
PARETO_AXES = ["resident_cost", "change_cost", "continuous_high_noise_cost", "existing_noise_overlap_cost"]


def _minute(value) -> int:
    return value.hour * 60 + value.minute


def _allowed_starts(task_id: str, duration: int, planning: PRDNoticePlanningInput, equipment_id: str | None) -> list[int]:
    lower = _minute(planning.total_work_window.start)
    upper = _minute(planning.total_work_window.end) - duration
    if planning.road_excavation and planning.road_occupancy_permit_window is not None:
        lower = max(lower, _minute(planning.road_occupancy_permit_window.start))
        upper = min(upper, _minute(planning.road_occupancy_permit_window.end) - duration)
    equipment = next((row for row in planning.equipment_constraints if row.equipment_id == equipment_id), None)
    windows = equipment.permitted_time_windows if equipment else []
    fixed = next((row for row in planning.fixed_tasks if row.task_id == task_id), None)
    values = []
    for start in range(lower, upper + 1, GRID_MINUTES):
        end = start + duration
        if windows and not any(start >= _minute(window.start) and end <= _minute(window.end) for window in windows):
            continue
        if fixed and fixed.fixed_start is not None and start != _minute(fixed.fixed_start):
            continue
        if fixed and fixed.fixed_end is not None and end != _minute(fixed.fixed_end):
            continue
        values.append(start)
    return values


class _Collector(cp_model.CpSolverSolutionCallback):
    def __init__(self, starts: dict[str, cp_model.IntVar], limit: int):
        super().__init__()
        self.starts = starts
        self.limit = limit
        self.solutions: list[dict[str, int]] = []
        self.limit_reached = False

    def on_solution_callback(self):
        self.solutions.append({task_id: self.value(var) for task_id, var in self.starts.items()})
        if len(self.solutions) >= self.limit:
            self.limit_reached = True
            self.stop_search()


def _candidate(scenario_id: str, day: date, starts: dict[str, int], durations: dict[str, int], candidate_index: int, *, sensitivity_enabled: bool, background_profile: str, sensitivity_policy: str, experimental_context_multiplier: float | None, include_existing_events: bool) -> ScheduleCandidate:
    midnight = datetime.combine(day, datetime.min.time(), tzinfo=ZoneInfo("Asia/Seoul"))
    assignments = [TaskAssignment(task_id=task_id, start=midnight + timedelta(minutes=start), end=midnight + timedelta(minutes=start + durations[task_id])) for task_id, start in sorted(starts.items())]
    metrics = schedule_metrics(scenario_id, day, assignments, sensitivity_enabled=sensitivity_enabled, background_profile=background_profile, sensitivity_policy=sensitivity_policy, experimental_context_multiplier=experimental_context_multiplier, include_existing_events=include_existing_events)
    original = default_assignments(get_scenario(scenario_id), day)
    original_starts = {row.task_id: row.start for row in original}
    changes = {row.task_id: abs(int((row.start - original_starts[row.task_id]).total_seconds() / 60)) if row.task_id in original_starts else 0 for row in assignments}
    metrics.schedule_change_minutes = sum(changes.values())
    metrics.project_start_change_minutes = abs(int((min(row.start for row in assignments) - min(row.start for row in original)).total_seconds() / 60))
    metrics.project_end_change_minutes = abs(int((max(row.end for row in assignments) - max(row.end for row in original)).total_seconds() / 60))
    return ScheduleCandidate(
        id=f"cp-sat-{candidate_index:03d}", task_assignments=assignments, feasibility=True, metrics=metrics,
        objective_values={"resident_cost": metrics.incremental_impact_cost, "change_cost": float(metrics.schedule_change_minutes), "continuous_high_noise_cost": float(metrics.max_continuous_high_noise_minutes), "existing_noise_overlap_cost": float(metrics.existing_noise_overlap_receptor_minutes), "absolute_impact_cost": metrics.absolute_impact_cost, "incremental_impact_cost": metrics.incremental_impact_cost},
        schedule_change_details={"definition": "sum of absolute per-task start shifts", "task_start_shift_minutes": changes, "total_task_start_shift_minutes": metrics.schedule_change_minutes, "project_start_shift_minutes": metrics.project_start_change_minutes, "project_end_shift_minutes": metrics.project_end_change_minutes, "predecessor_order_preserved": True, "resource_conflicts": []},
        provenance=SourceMetadata(status="derived", source="OR-Tools CP-SAT feasible-solution enumeration", note="Pareto optimal only within the explored solution set; acoustic objectives are evaluated after CP-SAT feasibility enumeration"),
    )


def _empty_result(reasons: list[str], limit: int) -> dict[str, Any]:
    return {"optimization_status": "infeasible", "solver": "ortools_cp_sat", "candidates": [], "pareto_candidates": [], "explored_candidate_count": 0, "pareto_candidate_count": 0, "solution_limit": limit, "solution_limit_reached": False, "search_complete": True, "global_optimality_guaranteed": False, "pareto_axes": PARETO_AXES, "infeasibility_reasons": reasons}


def optimize_advanced(scenario_id: str, day: date, planning: PRDNoticePlanningInput, predecessors: dict[str, list[str]], equipment_by_task: dict[str, str | None], restoration_task_ids: set[str], task_duration_by_task: dict[str, int] | None = None, *, sensitivity_enabled: bool = True, background_profile: str = "road_traffic_observed_profile", sensitivity_policy: str = "legacy_v1", experimental_context_multiplier: float | None = None, include_existing_events: bool = True, solution_limit: int = 2000) -> dict[str, Any]:
    scenario = get_scenario(scenario_id)
    known_tasks = {task.id: task for task in scenario["notice"].tasks}
    supplied_durations = task_duration_by_task or {}
    unknown_task_ids = sorted(set(supplied_durations) - set(known_tasks))
    tasks = [known_tasks[task_id] for task_id in supplied_durations if task_id in known_tasks]
    durations = {task.id: supplied_durations[task.id] for task in tasks}
    reasons = []
    if not supplied_durations:
        tasks = [task for task in scenario["notice"].tasks if task.duration_minutes is not None]
        durations = {task.id: task.duration_minutes for task in tasks}
    if unknown_task_ids:
        reasons.append("unsupported calculation task ids: " + ", ".join(unknown_task_ids))
    period = planning.construction_period
    if period.start is None or period.end is None or not period.start <= day <= period.end:
        reasons.append("analysis date is outside the confirmed construction period")
    if planning.same_day_restoration_required and not restoration_task_ids:
        reasons.append("same-day restoration is required but no restoration task was identified")
    if any(duration % GRID_MINUTES for duration in durations.values()):
        reasons.append("CP-SAT v2 requires task durations aligned to the 15-minute planning grid")
    required: dict[str, int] = {}
    for task_id, equipment_id in equipment_by_task.items():
        if equipment_id and task_id in durations:
            required[equipment_id] = required.get(equipment_id, 0) + durations[task_id]
    for constraint in planning.equipment_constraints:
        if required.get(constraint.equipment_id, 0) != constraint.required_usage_minutes:
            reasons.append(f"required equipment usage mismatch: {constraint.equipment_id}")
    if reasons:
        return _empty_result(reasons, solution_limit)

    model = cp_model.CpModel()
    starts: dict[str, cp_model.IntVar] = {}
    ends: dict[str, cp_model.IntVar] = {}
    intervals: dict[str, cp_model.IntervalVar] = {}
    for task in tasks:
        allowed = _allowed_starts(task.id, durations[task.id], planning, equipment_by_task.get(task.id))
        if not allowed:
            return _empty_result([f"no allowed start time for task {task.id}"], solution_limit)
        starts[task.id] = model.new_int_var_from_domain(cp_model.Domain.from_values(allowed), f"start_{task.id}")
        ends[task.id] = model.new_int_var(min(allowed) + durations[task.id], max(allowed) + durations[task.id], f"end_{task.id}")
        model.add(ends[task.id] == starts[task.id] + durations[task.id])
        intervals[task.id] = model.new_interval_var(starts[task.id], durations[task.id], ends[task.id], f"interval_{task.id}")
    for task_id, required_predecessors in predecessors.items():
        for predecessor in required_predecessors:
            if task_id in starts and predecessor in ends:
                model.add(starts[task_id] >= ends[predecessor])
    resources: dict[str, list[cp_model.IntervalVar]] = {}
    by_id = {task.id: task for task in tasks}
    for task_id, interval in intervals.items():
        for resource in by_id[task_id].required_resources:
            resources.setdefault(resource, []).append(interval)
    for rows in resources.values():
        if len(rows) > 1:
            model.add_no_overlap(rows)

    solver = cp_model.CpSolver()
    solver.parameters.enumerate_all_solutions = True
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    collector = _Collector(starts, solution_limit)
    status = solver.solve(model, collector)
    if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE} or not collector.solutions:
        return _empty_result(["CP-SAT found no feasible schedule"], solution_limit)
    unique = {tuple(sorted(row.items())): row for row in collector.solutions}
    candidates = [_candidate(scenario_id, day, row, durations, index, sensitivity_enabled=sensitivity_enabled, background_profile=background_profile, sensitivity_policy=sensitivity_policy, experimental_context_multiplier=experimental_context_multiplier, include_existing_events=include_existing_events) for index, (_, row) in enumerate(sorted(unique.items()), start=1)]
    points = [{"id": row.id, **row.objective_values} for row in candidates]
    frontier_ids = {row["id"] for row in non_dominated_multi(points, PARETO_AXES)}
    frontier = [row for row in candidates if row.id in frontier_ids]
    return {"optimization_status": "feasible_solution_set", "solver": "ortools_cp_sat", "candidates": candidates, "pareto_candidates": frontier, "explored_candidate_count": len(candidates), "pareto_candidate_count": len(frontier), "solution_limit": solution_limit, "solution_limit_reached": collector.limit_reached, "search_complete": status == cp_model.OPTIMAL and not collector.limit_reached, "global_optimality_guaranteed": False, "pareto_axes": PARETO_AXES, "infeasibility_reasons": []}
