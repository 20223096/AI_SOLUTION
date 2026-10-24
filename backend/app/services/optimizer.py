from datetime import date, datetime, timedelta

from app.models.domain import ScheduleCandidate, ScheduleMetrics, SourceMetadata, TaskAssignment
from app.services.data import get_scenario
from app.services.metrics import schedule_metrics
from app.services.pareto import non_dominated, non_dominated_multi
from app.services.prediction import default_assignments
from app.services.timegrid import at, overlaps


OBJECTIVE_FIELDS = {
    "incremental_impact": ("incremental_impact_cost", "experimental Impact points"),
    "absolute_impact": ("absolute_impact_cost", "experimental Impact points"),
    "physical_energy": ("new_project_energy_exposure_65db_ref_minutes", "65 dB-reference energy-minutes"),
    "sensitive_exposure": ("sensitive_new_project_receptor_minutes", "receptor-minutes"),
    "continuous_burden": ("max_continuous_new_project_minutes", "minutes"),
    "multi_axis": (None, "independent axes; no composite unit"),
}

MULTI_AXES = ["physical_energy_cost", "sensitive_exposure_cost", "continuous_burden_cost", "change_cost"]


def _candidate(scenario_id: str, day: date, offset_minutes: int, sensitivity_enabled: bool = True, background_profile: str = "assumed_demo", objective_mode: str = "incremental_impact", sensitivity_policy: str = "legacy_v1", experimental_context_multiplier: float | None = None) -> ScheduleCandidate:
    scenario = get_scenario(scenario_id)
    notice = scenario["notice"]
    timed = [t for t in notice.tasks if t.duration_minutes is not None]
    total = sum(t.duration_minutes for t in timed)
    window = notice.original_work_window
    available = int((datetime.combine(day, window.end) - datetime.combine(day, window.start)).total_seconds() / 60)
    reasons = []
    if notice.constraints.get("require_all_task_durations") and any(t.duration_minutes is None for t in notice.tasks):
        reasons.append("같은 날 복구 조건 검증에 필요한 공정 소요시간이 누락됨")
    max_daily = notice.constraints.get("max_daily_sequential_minutes")
    if max_daily is not None and total > max_daily:
        reasons.append(f"순차 작업 {total}분이 일일 제한 {max_daily}분을 초과")
    start = at(day, window.start) + timedelta(minutes=offset_minutes)
    if offset_minutes < 0 or offset_minutes + total > available:
        reasons.append("작업이 허용 시간대 [07:00,18:00) 밖으로 벗어남")
    if notice.constraints.get("fixed_schedule") and offset_minutes != 0:
        reasons.append("원 일정 변경 불가 제약으로 시작시간을 이동할 수 없음")
    assignments, cursor = [], start
    for task in timed:
        end = cursor + timedelta(minutes=task.duration_minutes)
        assignments.append(TaskAssignment(task_id=task.id, start=cursor, end=end))
        cursor = end
    for forbidden in notice.constraints.get("forbidden_windows", []):
        f_start = at(day, datetime.strptime(forbidden["start"], "%H:%M").time())
        f_end = at(day, datetime.strptime(forbidden["end"], "%H:%M").time())
        if any(overlaps(x.start, x.end, f_start, f_end) for x in assignments):
            reasons.append(f"작업 금지시간 {forbidden['start']}~{forbidden['end']}과 충돌")
    # Sequential construction preserves predecessors/resources by construction.
    feasible = not reasons
    metrics = schedule_metrics(scenario_id, day, assignments, sensitivity_enabled=sensitivity_enabled, background_profile=background_profile, sensitivity_policy=sensitivity_policy, experimental_context_multiplier=experimental_context_multiplier) if feasible else ScheduleMetrics()
    original = default_assignments(scenario, day)
    original_starts = {x.task_id: x.start for x in original}
    task_changes = {x.task_id: abs(int((x.start - original_starts[x.task_id]).total_seconds() / 60)) for x in assignments}
    change = sum(task_changes.values())
    project_start_change = abs(int((min(x.start for x in assignments) - min(x.start for x in original)).total_seconds() / 60)) if assignments and original else 0
    project_end_change = abs(int((max(x.end for x in assignments) - max(x.end for x in original)).total_seconds() / 60)) if assignments and original else 0
    metrics.schedule_change_minutes = change
    metrics.project_start_change_minutes = project_start_change
    metrics.project_end_change_minutes = project_end_change
    assignment_by_task = {x.task_id: x for x in assignments}
    predecessor_order_preserved = all(
        predecessor not in assignment_by_task or assignment_by_task[predecessor].end <= assignment_by_task[task.id].start
        for task in timed for predecessor in task.predecessors
    )
    resource_conflicts = []
    for index, left in enumerate(timed):
        for right in timed[index + 1:]:
            shared = sorted(set(left.required_resources) & set(right.required_resources))
            if shared and overlaps(assignment_by_task[left.id].start, assignment_by_task[left.id].end, assignment_by_task[right.id].start, assignment_by_task[right.id].end):
                resource_conflicts.append({"task_ids": [left.id, right.id], "resources": shared})
    overlap_count = metrics.existing_noise_overlap_receptor_minutes // 15
    overlap_penalty = float(scenario.get("settings", {}).get("existing_overlap_penalty_per_receptor_slot", 0))
    absolute_cost = metrics.absolute_impact_cost
    incremental_cost = metrics.incremental_impact_cost
    objective_field, _ = OBJECTIVE_FIELDS[objective_mode]
    resident_cost = incremental_cost if objective_field is None else getattr(metrics, objective_field)
    schedule_change_details = {"definition": "sum of absolute per-task start shifts", "task_start_shift_minutes": task_changes, "total_task_start_shift_minutes": change, "project_start_shift_minutes": project_start_change, "project_end_shift_minutes": project_end_change, "original_project_end": max((x.end for x in original), default=None), "candidate_project_end": max((x.end for x in assignments), default=None), "predecessor_order_preserved": predecessor_order_preserved, "resource_conflicts": resource_conflicts}
    return ScheduleCandidate(id=f"offset-{offset_minutes}", task_assignments=assignments if feasible else [], feasibility=feasible, infeasibility_reasons=reasons, needs_confirmation=["덤프트럭 소음 원천값", "미확정 공정 소요시간"] if reasons else ["덤프트럭 소음 원천값"], metrics=metrics, objective_values={"resident_cost": round(resident_cost, 6), "change_cost": float(change), "total_task_start_shift_minutes": float(change), "project_start_shift_minutes": float(project_start_change), "project_end_shift_minutes": float(project_end_change), "base_impact_cost": absolute_cost, "absolute_impact_cost": absolute_cost, "incremental_impact_cost": incremental_cost, "physical_energy_cost": metrics.new_project_energy_exposure_65db_ref_minutes, "sensitive_exposure_cost": float(metrics.sensitive_new_project_receptor_minutes), "weighted_sensitive_exposure": metrics.sensitivity_weighted_new_project_receptor_minutes, "continuous_burden_cost": float(metrics.max_continuous_new_project_minutes), "existing_noise_overlap_slots": float(overlap_count), "existing_noise_overlap_minutes": float(overlap_count * 15), "policy_overlap_cost": round(overlap_count * overlap_penalty, 2), "existing_noise_overlap_penalty": round(overlap_count * overlap_penalty, 2)}, schedule_change_details=schedule_change_details, provenance=SourceMetadata(status="derived", source="exact 15-minute offset enumeration", note="No duration reduction or parallel work assumed; each objective retains its own unit; overlap policy cost is reported separately"))


def _dominated_reason(candidate: ScheduleCandidate, valid: list[ScheduleCandidate], axes: list[str]) -> dict | None:
    x = candidate.objective_values
    dominators = [o for o in valid if o.id != candidate.id and all(o.objective_values[axis] <= x[axis] for axis in axes) and any(o.objective_values[axis] < x[axis] for axis in axes)]
    if not dominators:
        return None
    best = min(dominators, key=lambda o: tuple(o.objective_values[axis] for axis in axes))
    return {"dominated_by": best.id, "axes": axes, "reason": "모든 비교 축이 같거나 낮고 하나 이상 엄격히 낮음"}


def _recommendation_reasons(candidate: ScheduleCandidate, original: ScheduleCandidate, characters: list[str], objective_mode: str, objective_unit: str) -> list[dict]:
    reasons = []
    if "construction_convenience" in characters:
        reasons.append({"code": "minimum_schedule_change", "message": "Pareto 후보 중 작업별 시작시간 변경 합계가 최소입니다.", "evidence": [{"field": "objective_values.total_task_start_shift_minutes", "value": candidate.objective_values["total_task_start_shift_minutes"], "unit": "minutes"}]})
    if "resident_protection" in characters:
        reasons.append({"code": "minimum_selected_objective", "message": "선택된 단일 목적지표가 Pareto 후보 중 최소입니다.", "evidence": [{"field": f"metrics.{OBJECTIVE_FIELDS[objective_mode][0]}", "value": candidate.objective_values["resident_cost"], "unit": objective_unit}]})
    if "multi_axis_pareto_reference" in characters:
        reasons.append({"code": "non_dominated_multi_axis", "message": "독립된 네 목적 축에서 지배되지 않는 결정론적 참조 후보이며 단일 최적안은 아닙니다.", "evidence": [{"field": f"objective_values.{axis}", "value": candidate.objective_values[axis]} for axis in MULTI_AXES]})
    reasons.append({"code": "comparison_to_original", "message": "계산된 원 일정 대비 변화입니다.", "evidence": [
        {"field": "metrics.incremental_impact_cost", "delta": round(candidate.metrics.incremental_impact_cost - original.metrics.incremental_impact_cost, 6), "unit": "legacy Impact points"},
        {"field": "metrics.new_project_energy_exposure_65db_ref_minutes", "delta": round(candidate.metrics.new_project_energy_exposure_65db_ref_minutes - original.metrics.new_project_energy_exposure_65db_ref_minutes, 6), "unit": "65 dB-reference energy-minutes"},
        {"field": "metrics.sensitive_new_project_receptor_minutes", "delta": candidate.metrics.sensitive_new_project_receptor_minutes - original.metrics.sensitive_new_project_receptor_minutes, "unit": "receptor-minutes"},
        {"field": "metrics.max_continuous_new_project_minutes", "delta": candidate.metrics.max_continuous_new_project_minutes - original.metrics.max_continuous_new_project_minutes, "unit": "minutes"},
        {"field": "metrics.existing_noise_overlap_receptor_minutes", "delta": candidate.metrics.existing_noise_overlap_receptor_minutes - original.metrics.existing_noise_overlap_receptor_minutes, "unit": "receptor-minutes"},
        {"field": "objective_values.total_task_start_shift_minutes", "delta": candidate.objective_values["total_task_start_shift_minutes"] - original.objective_values["total_task_start_shift_minutes"], "unit": "minutes"},
    ]})
    reasons.append({"code": "data_quality", "message": "장비 참고값·민감도 가중치·가정 이벤트는 실제 현장 검증값이 아닙니다.", "evidence": [{"field": "provenance.status", "value": "mixed_verified_derived_assumed"}]})
    reasons.append({"code": "policy_uncertainty", "message": "기존 이벤트 중첩은 보고만 하며 검증되지 않은 정책비용을 추천 목적에 더하지 않았습니다.", "evidence": [{"field": "diagnostics.policy_overlap_cost_included_in_pareto", "value": False}]})
    return reasons


def optimize(scenario_id: str, day: date, sensitivity_enabled: bool = True, background_profile: str = "assumed_demo", objective_mode: str = "incremental_impact", sensitivity_policy: str = "legacy_v1", experimental_context_multiplier: float | None = None) -> dict:
    if objective_mode not in OBJECTIVE_FIELDS:
        raise ValueError(f"unknown objective_mode: {objective_mode}")
    scenario = get_scenario(scenario_id)
    raw = [_candidate(scenario_id, day, offset, sensitivity_enabled=sensitivity_enabled, background_profile=background_profile, objective_mode=objective_mode, sensitivity_policy=sensitivity_policy, experimental_context_multiplier=experimental_context_multiplier) for offset in range(0, 121, 15)]
    valid = [x for x in raw if x.feasibility]
    points = [{"id": x.id, **x.objective_values} for x in valid]
    pareto_axes = MULTI_AXES if objective_mode == "multi_axis" else ["resident_cost", "change_cost"]
    pareto_points = non_dominated_multi(points, pareto_axes) if objective_mode == "multi_axis" else non_dominated(points)
    ids = {x["id"] for x in pareto_points}
    frontier = [x for x in valid if x.id in ids]
    selections = {}
    if frontier:
        selections["construction_convenience"] = min(frontier, key=lambda x: x.objective_values["change_cost"])
        if objective_mode != "multi_axis":
            selections["resident_protection"] = min(frontier, key=lambda x: x.objective_values["resident_cost"])
        else:
            selections["multi_axis_pareto_reference"] = min(frontier, key=lambda x: tuple(x.objective_values[axis] for axis in MULTI_AXES) + (x.id,))
        # Preserve the v8 normalized balanced selector only for legacy Impact
        # modes. Experimental metrics intentionally avoid cross-unit sums.
        if objective_mode in {"incremental_impact", "absolute_impact"}:
            selections["balanced"] = min(frontier, key=lambda x: x.objective_values["resident_cost"] / max(1, max(y.objective_values["resident_cost"] for y in frontier)) + x.objective_values["change_cost"] / max(1, max(y.objective_values["change_cost"] for y in frontier)))
    # Deduplicate labels that select the same candidate.
    original = next((x for x in valid if x.id == "offset-0"), valid[0] if valid else raw[0])
    objective_unit = OBJECTIVE_FIELDS[objective_mode][1]
    unique = {}
    for value in selections.values():
        characters = [key for key, selected in selections.items() if selected.id == value.id]
        unique[value.id] = {"character": characters, "candidate": value, "recommendation_reasons": _recommendation_reasons(value, original, characters, objective_mode, objective_unit)}
    diagnostics = {
        "generated_candidate_count": len(raw), "feasible_candidate_count": len(valid),
        "infeasible_candidate_count": len(raw) - len(valid), "pareto_candidate_count": len(frontier), "pareto_axes": pareto_axes,
        "candidate_metrics": [{"id": x.id, "feasibility": x.feasibility, "pareto_included": x.id in ids, "objective_values": x.objective_values, "metrics": x.metrics, "schedule_change_details": x.schedule_change_details, "infeasibility_reasons": x.infeasibility_reasons, "dominated_reason": _dominated_reason(x, valid, pareto_axes) if x.feasibility else None} for x in raw],
        "sensitivity_enabled": sensitivity_enabled, "background_profile": background_profile, "objective_mode": objective_mode, "objective_field": OBJECTIVE_FIELDS[objective_mode][0], "objective_unit": OBJECTIVE_FIELDS[objective_mode][1], "default_objective_unchanged": True, "balanced_selection": "legacy_v1_normalized_impact_plus_change" if objective_mode in {"incremental_impact", "absolute_impact"} else None, "policy_overlap_cost_included_in_pareto": False,
    }
    if not valid:
        return {"scenario_id": scenario_id, "analysis_date": day, "optimization_status": "infeasible", "scoring_version": "legacy_v1", "metrics_version": "robust_experimental_v1", "valid_candidates": [], "pareto_candidates": [], "recommended_options": [], "infeasible_result": raw[0], "relaxation_guidance": ["누락 공정시간을 확인", "금지시간 또는 일일 제한을 담당자가 검토", "필요하면 다일 분할 가능 여부 확인"], "solver": "exact_enumeration", "diagnostics": diagnostics}
    return {"scenario_id": scenario_id, "analysis_date": day, "optimization_status": "optimal_enumeration", "scoring_version": "legacy_v1", "metrics_version": "robust_experimental_v1", "valid_candidates": valid, "pareto_candidates": frontier, "recommended_options": list(unique.values()), "solver": "exact_enumeration", "note": "Only distinct non-dominated schedules are returned.", "diagnostics": diagnostics}
