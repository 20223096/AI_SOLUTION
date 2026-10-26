from __future__ import annotations

import csv
import statistics
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from app.models.domain import DesignBasedSimulationRequest, M1NoiseSource, M1Point, M1PredictRequest, M1Receptor
from app.services.m1_acoustics import predict_m1
from app.services.pareto import non_dominated_multi
from app.services.public_data import PROCESSED, official_construction_design

KST = timezone(timedelta(hours=9))
SLOT = 15

# Durations, duty factors, work window and precedence are simulation assumptions.
# They are deliberately not derived from official quantities or the 31/31/5-day metadata.
PROCESS_TEMPLATE = [
    {"id": "cut", "name": "포장 절단", "duration": 60, "predecessors": [], "equipment": [("콘크리트 절단기", 113.0, 0.5)]},
    {"id": "break", "name": "포장 깨기", "duration": 90, "predecessors": ["cut"], "equipment": [("브레이커", 122.0, 0.5), ("굴삭기", 100.0, 0.5)]},
    {"id": "excavate", "name": "굴착", "duration": 120, "predecessors": ["break"], "equipment": [("굴삭기", 100.0, 0.5)]},
    {"id": "pipe", "name": "관 부설", "duration": 90, "predecessors": ["excavate"], "equipment": []},
    {"id": "backfill", "name": "되메우기", "duration": 75, "predecessors": ["pipe"], "equipment": [("굴삭기", 100.0, 0.5)]},
    {"id": "compact", "name": "다짐", "duration": 45, "predecessors": ["backfill"], "equipment": []},
    {"id": "pave", "name": "포장 복구", "duration": 60, "predecessors": ["compact"], "equipment": []},
]
MISSING_NOISE = ["램머 80kg", "덤프트럭 2.5/4.5/15/24t", "디젤펌프 D150mm 20hp", "관부설 장비", "포장장비"]


def _official_noise_summary() -> dict:
    path = PROCESSED / "official_equipment_noise.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = {}
    for category in ("콘크리트 절단기", "브레이커", "굴착기", "롤러/다짐기계"):
        group = [row for row in rows if row["equipment_category"] == category]
        values = [float(row["noise_db"]) for row in group]
        result[category] = {
            "record_count": len(group), "unit": "Lw_dBA", "minimum": min(values),
            "median": statistics.median(values), "maximum": max(values),
            "measurement_condition": group[0]["measurement_condition"],
            "provenance": "official_reference_noise",
        }
    return result


def design_simulation_catalog() -> dict:
    design = official_construction_design()
    segments = []
    for segment in design["segments"]:
        segments.append({
            **deepcopy(segment), "simulation_geometry": None,
            "receptor_set_id": f"{segment['id']}-simulation-receptors",
            "simulation_status": "requires_explicit_distance_or_simulation_coordinates",
        })
    return {
        "data_version": design["data_version"], "simulation_version": "design-noise-simulation-v1",
        "official_design_data": {"segments": segments, "work_packages": deepcopy(design["work_packages"]), "schedule_metadata": deepcopy(design["schedule_metadata"])},
        "official_reference_noise": _official_noise_summary(),
        "excavator_capacity_match": {
            "requested_bucket_capacities_m3": [0.2, 0.4, 0.7], "match_status": "not_classifiable",
            "reason": "753-record CSV has model names but no bucket-capacity field; numeric substrings in model names are not bucket specifications.",
            "records_must_not_be_pooled_as_capacity_matches": True,
        },
        "missing_required_inputs": MISSING_NOISE + ["official segment geometry", "segment-specific receptors", "actual equipment models", "actual operating times", "confirmed daily sequence"],
        "official_prediction_status": "deferred", "validation_status": "not_evaluable",
    }


def _base_assignments(start: datetime, break_delay: int = 0, swap_cut_break: bool = False) -> list[dict]:
    tasks = deepcopy(PROCESS_TEMPLATE)
    if swap_cut_break:
        tasks[0], tasks[1] = tasks[1], tasks[0]
    cursor = start
    assignments = []
    for task in tasks:
        if task["id"] == "break":
            cursor += timedelta(minutes=break_delay)
        end = cursor + timedelta(minutes=task["duration"])
        assignments.append({**task, "start": cursor, "end": end})
        cursor = end
    return assignments


def _validate(assignments: list[dict], workday_start: datetime, workday_end: datetime) -> list[str]:
    reasons = []
    by_id = {row["id"]: row for row in assignments}
    if min(row["start"] for row in assignments) < workday_start or max(row["end"] for row in assignments) > workday_end:
        reasons.append("assumed workday window exceeded")
    for row in assignments:
        for predecessor in row["predecessors"]:
            if predecessor not in by_id or by_id[predecessor]["end"] > row["start"]:
                reasons.append(f"precedence violation: {predecessor}->{row['id']}")
    for left_index, left in enumerate(assignments):
        for right in assignments[left_index + 1:]:
            if left["start"] < right["end"] and right["start"] < left["end"]:
                reasons.append(f"single-workfront resource conflict: {left['id']}+{right['id']}")
    return sorted(set(reasons))


def _evaluate_candidate(candidate_id: str, method: str, assignments: list[dict], request: DesignBasedSimulationRequest, overlap_mode: str, original: list[dict]) -> dict:
    day_start = datetime.combine(request.simulation_date, request.workday_start, KST)
    day_end = datetime.combine(request.simulation_date, request.workday_end, KST)
    failures = _validate(assignments, day_start, day_end)
    if failures:
        return {"id": candidate_id, "method": method, "feasible": False, "infeasibility_reasons": failures, "pareto_included": False}

    source_point = M1Point(x=0, y=0, z_m=1, crs="EPSG:5186", provenance="assumed")
    receptor_point = M1Point(x=request.distance_m, y=0, z_m=1.5, crs="EPSG:5186", provenance="assumed")
    receptor = M1Receptor(id=request.receptor_id, position=receptor_point)
    sensitive_start = datetime.combine(request.simulation_date, request.sensitive_start, KST)
    sensitive_end = datetime.combine(request.simulation_date, request.sensitive_end, KST)
    energy = 0.0
    sensitive = 0.0
    maximum_level = None
    slot_results = []
    active_known_flags = []
    cursor = day_start
    while cursor < day_end:
        end = cursor + timedelta(minutes=SLOT)
        active = [row for row in assignments if row["start"] < end and cursor < row["end"]]
        sources = []
        for task in active:
            deployed = (min(end, task["end"]) - max(cursor, task["start"])).total_seconds() / 60
            for index, (category, lw, duty) in enumerate(task["equipment"]):
                sources.append(M1NoiseSource(
                    id=f"{candidate_id}:{task['id']}:{index}:{cursor.isoformat()}", segment_id=request.segment_id,
                    source_type="impulsive" if category == "브레이커" else "moving_work", equipment_category=category,
                    count=1, sound_power_level_db=lw, lw_provenance="official_reference", position=source_point,
                    deployment_start=max(cursor, task["start"]), deployment_end=min(end, task["end"]),
                    actual_active_minutes=deployed * duty, activity_provenance="assumed", measurement_condition_verified=False,
                ))
        active_known_flags.append(bool(sources))
        if sources:
            predicted = predict_m1(M1PredictRequest(
                slot_start=cursor, slot_end=end, sources=sources, receptors=[receptor],
                background_laeq_db=request.background_laeq_db, background_provenance="assumed", overlap_mode=overlap_mode,
            ))["results"][0]
            energy += predicted["new_project_energy_exposure_65db_ref_minutes"] or 0
            maximum_level = max(maximum_level or -999, predicted["maximum_concurrent_combined_level_db"] or -999)
            if cursor < sensitive_end and sensitive_start < end:
                sensitive += SLOT
            slot_results.append(predicted)
        elif active:
            slot_results.append({
                "receptor_id": request.receptor_id, "slot_start": cursor, "slot_end": end,
                "new_project_contribution_laeq_db": None, "slot_laeq_dba": None, "total_laeq_db": None,
                "maximum_concurrent_combined_level_db": None, "calculation_status": "incomplete_missing_noise_reference",
                "active_processes": [row["id"] for row in active],
            })
        cursor = end
    run = maximum_run = 0
    for active in active_known_flags:
        run = run + SLOT if active else 0
        maximum_run = max(maximum_run, run)
    original_starts = {row["id"]: row["start"] for row in original}
    change = sum(abs(int((row["start"] - original_starts[row["id"]]).total_seconds() / 60)) for row in assignments)
    occupied = sum((row["end"] - row["start"]).total_seconds() / 60 for row in assignments)
    non_operating = int((day_end - day_start).total_seconds() / 60 - occupied)
    non_operating_intervals = []
    interval_cursor = day_start
    for row in sorted(assignments, key=lambda item: item["start"]):
        if interval_cursor < row["start"]:
            non_operating_intervals.append({"start": interval_cursor, "end": row["start"]})
        interval_cursor = max(interval_cursor, row["end"])
    if interval_cursor < day_end:
        non_operating_intervals.append({"start": interval_cursor, "end": day_end})
    return {
        "id": candidate_id, "method": method, "feasible": True, "pareto_included": False,
        "assignments": [{key: value for key, value in row.items() if key not in {"equipment", "predecessors"}} for row in assignments],
        "slot_results": slot_results,
        "metrics": {
            "new_project_energy_exposure_partial": round(energy, 6),
            "sensitive_exposure_minutes_partial": int(sensitive),
            "maximum_concurrent_combined_level_db_partial": None if maximum_level is None else round(maximum_level, 2),
            "maximum_continuous_known_noise_minutes": maximum_run,
            "existing_event_overlap_minutes": None,
            "new_project_non_operating_minutes": non_operating,
            "new_project_non_operating_intervals": non_operating_intervals,
            "project_end": max(row["end"] for row in assignments),
            "total_task_start_shift_minutes": change,
        },
        "acoustic_completeness": "partial", "missing_noise_equipment": MISSING_NOISE,
    }


def run_design_rescheduling(request: DesignBasedSimulationRequest) -> dict:
    catalog = design_simulation_catalog()
    start = datetime.combine(request.simulation_date, request.workday_start, KST)
    original = _base_assignments(start)
    specifications = [
        ("A-original", "original_schedule", original, "complete_concurrent"),
        ("B-whole-shift-60", "whole_project_start_shift", _base_assignments(start + timedelta(minutes=60)), "complete_concurrent"),
        ("C-delay-high-noise-60", "per_process_time_adjustment", _base_assignments(start, break_delay=60), "complete_concurrent"),
        ("D-sequential-break-equipment", "sequential_equipment_operation", original, "sequential_possible"),
        ("D-invalid-order-swap", "work_order_change", _base_assignments(start, swap_cut_break=True), "complete_concurrent"),
    ]
    candidates = [_evaluate_candidate(candidate_id, method, assignments, request, overlap_mode, original) for candidate_id, method, assignments, overlap_mode in specifications]
    feasible = [row for row in candidates if row["feasible"]]
    axes = ["new_project_energy_exposure_partial", "sensitive_exposure_minutes_partial", "maximum_concurrent_combined_level_db_partial", "maximum_continuous_known_noise_minutes", "total_task_start_shift_minutes"]
    points = [{"id": row["id"], **{axis: row["metrics"][axis] for axis in axes}} for row in feasible]
    frontier_ids = {row["id"] for row in non_dominated_multi(points, axes)}
    for row in feasible:
        row["pareto_included"] = row["id"] in frontier_ids
    frontier = [row for row in feasible if row["pareto_included"]]
    recommendation = min(frontier, key=lambda row: tuple(row["metrics"][axis] for axis in axes) + (row["id"],)) if frontier else None
    return {
        "simulation_version": "design-noise-simulation-v1", "result_type": "design_based_simulation",
        "official_field_prediction_status": "deferred", "simulation_status": "simulated", "validation_status": "not_evaluable",
        "segment": next(row for row in catalog["official_design_data"]["segments"] if row["id"] == request.segment_id),
        "simulation_geometry": {
            "mode": "explicit_distance_condition", "distance_m": request.distance_m, "official_geometry_unchanged": None,
            "source_point": {"x": 0, "y": 0, "z_m": 1, "crs": "EPSG:5186", "provenance": "simulation_assumption"},
            "receptor_point": {"x": request.distance_m, "y": 0, "z_m": 1.5, "crs": "EPSG:5186", "provenance": "simulation_assumption"},
            "warning": "Local relative coordinates are not cadastral or official map coordinates.",
        },
        "background_profile": {
            "id": f"{request.segment_id}-simulation-background",
            "laeq_db": request.background_laeq_db,
            "provenance": "simulation_assumption",
            "shared_with_other_segment": False,
        },
        "data_quality": {
            "official_design_data": ["segment address", "diameter", "route length", "project-wide quantities"],
            "official_reference_noise": ["cutter", "breaker", "excavator category medians"],
            "derived": ["M1 slot levels", "exposure metrics", "Pareto membership"],
            "simulation_assumption": ["distance", "receptor", "background", "daily durations", "sequence", "duty factors", "sensitive window", "workday window"],
            "missing_required_inputs": catalog["missing_required_inputs"],
        },
        "quantity_allocation": "project-wide official quantities preserved; not allocated to segment or converted to hours",
        "process_assumptions": PROCESS_TEMPLATE,
        "candidate_count": len(candidates), "feasible_candidate_count": len(feasible),
        "pareto_axes": axes, "candidates": candidates, "pareto_candidates": frontier,
        "recommended_candidate": recommendation,
        "recommendation_reasons": [] if recommendation is None else [
            {"code": "non_dominated_partial_acoustics", "evidence_fields": [f"metrics.{axis}" for axis in axes]},
            {"code": "no_cross_unit_sum", "axis_order": axes},
            {"code": "incomplete_equipment_noise", "missing": MISSING_NOISE},
        ],
        "accuracy_claim": None,
    }
