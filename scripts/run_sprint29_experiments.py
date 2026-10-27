#!/usr/bin/env python3
"""Reproduce Sprint 29 A-F comparisons without changing source fixtures."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import date
from pathlib import Path

import ortools

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.models.domain import ConstructionPeriod, SourceMetadata, TimeWindow  # noqa: E402
from app.models.prd_v2_1 import EquipmentPlanningConstraint, PRDNoticePlanningInput  # noqa: E402
from app.services.advanced_optimizer import optimize_advanced  # noqa: E402
from app.services.data import get_scenario  # noqa: E402
from app.services.optimizer import optimize  # noqa: E402


PROFILE = "road_traffic_observed_profile"
DATES = ((date(2026, 9, 11), "final-demo-congestion"), (date(2026, 10, 7), "official_reference_equipment"))


def planning(day: date, scenario_id: str) -> tuple[PRDNoticePlanningInput, dict, dict]:
    scenario = get_scenario(scenario_id)
    notice = scenario["notice"]
    source = SourceMetadata(status="user_provided", source="Sprint 29 confirmed experiment input")
    timed = [task for task in notice.tasks if task.duration_minutes is not None]
    equipment = [EquipmentPlanningConstraint(equipment_id=task.equipment_id, category=task.name, max_daily_count=1, required_usage_minutes=task.duration_minutes, permitted_time_windows=[notice.original_work_window], source_metadata=source) for task in timed if task.equipment_id]
    return (
        PRDNoticePlanningInput(notice_id=notice.id, project_name=notice.name or notice.id, location=notice.location or "missing", construction_period=ConstructionPeriod(start=day, end=day), total_work_window=notice.original_work_window, road_excavation=False, equipment_constraints=equipment, same_day_restoration_required=False, project_completion_date=day, field_provenance={"construction_period": source, "total_work_window": source, "equipment_constraints": source}, provenance="user_provided"),
        {task.id: task.predecessors for task in timed if task.predecessors},
        {task.id: task.equipment_id for task in timed},
    )


def metrics(candidate) -> dict:
    value = candidate.metrics
    return {
        "candidate_id": candidate.id, "constraint_violation_count": len(candidate.infeasibility_reasons),
        "noise_impact": value.incremental_impact_cost,
        "continuous_high_noise_minutes": value.max_continuous_high_noise_minutes,
        "quiet_window_minutes": value.longest_quiet_window_minutes,
        "simultaneous_high_noise_minutes": None,
        "simultaneous_metric_limitation": "not represented as wall-clock minutes; existing overlap is receptor-minutes",
        "existing_noise_overlap_receptor_minutes": value.existing_noise_overlap_receptor_minutes,
        "schedule_change_minutes": value.schedule_change_minutes,
    }


def choose(candidates, keys):
    return min(candidates, key=lambda row: tuple(getattr(row.metrics, key) for key in keys) + (row.id,))


def run_day(day: date, scenario_id: str) -> dict:
    plan, predecessors, equipment_by_task = planning(day, scenario_id)
    offset = optimize(scenario_id, day, background_profile=PROFILE)
    original = next(row for row in offset["valid_candidates"] if row.id == "offset-0")
    offset_best = choose(offset["pareto_candidates"], ("incremental_impact_cost", "schedule_change_minutes"))
    advanced = optimize_advanced(scenario_id, day, plan, predecessors, equipment_by_task, set(), background_profile=PROFILE)
    advanced_best = choose(advanced["pareto_candidates"], ("incremental_impact_cost", "existing_noise_overlap_receptor_minutes", "max_continuous_high_noise_minutes", "schedule_change_minutes"))
    empty_baseline = choose(advanced["candidates"], ("existing_noise_overlap_receptor_minutes", "schedule_change_minutes"))
    insensitive = optimize_advanced(scenario_id, day, plan, predecessors, equipment_by_task, set(), background_profile=PROFILE, sensitivity_enabled=False)
    insensitive_best = choose(insensitive["pareto_candidates"], ("incremental_impact_cost", "schedule_change_minutes"))
    without_events = optimize_advanced(scenario_id, day, plan, predecessors, equipment_by_task, set(), background_profile=PROFILE, include_existing_events=False)
    without_events_best = choose(without_events["pareto_candidates"], ("incremental_impact_cost", "schedule_change_minutes"))
    weights = []
    for multiplier in (1.1, 1.3, 1.5):
        result = optimize_advanced(scenario_id, day, plan, predecessors, equipment_by_task, set(), background_profile=PROFILE, sensitivity_policy="prd_max_v2_1_experimental", experimental_context_multiplier=multiplier)
        best = choose(result["pareto_candidates"], ("incremental_impact_cost", "schedule_change_minutes"))
        weights.append({"multiplier": multiplier, "candidate_count": result["explored_candidate_count"], "pareto_count": result["pareto_candidate_count"], "result": metrics(best)})
    return {
        "analysis_date": day.isoformat(), "scenario_id": scenario_id,
        "input_data": {"background": "historical representative road-traffic LEQ profile", "sdot": "observed but excluded from synthesis", "existing_events": "scenario opt-in; 9/11 overlay is assumed", "equipment_and_distance": "official-reference/derived/assumed mixture documented by scenario provenance"},
        "A_original_vs_offset": {"candidate_count": len(offset["valid_candidates"]), "pareto_count": len(offset["pareto_candidates"]), "original": metrics(original), "offset_recommendation": metrics(offset_best)},
        "B_original_vs_advanced": {"candidate_count": advanced["explored_candidate_count"], "pareto_count": advanced["pareto_candidate_count"], "original": metrics(original), "advanced_recommendation": metrics(advanced_best)},
        "C_simple_empty_vs_advanced": {"definition": "minimum existing-event overlap, then minimum schedule change", "simple_empty": metrics(empty_baseline), "advanced_recommendation": metrics(advanced_best)},
        "D_sensitivity_off_vs_on": {"off": metrics(insensitive_best), "on": metrics(advanced_best)},
        "E_existing_event_off_vs_on": {"off": metrics(without_events_best), "on": metrics(advanced_best)},
        "F_sensitivity_weights": weights,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = {"experiment_version": "sprint29_cp_sat_v2", "environment": {"python": platform.python_version(), "platform": platform.platform(), "ortools": ortools.__version__, "grid_minutes": 15}, "global_optimality_claimed": False, "results": [run_day(day, scenario) for day, scenario in DATES]}
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
