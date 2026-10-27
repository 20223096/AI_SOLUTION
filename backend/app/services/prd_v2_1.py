from __future__ import annotations

import json
from datetime import date

from app.models.domain import ConstructionNotice, SourceMetadata, TaskAssignment, TimeWindow
from app.models.prd_v2_1 import PRDConstraintRecommendationRequest, PRDNoticePlanningInput, PRDPlanningDraftRequest
from app.core.config import get_settings
from app.services.optimizer import optimize
from app.services.pareto import non_dominated, non_dominated_multi
from app.services.optimizer import MULTI_AXES
from app.services.advanced_optimizer import PARETO_AXES as ADVANCED_AXES, optimize_advanced
from app.services.timegrid import at as _at


def validate_prd_schedule(
    planning: PRDNoticePlanningInput,
    day: date,
    assignments: list[TaskAssignment],
    predecessors: dict[str, list[str]],
    equipment_by_task: dict[str, str | None],
    restoration_task_ids: set[str],
    equipment_count_by_task: dict[str, int] | None = None,
    task_duration_by_task: dict[str, int] | None = None,
) -> dict:
    """Validate explicit PRD inputs without inventing universal work-hour rules."""
    violations: list[dict] = []
    by_task = {item.task_id: item for item in assignments}
    period = planning.construction_period
    if period.start is None or period.end is None:
        violations.append({"code": "construction_period_missing", "detail": "construction_period.start and end are required for schedule validation"})
    elif not period.start <= day <= period.end:
        violations.append({"code": "outside_construction_period", "detail": f"{day.isoformat()} is outside {period.start.isoformat()}..{period.end.isoformat()}"})
    overall_start = _at(day, planning.total_work_window.start)
    overall_end = _at(day, planning.total_work_window.end)
    for item in assignments:
        if item.start < overall_start or item.end > overall_end:
            violations.append({"code": "outside_total_work_window", "task_id": item.task_id})

    equipment_constraints = {item.equipment_id: item for item in planning.equipment_constraints}
    equipment_count_by_task = equipment_count_by_task or {}
    task_duration_by_task = task_duration_by_task or {}
    for task_id, expected in task_duration_by_task.items():
        assignment = by_task.get(task_id)
        if assignment is None:
            violations.append({"code": "task_assignment_missing", "task_id": task_id})
        elif int((assignment.end - assignment.start).total_seconds() / 60) != expected:
            violations.append({"code": "task_duration_mismatch", "task_id": task_id, "required_minutes": expected})
    scheduled_minutes_by_equipment: dict[str, int] = {}
    assignments_by_equipment: dict[str, list[TaskAssignment]] = {}
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
        assignments_by_equipment.setdefault(equipment_id, []).append(assignment)
        count = equipment_count_by_task.get(task_id)
        if constraint.max_daily_count is not None and count is None:
            violations.append({"code": "equipment_count_missing", "task_id": task_id, "equipment_id": equipment_id})
        elif count is not None and constraint.max_daily_count is not None and count > constraint.max_daily_count:
            violations.append({"code": "equipment_daily_count_exceeded", "task_id": task_id, "equipment_id": equipment_id, "count": count, "maximum": constraint.max_daily_count})
    for equipment_id, constraint in equipment_constraints.items():
        actual = scheduled_minutes_by_equipment.get(equipment_id, 0)
        if actual != constraint.required_usage_minutes:
            violations.append({"code": "equipment_required_usage_mismatch", "equipment_id": equipment_id, "scheduled_minutes": actual, "required_minutes": constraint.required_usage_minutes})
        if constraint.max_daily_count is not None:
            scheduled = assignments_by_equipment.get(equipment_id, [])
            for moment in {item.start for item in scheduled}:
                concurrent = sum(equipment_count_by_task.get(item.task_id, 0) for item in scheduled if item.start <= moment < item.end)
                if concurrent > constraint.max_daily_count:
                    violations.append({"code": "equipment_concurrent_count_exceeded", "equipment_id": equipment_id, "count": concurrent, "maximum": constraint.max_daily_count})
                    break

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


def planning_draft_from_notice(request: PRDPlanningDraftRequest) -> dict:
    """Map only fields present in an extracted notice; never complete missing facts."""
    notice: ConstructionNotice = request.notice
    document_source = notice.source_provenance.get("document") or notice.source_provenance.get("scenario") or SourceMetadata(
        status="missing", note="No document-level provenance supplied"
    )
    equipment_by_id = {}
    constraints = notice.constraints
    equipment_counts = constraints.get("equipment_counts", {}) if isinstance(constraints.get("equipment_counts"), dict) else {}
    equipment_usage = constraints.get("equipment_usage_times", {}) if isinstance(constraints.get("equipment_usage_times"), dict) else {}
    equipment_models = constraints.get("equipment_models", {}) if isinstance(constraints.get("equipment_models"), dict) else {}
    for task in notice.tasks:
        if task.equipment_id is None:
            continue
        usage_rows = equipment_usage.get(task.equipment_id, [])
        windows = []
        for row in usage_rows if isinstance(usage_rows, list) else []:
            try:
                windows.append(TimeWindow.model_validate(row))
            except (TypeError, ValueError):
                pass
        duration = task.duration_minutes
        if duration is None and windows:
            duration = int((windows[0].end.hour * 60 + windows[0].end.minute) - (windows[0].start.hour * 60 + windows[0].start.minute))
        equipment_by_id.setdefault(task.equipment_id, {
            "equipment_id": task.equipment_id,
            "category": task.name,
            "specification": None,
            "model_name": equipment_models.get(task.equipment_id),
            "max_daily_count": equipment_counts.get(task.equipment_id),
            "required_usage_minutes": duration,
            "permitted_time_windows": task.permitted_time_windows or windows,
            "source_metadata": document_source,
        })
    equipment = list(equipment_by_id.values())
    road_excavation = constraints.get("road_excavation") if isinstance(constraints.get("road_excavation"), bool) else None
    same_day = constraints.get("same_day") if isinstance(constraints.get("same_day"), bool) else None
    field_values = {
        "project_name": notice.name,
        "location": notice.location,
        "construction_period": notice.construction_period.start if notice.construction_period.start and notice.construction_period.end else None,
        "total_work_window": notice.original_work_window,
        "road_excavation": road_excavation,
    }
    missing = [name for name, value in field_values.items() if value is None]
    if not equipment:
        missing.append("equipment_constraints")
    if any(row["required_usage_minutes"] is None for row in equipment):
        missing.append("equipment_required_usage_minutes")
    missing.extend(["road_occupancy_permit_window", "max_daily_equipment_count"])
    missing = list(dict.fromkeys(missing))
    provenance = {name: document_source for name, value in field_values.items() if value is not None}
    provenance.update({name: SourceMetadata(status="missing", note="Not confirmed in extracted notice") for name in missing})
    return {
        "status": "needs_confirmation" if missing else "ready_for_confirmation",
        "extractor_mode": request.extractor_mode,
        "is_actual_ai": request.is_actual_ai,
        "planning_draft": {
            "notice_id": notice.id,
            "project_name": notice.name,
            "location": notice.location,
            "construction_period": notice.construction_period,
            "total_work_window": notice.original_work_window,
            "road_excavation": road_excavation,
            "road_occupancy_permit_window": None,
            "equipment_constraints": equipment,
            "fixed_tasks": [],
            "predecessors": {task.id: task.predecessors for task in notice.tasks if task.predecessors},
            "same_day_restoration_required": same_day,
            "non_adjustable_conditions": constraints.get("non_adjustable_conditions", []),
            "source_evidence": request.field_evidence,
            "field_provenance": provenance,
        },
        "missing_fields": missing,
        "confirmation_required_fields": sorted(set(missing + ["project_name", "location", "construction_period", "total_work_window", "equipment_constraints"])),
        "warnings": [
            "Extraction output is an unconfirmed draft and is not an official filing fact.",
            "Null and missing values must be confirmed by a user; no constraint was inferred.",
        ],
    }


def constraint_filtered_recommendations(request: PRDConstraintRecommendationRequest) -> dict:
    scenario_id, _, _ = demo_scenario_for_date(request.analysis_date)
    baseline = optimize(scenario_id, request.analysis_date, background_profile=request.background_profile, objective_mode=request.objective_mode)
    if request.recommendation_engine == "cp_sat_v2":
        result = optimize_advanced(
            scenario_id, request.analysis_date, request.planning, request.predecessors,
            request.equipment_by_task, request.restoration_task_ids, request.task_duration_by_task,
            background_profile=request.background_profile,
        )
        base_candidates = result["candidates"]
        axes = ADVANCED_AXES
    else:
        result = baseline
        base_candidates = result.get("valid_candidates", [])
        axes = MULTI_AXES if request.objective_mode == "multi_axis" else ["resident_cost", "change_cost"]
    rows = []
    feasible_points = []
    for candidate in base_candidates:
        validation = validate_prd_schedule(
            request.planning, request.analysis_date, candidate.task_assignments, request.predecessors,
            request.equipment_by_task, request.restoration_task_ids, request.equipment_count_by_task,
            request.task_duration_by_task,
        )
        if validation["feasible"]:
            feasible_points.append({"id": candidate.id, **candidate.objective_values})
        rows.append((candidate, validation))
    frontier_points = non_dominated_multi(feasible_points, axes) if len(axes) > 2 else non_dominated(feasible_points)
    frontier_ids = {row["id"] for row in frontier_points}
    original_candidate = next((item for item in baseline.get("valid_candidates", []) if item.id == "offset-0"), None)
    original_validation = validate_prd_schedule(
        request.planning, request.analysis_date, original_candidate.task_assignments, request.predecessors,
        request.equipment_by_task, request.restoration_task_ids, request.equipment_count_by_task,
        request.task_duration_by_task,
    ) if original_candidate is not None else None
    if request.recommendation_engine == "cp_sat_v2":
        rows = [(candidate, validation) for candidate, validation in rows if candidate.id in frontier_ids]
    candidates = []
    for candidate, validation in rows:
        candidates.append({
            "candidate_id": candidate.id,
            "assignments": candidate.task_assignments,
            "base_optimizer_feasible": True,
            "prd_feasible": validation["feasible"],
            "recommendable": validation["feasible"] and candidate.id in frontier_ids,
            "violations": validation["violations"],
            "pareto_after_constraint_filter": candidate.id in frontier_ids,
            "schedule_change_minutes": candidate.metrics.schedule_change_minutes,
            "project_start_change_minutes": candidate.metrics.project_start_change_minutes,
            "project_end_change_minutes": candidate.metrics.project_end_change_minutes,
            "noise_impact": candidate.metrics,
            "objective_values": candidate.objective_values,
        })
    missing = []
    task_ids = {assignment.task_id for candidate in base_candidates for assignment in candidate.task_assignments}
    missing.extend(f"equipment_by_task.{task_id}" for task_id in sorted(task_ids - request.equipment_by_task.keys()))
    missing.extend(f"field_provenance.{field}" for field in (
        "construction_period", "total_work_window", "road_excavation"
    ) if field not in request.planning.field_provenance)
    recommendable = [row["candidate_id"] for row in candidates if row["recommendable"]]
    original = next((row for row in candidates if row["candidate_id"] == "offset-0"), None)
    if request.recommendation_engine == "cp_sat_v2" and original_candidate is not None and original_validation is not None:
        original = {
            "candidate_id": original_candidate.id, "assignments": original_candidate.task_assignments,
            "base_optimizer_feasible": True, "prd_feasible": original_validation["feasible"],
            "recommendable": False, "violations": original_validation["violations"],
            "pareto_after_constraint_filter": False,
            "schedule_change_minutes": original_candidate.metrics.schedule_change_minutes,
            "project_start_change_minutes": original_candidate.metrics.project_start_change_minutes,
            "project_end_change_minutes": original_candidate.metrics.project_end_change_minutes,
            "noise_impact": original_candidate.metrics, "objective_values": original_candidate.objective_values,
        }
    advanced = request.recommendation_engine == "cp_sat_v2"
    return {
        "input_planning": request.planning,
        "input_provenance": request.planning.field_provenance,
        "policy_version": "prd_v2_1_explicit_input_only",
        "candidate_generation_mode": "ortools_cp_sat_task_start_enumeration" if advanced else "existing_optimizer_15_minute_offsets_0_to_120",
        "optimization_claim": "constraint_filtered_candidate_set_not_global_optimum",
        "solver": result.get("solver", "exact_enumeration"),
        "explored_candidate_count": result.get("explored_candidate_count", len(base_candidates)),
        "pareto_candidate_count": len(frontier_ids),
        "pareto_axes": axes,
        "search_complete": result.get("search_complete", True),
        "global_optimality_guaranteed": False,
        "scenario_id": scenario_id,
        "analysis_date": request.analysis_date,
        "original_schedule": original,
        "candidates": candidates,
        "recommendable_candidate_ids": recommendable,
        "recommendation_status": "available" if recommendable else "none_feasible",
        "no_recommendation_reasons": [] if recommendable else (result.get("infeasibility_reasons") or ["All explored candidates violate explicit PRD constraints."]),
        "simulation_status": "simulated",
        "missing_information": missing,
        "caveats": [
            "This is a constraint-filtered result over the explored candidate set, not a global optimum." if advanced else "This is a constraint-filtered result over the existing offset candidate set, not a global optimum.",
            "No unspecified time limit or relaxed constraint was introduced.",
            "S-DoT observations are not added to the acoustic synthesis.",
            "Official construction geometry and residential facade receptors remain unavailable; field accuracy is not_evaluable.",
        ],
    }


def demo_fixture() -> dict:
    path = get_settings().data_dir / "demo_2026_09_11.json"
    return json.loads(path.read_text(encoding="utf-8"))


def demo_scenario_for_date(day: date) -> tuple[str, str, str]:
    if day == date(2026, 9, 11):
        return "final-demo-congestion", "9/11 assumed congestion overlay is scoped to its fixture analysis date", "demo_simulation"
    if day == date(2026, 10, 7):
        return "official_reference_equipment", "comparison day excludes the date-specific 9/11 assumed congestion overlay", "comparison_day_simulation"
    raise ValueError("analysis_date must be 2026-09-11 or 2026-10-07")


def _candidate_diagnostics(result: dict, *, assumed_overlap: bool) -> list[dict]:
    pareto_ids = {item.id for item in result.get("pareto_candidates", [])}
    output = []
    for row in result["diagnostics"]["candidate_metrics"]:
        candidate_id = row["id"]
        candidate = next((item for item in result.get("valid_candidates", []) if item.id == candidate_id), None)
        if candidate is None and result.get("infeasible_result") is not None and result["infeasible_result"].id == candidate_id:
            candidate = result["infeasible_result"]
        metrics = row["metrics"]
        assignments = candidate.task_assignments if candidate is not None else []
        output.append({
            "id": candidate_id,
            "first_task_start": min((item.start for item in assignments), default=None),
            "project_start_shift_minutes": int(row["schedule_change_details"].get("project_start_shift_minutes", 0)),
            "total_task_start_shift_minutes": int(row["schedule_change_details"].get("total_task_start_shift_minutes", 0)),
            "feasibility": row["feasibility"],
            "infeasibility_reasons": row["infeasibility_reasons"],
            "objective_values": row["objective_values"],
            "sensitive_time_exposure_minutes": metrics.sensitive_new_project_receptor_minutes,
            "weighted_sensitive_exposure": metrics.sensitivity_weighted_new_project_receptor_minutes,
            "existing_noise_overlap_receptor_minutes": metrics.existing_noise_overlap_receptor_minutes,
            "existing_event_overlap_basis": "assumed_simulation" if assumed_overlap and metrics.existing_noise_overlap_receptor_minutes else "none",
            "metrics": metrics,
            "pareto_included": candidate_id in pareto_ids,
            "dominated_reason": row["dominated_reason"],
        })
    return output


def recommendation_diagnostics(day: date, background_profile: str = "road_traffic_observed_profile", objective_mode: str = "incremental_impact") -> dict:
    scenario_id, reason, role = demo_scenario_for_date(day)
    result = optimize(scenario_id, day, background_profile=background_profile, objective_mode=objective_mode)
    recommended_ids = [item["candidate"].id for item in result.get("recommended_options", [])]
    original = next((item for item in result.get("valid_candidates", []) if item.id == "offset-0"), None)
    improved = [
        item["candidate"] for item in result.get("recommended_options", [])
        if original is not None and item["candidate"].id != original.id and item["candidate"].objective_values["resident_cost"] < original.objective_values["resident_cost"]
    ]
    summary = "No feasible candidate improves the selected noise objective over the original schedule without adding schedule change." if not improved else f"{', '.join(item.id for item in improved)} improves the selected noise objective but requires schedule change."
    return {
        "analysis_date": day,
        "scenario_id": scenario_id,
        "scenario_selection_reason": reason,
        "comparison_data_role": role,
        "optimization_status": result["optimization_status"],
        "objective_mode": objective_mode,
        "scoring_version": result["scoring_version"],
        "solver": result["solver"],
        "recommended_candidate_ids": recommended_ids,
        "pareto_candidate_ids": [item.id for item in result.get("pareto_candidates", [])],
        "improvement_over_original": bool(improved),
        "improvement_summary": summary,
        "candidates": _candidate_diagnostics(result, assumed_overlap=day == date(2026, 9, 11)),
        "caveats": [
            "The road traffic profile is a historical representative profile, not receptor-specific measurements for this date.",
            "S-DoT observations are quality-audited context and are not used in the acoustic sum.",
            "65 dB is a PoC analysis threshold, not a legal compliance limit.",
        ],
    }


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


def demo_sensitivity_policy_experiment(analysis_dates: list[date], background_profile: str, multipliers: list[float]) -> dict:
    experiments = []
    for day in analysis_dates:
        scenario_id, reason, _ = demo_scenario_for_date(day)
        result = sensitivity_policy_experiment(scenario_id, day, background_profile, multipliers)
        cases = []
        for case, multiplier in zip(result["cases"], multipliers):
            optimized = optimize(
                scenario_id,
                day,
                background_profile=background_profile,
                sensitivity_policy="prd_max_v2_1_experimental",
                experimental_context_multiplier=multiplier,
            )
            cases.append({
                **case,
                "infeasible_candidate_ids": [row["id"] for row in optimized["diagnostics"]["candidate_metrics"] if not row["feasibility"]],
                "candidate_diagnostics": _candidate_diagnostics(optimized, assumed_overlap=day == date(2026, 9, 11)),
            })
        experiments.append({
            "analysis_date": day,
            "scenario_id": scenario_id,
            "scenario_selection_reason": reason,
            "baseline_policy": result["baseline_policy"],
            "baseline_recommended_candidate_ids": result["baseline_recommended_candidate_ids"],
            "baseline_candidate_ranking": result["baseline_candidate_ranking"],
            "cases": cases,
        })
    return {
        "policy_name": "PRD v2.1 maximum-overlap sensitivity experiment",
        "policy_version": "prd_max_v2_1_experimental",
        "overlap_rule": "maximum_single_multiplier",
        "status": "simulated",
        "background_profile": background_profile,
        "experiments": experiments,
        "default_m0_m1_unchanged": True,
        "disclaimer": "Sensitivity multipliers are planning assumptions, not validated harm coefficients or legal criteria.",
    }
