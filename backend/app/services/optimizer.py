from datetime import date, datetime, timedelta

from app.models.domain import ScheduleCandidate, ScheduleMetrics, SourceMetadata, TaskAssignment
from app.services.data import get_scenario
from app.services.metrics import schedule_metrics
from app.services.pareto import non_dominated
from app.services.prediction import default_assignments
from app.services.prediction import predict
from app.services.timegrid import at, overlaps


def _candidate(scenario_id: str, day: date, offset_minutes: int, sensitivity_enabled: bool = True, background_profile: str = "assumed_demo") -> ScheduleCandidate:
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
    metrics = schedule_metrics(scenario_id, day, assignments, sensitivity_enabled=sensitivity_enabled, background_profile=background_profile) if feasible else ScheduleMetrics()
    original = default_assignments(scenario, day)
    original_starts = {x.task_id: x.start for x in original}
    change = sum(abs(int((x.start - original_starts[x.task_id]).total_seconds() / 60)) for x in assignments)
    metrics.schedule_change_minutes = change
    overlap_count = 0
    overlap_penalty = float(scenario.get("settings", {}).get("existing_overlap_penalty_per_receptor_slot", 0))
    if feasible and overlap_penalty:
        rows = predict(scenario_id, day, assignments, sensitivity_enabled=sensitivity_enabled, background_profile=background_profile)["predictions"]
        overlap_count = sum(bool(x["active_task_ids"] and x["existing_event_ids"]) for x in rows)
    resident_cost = metrics.total_impact_score + overlap_count * overlap_penalty
    return ScheduleCandidate(id=f"offset-{offset_minutes}", task_assignments=assignments if feasible else [], feasibility=feasible, infeasibility_reasons=reasons, needs_confirmation=["덤프트럭 소음 원천값", "미확정 공정 소요시간"] if reasons else ["덤프트럭 소음 원천값"], metrics=metrics, objective_values={"resident_cost": round(resident_cost, 2), "change_cost": float(change), "base_impact_cost": metrics.total_impact_score, "existing_noise_overlap_slots": float(overlap_count), "existing_noise_overlap_penalty": round(overlap_count * overlap_penalty, 2)}, provenance=SourceMetadata(status="derived", source="exact 15-minute offset enumeration", note="No duration reduction or parallel work assumed"))


def _dominated_reason(candidate: ScheduleCandidate, valid: list[ScheduleCandidate]) -> dict | None:
    x = candidate.objective_values
    dominators = [o for o in valid if o.id != candidate.id and o.objective_values["resident_cost"] <= x["resident_cost"] and o.objective_values["change_cost"] <= x["change_cost"] and (o.objective_values["resident_cost"] < x["resident_cost"] or o.objective_values["change_cost"] < x["change_cost"])]
    if not dominators:
        return None
    best = min(dominators, key=lambda o: (o.objective_values["resident_cost"], o.objective_values["change_cost"]))
    return {"dominated_by": best.id, "reason": "resident_cost와 change_cost가 모두 같거나 낮고 하나 이상 엄격히 낮음"}


def optimize(scenario_id: str, day: date, sensitivity_enabled: bool = True, background_profile: str = "assumed_demo") -> dict:
    scenario = get_scenario(scenario_id)
    raw = [_candidate(scenario_id, day, offset, sensitivity_enabled=sensitivity_enabled, background_profile=background_profile) for offset in range(0, 121, 15)]
    valid = [x for x in raw if x.feasibility]
    points = [{"id": x.id, **x.objective_values} for x in valid]
    ids = {x["id"] for x in non_dominated(points)}
    frontier = [x for x in valid if x.id in ids]
    selections = {}
    if frontier:
        selections["construction_convenience"] = min(frontier, key=lambda x: x.objective_values["change_cost"])
        selections["resident_protection"] = min(frontier, key=lambda x: x.objective_values["resident_cost"])
        selections["balanced"] = min(frontier, key=lambda x: x.objective_values["resident_cost"] / max(1, max(y.objective_values["resident_cost"] for y in frontier)) + x.objective_values["change_cost"] / max(1, max(y.objective_values["change_cost"] for y in frontier)))
    # Deduplicate labels that select the same candidate.
    unique = {v.id: {"character": [k for k, c in selections.items() if c.id == v.id], "candidate": v} for v in selections.values()}
    diagnostics = {
        "generated_candidate_count": len(raw), "feasible_candidate_count": len(valid),
        "infeasible_candidate_count": len(raw) - len(valid), "pareto_candidate_count": len(frontier),
        "candidate_metrics": [{"id": x.id, "feasibility": x.feasibility, "objective_values": x.objective_values, "metrics": x.metrics, "infeasibility_reasons": x.infeasibility_reasons, "dominated_reason": _dominated_reason(x, valid) if x.feasibility else None} for x in raw],
        "sensitivity_enabled": sensitivity_enabled, "background_profile": background_profile,
    }
    if not valid:
        return {"scenario_id": scenario_id, "analysis_date": day, "optimization_status": "infeasible", "valid_candidates": [], "pareto_candidates": [], "recommended_options": [], "infeasible_result": raw[0], "relaxation_guidance": ["누락 공정시간을 확인", "금지시간 또는 일일 제한을 담당자가 검토", "필요하면 다일 분할 가능 여부 확인"], "solver": "exact_enumeration", "diagnostics": diagnostics}
    return {"scenario_id": scenario_id, "analysis_date": day, "optimization_status": "optimal_enumeration", "valid_candidates": valid, "pareto_candidates": frontier, "recommended_options": list(unique.values()), "solver": "exact_enumeration", "note": "Only distinct non-dominated schedules are returned.", "diagnostics": diagnostics}
