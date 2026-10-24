from __future__ import annotations

import csv
import math
from datetime import datetime
from functools import lru_cache

from app.models.domain import ImpactRequest, M1NoiseSource, M1Point, M1PredictRequest, M1ScheduleEvaluationRequest, M1UncertaintyRequest
from app.services.acoustics import energy_sum, reference_energy_exposure, sound_power_to_pressure
from app.services.impact import calculate_impact
from app.services.optimizer import optimize
from app.services.pareto import non_dominated_multi
from app.services.prediction import predict
from app.services.public_data import PROCESSED
from app.services.timegrid import slots

SLOT_MINUTES = 15.0
SUPPORTED_PROJECTED_CRS = {"EPSG:5179", "EPSG:5186"}
REFERENCE_CATEGORY = {
    "콘크리트 절단기": "콘크리트 절단기",
    "절단기": "콘크리트 절단기",
    "브레이커": "브레이커",
    "굴삭기": "굴착기",
    "굴착기": "굴착기",
    "롤러": "롤러/다짐기계",
}
PROHIBITED_REFERENCE_CATEGORIES = {"램머", "덤프트럭", "디젤펌프", "펌프"}
CORRECTION_KEYS = ("ground", "atmospheric", "barrier", "building", "reflection", "meteorology")


@lru_cache
def _official_rows() -> list[dict]:
    with (PROCESSED / "official_equipment_noise.csv").open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def distance_3d_m(source: M1Point, receptor: M1Point) -> float:
    if source.crs != receptor.crs:
        raise ValueError("source and receptor CRS must match; implicit CRS transformation is not allowed")
    if source.crs == "EPSG:4326":
        if not (-180 <= source.x <= 180 and -90 <= source.y <= 90 and -180 <= receptor.x <= 180 and -90 <= receptor.y <= 90):
            raise ValueError("invalid EPSG:4326 longitude/latitude")
        radius = 6_371_008.8
        lat1, lat2 = math.radians(source.y), math.radians(receptor.y)
        dlat, dlon = lat2 - lat1, math.radians(receptor.x - source.x)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        horizontal = radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    elif source.crs in SUPPORTED_PROJECTED_CRS:
        horizontal = math.hypot(receptor.x - source.x, receptor.y - source.y)
    else:  # protected by the Pydantic literal; retained for direct-call safety
        raise ValueError(f"unsupported CRS: {source.crs}")
    return math.hypot(horizontal, receptor.z_m - source.z_m)


def resolve_official_lw(source: M1NoiseSource) -> tuple[float | None, dict]:
    if source.sound_power_level_db is not None:
        return source.sound_power_level_db, {
            "provenance": source.lw_provenance,
            "selection": "explicit_input",
            "measurement_condition_verified": source.measurement_condition_verified,
        }
    if source.equipment_category in PROHIBITED_REFERENCE_CATEGORIES:
        return None, {"provenance": "unknown", "status": "missing_noise_reference", "reason": "substitution with another equipment class is prohibited"}
    category = REFERENCE_CATEGORY.get(source.equipment_category)
    if category is None:
        return None, {"provenance": "unknown", "status": "missing_noise_reference", "reason": "no compatible official inspection category"}
    rows = [row for row in _official_rows() if row["equipment_category"] == category]
    if source.equipment_model:
        hits = [row for row in rows if row["model_name"] == source.equipment_model]
        if len(hits) != 1:
            return None, {"provenance": "unknown", "status": "model_match_failed", "reason": "exactly one same-category model record is required"}
        hit = hits[0]
        return float(hit["noise_db"]), {
            "provenance": "official_reference", "status": "exact_model_reference",
            "model_name": hit["model_name"], "approval_number": hit["approval_number"],
            "source_url": hit["source_url"], "measurement_condition": hit["measurement_condition"],
            "measurement_condition_verified": False,
            "note": "model reference only; field operating condition is not verified",
        }
    if source.reference_scenario is None:
        return None, {"provenance": "unknown", "status": "missing_noise_reference", "reason": "model or low/median/high reference_scenario is required"}
    ordered = sorted(rows, key=lambda row: (float(row["noise_db"]), row["model_name"], row["approval_number"]))
    index = {"low": 0, "median": (len(ordered) - 1) // 2, "high": len(ordered) - 1}[source.reference_scenario]
    hit = ordered[index]
    return float(hit["noise_db"]), {
        "provenance": "official_reference", "status": "category_distribution_reference",
        "reference_scenario": source.reference_scenario, "category": category, "record_count": len(rows),
        "model_name": hit["model_name"], "approval_number": hit["approval_number"],
        "source_url": hit["source_url"], "measurement_condition": hit["measurement_condition"],
        "measurement_condition_verified": False,
        "note": "distribution reference; not confirmed site equipment or operating condition",
    }


def _overlap_minutes(start: datetime, end: datetime, slot_start: datetime, slot_end: datetime) -> float:
    return max(0.0, (min(end, slot_end) - max(start, slot_start)).total_seconds() / 60)


def _active_minutes(source: M1NoiseSource, request: M1PredictRequest) -> tuple[float | None, str]:
    deployed = _overlap_minutes(source.deployment_start, source.deployment_end, request.slot_start, request.slot_end)
    if deployed <= 0:
        return 0.0, "outside_slot"
    if source.active_intervals:
        clipped = sorted(
            (max(x.start, request.slot_start, source.deployment_start), min(x.end, request.slot_end, source.deployment_end))
            for x in source.active_intervals
            if min(x.end, request.slot_end, source.deployment_end) > max(x.start, request.slot_start, source.deployment_start)
        )
        merged = []
        for start, end in clipped:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        value = sum((end - start).total_seconds() / 60 for start, end in merged)
        return value, "explicit_intervals"
    if source.actual_active_minutes is not None:
        if source.actual_active_minutes > deployed:
            raise ValueError(f"{source.id}: actual_active_minutes exceeds deployment overlap in slot")
        return source.actual_active_minutes, "explicit_active_minutes"
    return None, "unknown"


def _corrections(request: M1PredictRequest) -> tuple[float, dict]:
    applied = 0.0
    details = {}
    for key in CORRECTION_KEYS:
        item = request.corrections.get(key)
        if item is None or item.status == "not_modelled":
            details[key] = {"status": "not_modelled", "value_db": None}
        else:
            applied += item.value_db or 0.0
            details[key] = item.model_dump()
    return applied, details


def _pair_overlap_bounds(a: float, b: float, slot_minutes: float = SLOT_MINUTES) -> dict:
    return {
        "minimum_overlap_minutes": max(0.0, a + b - slot_minutes),
        "maximum_overlap_minutes": min(a, b),
        "complete_sequential_feasible": a + b <= slot_minutes,
    }


def _exact_temporal_metrics(active: list[dict]) -> tuple[float | None, dict]:
    events = []
    pairwise = []
    intervals_by_id = {row["id"]: row["active_intervals"] for row in active}
    for row in active:
        for interval in row["active_intervals"]:
            events.append((interval.start, 1, row["full_activity_lp_db"], row["id"]))
            events.append((interval.end, -1, row["full_activity_lp_db"], row["id"]))
    for index, left in enumerate(active):
        for right in active[index + 1:]:
            overlap = sum(
                max(0.0, (min(a.end, b.end) - max(a.start, b.start)).total_seconds() / 60)
                for a in intervals_by_id[left["id"]] for b in intervals_by_id[right["id"]]
            )
            pairwise.append({"source_ids": [left["id"], right["id"]], "actual_overlap_minutes": overlap})
    current, maximum, max_count = {}, None, 0
    for moment, direction, level, source_id in sorted(events, key=lambda x: (x[0], x[1])):
        if direction < 0:
            current.pop(source_id, None)
        else:
            current[source_id] = level
            value = energy_sum(current.values())
            maximum = value if maximum is None else max(maximum, value or maximum)
            max_count = max(max_count, len(current))
    all_intervals = sorted((interval.start, interval.end) for row in active for interval in row["active_intervals"])
    merged = []
    for start, end in all_intervals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    maximum_continuous = max(((end - start).total_seconds() / 60 for start, end in merged), default=0.0)
    return maximum, {
        "mode": "exact", "bound": "explicit interval overlap", "pairwise_overlap": pairwise,
        "maximum_concurrent_source_count": max_count,
        "maximum_continuous_construction_noise_minutes": round(maximum_continuous, 6),
    }


def _peak_level(source_rows: list[dict], mode: str) -> tuple[float | None, dict]:
    active = [row for row in source_rows if row["active_minutes"] > 0]
    if not active:
        return None, {"mode": mode, "interpretation": "no active source"}
    levels = [row["full_activity_lp_db"] for row in active]
    durations = [row["active_minutes"] for row in active]
    total_activity = sum(durations)
    sequential_feasible = total_activity <= SLOT_MINUTES
    minimum_concurrency = max(1, math.ceil(total_activity / SLOT_MINUTES - 1e-12))
    concurrent = energy_sum(levels)
    sequential = max(levels)
    pairwise = []
    for index, left in enumerate(active):
        for right in active[index + 1:]:
            pairwise.append({"source_ids": [left["id"], right["id"]], **_pair_overlap_bounds(left["active_minutes"], right["active_minutes"])})
    temporal = {
        "total_source_activity_minutes": total_activity,
        "complete_sequential_feasible": sequential_feasible,
        "minimum_feasible_concurrent_source_count": minimum_concurrency,
        "maximum_concurrent_source_count": len(active),
        "pairwise_overlap": pairwise,
        "maximum_continuous_construction_noise_minutes_range": {
            "minimum": max(durations), "maximum": min(SLOT_MINUTES, total_activity)
        },
    }
    if mode == "complete_concurrent":
        return concurrent, {"mode": mode, "bound": "complete temporal overlap assumption", **temporal}
    if mode == "sequential_possible":
        if not sequential_feasible:
            raise ValueError(f"complete sequential operation is infeasible: {total_activity:g} source-minutes exceed {SLOT_MINUTES:g}-minute slot")
        return sequential, {"mode": mode, "bound": "feasible non-overlap assumption", **temporal}
    if mode == "overlap_unknown":
        meta = {"mode": mode, "maximum_possible_combined_level_db": round(concurrent, 2), "confidence_interval": None, **temporal}
        if len(active) == 2:
            required = pairwise[0]["minimum_overlap_minutes"]
            minimum_peak = concurrent if required > 0 else sequential
            meta["minimum_feasible_combined_level_db"] = round(minimum_peak, 2)
            meta["minimum_peak_basis"] = "two-source overlap capacity exact bound"
        else:
            average_energy_bound = 10 * math.log10(sum(10 ** (level / 10) * duration / SLOT_MINUTES for level, duration in zip(levels, durations)))
            meta["minimum_feasible_combined_level_db"] = None
            meta["minimum_peak_lower_bound_db"] = round(max(sequential, average_energy_bound), 2)
            meta["minimum_peak_basis"] = "multi-source lower bound; exact ordering is unspecified"
        return None, meta
    if not all(row["active_intervals"] for row in active):
        return None, {"mode": mode, "reason": "exact mode requires active_intervals", **temporal}
    return _exact_temporal_metrics(active)


def predict_m1(request: M1PredictRequest) -> dict:
    missing = []
    resolved = []
    correction_db, correction_details = _corrections(request)
    for source in request.sources:
        active_minutes, activity_basis = _active_minutes(source, request)
        lw, lw_meta = resolve_official_lw(source)
        if active_minutes is None:
            missing.append({"source_id": source.id, "field": "actual_active_minutes", "status": "unknown"})
        if source.position is None:
            missing.append({"source_id": source.id, "field": "position", "status": "unknown"})
        if lw is None:
            missing.append({"source_id": source.id, "field": "sound_power_level_db", **lw_meta})
        resolved.append((source, active_minutes, activity_basis, lw, lw_meta))
    for receptor in request.receptors:
        if receptor.position is None:
            missing.append({"receptor_id": receptor.id, "field": "position", "status": "unknown"})
    if missing:
        return {
            "model_version": "M1_physical_v1", "calculation_status": "deferred",
            "validation_status": "not_evaluable", "missing_required_inputs": missing,
            "results": [], "corrections": correction_details,
            "disclaimer": "입력 결손으로 확정 거리·음향 계산을 수행하지 않았습니다.",
        }

    results = []
    for receptor in request.receptors:
        rows = []
        linear_slot_energy = 0.0
        for source, active_minutes, activity_basis, lw, lw_meta in resolved:
            assert source.position is not None and receptor.position is not None and active_minutes is not None and lw is not None
            distance = distance_3d_m(source.position, receptor.position)
            if distance <= 0:
                raise ValueError("source-to-receptor 3D distance must be greater than zero")
            lp_one = sound_power_to_pressure(lw, distance, correction_db)
            lp_count = lp_one + 10 * math.log10(source.count)
            fraction = active_minutes / SLOT_MINUTES
            if fraction > 0:
                linear_slot_energy += 10 ** (lp_count / 10) * fraction
            rows.append({
                "id": source.id, "segment_id": source.segment_id, "source_type": source.source_type,
                "equipment_category": source.equipment_category, "equipment_model": source.equipment_model,
                "simultaneous_group": source.simultaneous_group,
                "count": source.count, "lw_db": lw, "lw_source": lw_meta,
                "distance_3d_m": round(distance, 3), "full_activity_lp_db": lp_count,
                "source_position": source.position.model_dump(), "receptor_position": receptor.position.model_dump(),
                "active_minutes": active_minutes, "activity_ratio": round(fraction, 6),
                "activity_basis": activity_basis, "activity_provenance": source.activity_provenance,
                "active_intervals": source.active_intervals,
                "measurement_condition_verified": source.measurement_condition_verified,
            })
        construction = 10 * math.log10(linear_slot_energy) if linear_slot_energy > 0 else None
        total = energy_sum(([request.background_laeq_db] if request.background_laeq_db is not None else []) + ([construction] if construction is not None else []))
        delta = (total - request.background_laeq_db) if total is not None and request.background_laeq_db is not None and construction is not None else None
        incremental_impact = None
        if total is not None and request.background_laeq_db is not None:
            total_impact = calculate_impact(ImpactRequest(total_noise_db=total, threshold_db=65, duration_minutes=15 if total >= 65 else 0, continuous_minutes=15 if total >= 65 else 0, sensitivity_weight=1))["score"]
            baseline_impact = calculate_impact(ImpactRequest(total_noise_db=request.background_laeq_db, threshold_db=65, duration_minutes=15 if request.background_laeq_db >= 65 else 0, continuous_minutes=15 if request.background_laeq_db >= 65 else 0, sensitivity_weight=1))["score"]
            incremental_impact = max(0.0, round(total_impact - baseline_impact, 2))
        peak, peak_meta = _peak_level(rows, request.overlap_mode)
        active_values = [row["active_minutes"] for row in rows if row["active_minutes"] > 0]
        continuous_range = None if not active_values else {
            "minimum_minutes": max(active_values),
            "maximum_minutes": min(SLOT_MINUTES, sum(active_values)),
            "interpretation": "range from complete overlap to sequential union; not a confidence interval",
        }
        if request.overlap_mode == "exact" and peak_meta.get("maximum_continuous_construction_noise_minutes") is not None:
            exact_continuous = peak_meta["maximum_continuous_construction_noise_minutes"]
            continuous_range = {"minimum_minutes": exact_continuous, "maximum_minutes": exact_continuous, "interpretation": "explicit interval union"}
        maximum_concurrent_level = peak if peak is not None else peak_meta.get("maximum_possible_combined_level_db")
        results.append({
            "receptor_id": receptor.id, "slot_start": request.slot_start, "slot_end": request.slot_end,
            "new_project_contribution_laeq_db": None if construction is None else round(construction, 2),
            "slot_laeq_dba": None if construction is None else round(construction, 2),
            "total_laeq_db": None if total is None else round(total, 2),
            "delta_total_db": None if delta is None else round(delta, 2),
            "new_project_energy_exposure_65db_ref_minutes": None if construction is None else round(reference_energy_exposure(construction, SLOT_MINUTES), 6),
            "incremental_impact_legacy_v1": incremental_impact,
            "max_simultaneous_lp_db": None if peak is None else round(peak, 2),
            "maximum_concurrent_combined_level_db": None if maximum_concurrent_level is None else round(maximum_concurrent_level, 2),
            "measured_lafmax_dba": None,
            "simultaneity": peak_meta, "continuous_new_project_exposure": continuous_range,
            "sources": [{key: value for key, value in row.items() if key not in {"full_activity_lp_db", "active_intervals"}} for row in rows],
        })
    return {
        "model_version": "M1_physical_v1", "calculation_status": "simulated" if any(s.activity_provenance == "assumed" or (s.position and s.position.provenance == "assumed") for s in request.sources) else "calculated",
        "validation_status": "not_evaluable", "slot_minutes": 15, "overlap_mode": request.overlap_mode,
        "background": {"laeq_db": request.background_laeq_db, "provenance": request.background_provenance},
        "corrections": correction_details, "results": results, "missing_required_inputs": [],
        "accuracy_claim": None, "disclaimer": "M1 계산 차이는 입력 세분화 효과이며 실측 검증 전 정확도 향상을 의미하지 않습니다.",
    }


def compare_m0_m1(request: M1PredictRequest) -> dict:
    m1 = predict_m1(request)
    if m1["calculation_status"] == "deferred":
        return {"comparison_status": "deferred", "m1": m1, "validation_status": "not_evaluable"}
    m0_payload = request.model_copy(deep=True)
    m0_payload.overlap_mode = "complete_concurrent"
    for source in m0_payload.sources:
        source.actual_active_minutes = SLOT_MINUTES
        source.activity_provenance = "assumed"
        source.active_intervals = []
    m0 = predict_m1(m0_payload)
    m0["model_version"] = "M0_representative_point_assumption"
    comparisons = []
    for old, new in zip(m0["results"], m1["results"]):
        comparisons.append({
            "receptor_id": new["receptor_id"],
            "m0_new_project_laeq_db": old["new_project_contribution_laeq_db"],
            "m1_new_project_laeq_db": new["new_project_contribution_laeq_db"],
            "m0_total_laeq_db": old["total_laeq_db"], "m1_total_laeq_db": new["total_laeq_db"],
            "m0_delta_total_db": old["delta_total_db"], "m1_delta_total_db": new["delta_total_db"],
            "m0_energy_exposure": old["new_project_energy_exposure_65db_ref_minutes"],
            "m1_energy_exposure": new["new_project_energy_exposure_65db_ref_minutes"],
            "m0_incremental_impact": old["incremental_impact_legacy_v1"],
            "m1_incremental_impact": new["incremental_impact_legacy_v1"],
        })
    return {
        "comparison_status": "simulated", "validation_status": "not_evaluable",
        "m0_characterization": "representative_point_assumption with explicit 100% slot activity",
        "m1_characterization": "activity-duration energy averaging and explicit simultaneity",
        "comparisons": comparisons, "m0": m0, "m1": m1,
        "accuracy_improvement_claimed": False,
    }


def validation_metrics(predicted: list[float], measured: list[float]) -> dict:
    if not measured:
        return {"validation_status": "not_evaluable", "mae": None, "rmse": None, "bias": None}
    if len(predicted) != len(measured) or not predicted:
        raise ValueError("predicted and measured values must be non-empty and aligned")
    errors = [p - m for p, m in zip(predicted, measured)]
    return {
        "validation_status": "evaluated", "sample_count": len(errors),
        "mae": sum(abs(x) for x in errors) / len(errors),
        "rmse": math.sqrt(sum(x * x for x in errors) / len(errors)),
        "bias": sum(errors) / len(errors),
    }


def analyze_uncertainty(request: M1UncertaintyRequest) -> dict:
    """Evaluate caller-declared one-factor cases; never invent a probability distribution."""
    cases = []
    for case in request.cases:
        prediction = predict_m1(case.request)
        cases.append({"id": case.id, "varied_variable": case.varied_variable, "prediction": prediction})
    metrics = ("new_project_contribution_laeq_db", "total_laeq_db", "delta_total_db", "new_project_energy_exposure_65db_ref_minutes", "incremental_impact_legacy_v1")
    ranges = []
    receptor_ids = sorted({row["receptor_id"] for case in cases for row in case["prediction"].get("results", [])})
    for receptor_id in receptor_ids:
        summary = {"receptor_id": receptor_id, "metrics": {}}
        for metric in metrics:
            values = []
            for case in cases:
                row = next((x for x in case["prediction"].get("results", []) if x["receptor_id"] == receptor_id), None)
                if row is not None and row.get(metric) is not None:
                    values.append({"case_id": case["id"], "value": row[metric]})
            summary["metrics"][metric] = {
                "minimum": min((x["value"] for x in values), default=None),
                "maximum": max((x["value"] for x in values), default=None),
                "case_values": values,
            }
        ranges.append(summary)
    return {
        "analysis_type": "deterministic_sensitivity_cases", "probability_distribution": None,
        "confidence_interval": None, "validation_status": "not_evaluable",
        "cases": cases, "ranges": ranges,
        "note": "Ranges are declared-assumption scenario bounds, not statistical confidence intervals.",
    }


def evaluate_m1_schedule_candidates(request: M1ScheduleEvaluationRequest) -> dict:
    """Score only candidates already found feasible by the existing optimizer."""
    missing = []
    receptor_ids = {x.id for x in request.receptors}
    for receptor in request.receptors:
        if receptor.position is None:
            missing.append({"receptor_id": receptor.id, "field": "position", "status": "unknown"})
    for mapping in request.task_mappings:
        if mapping.position is None:
            missing.append({"task_id": mapping.task_id, "field": "position", "status": "unknown"})
        if mapping.active_ratio is None:
            missing.append({"task_id": mapping.task_id, "field": "active_ratio", "status": "unknown"})
    if missing:
        return {"evaluation_status": "deferred", "validation_status": "not_evaluable", "missing_required_inputs": missing, "candidates": [], "pareto_candidates": []}

    base = optimize(request.scenario_id, request.analysis_date, background_profile=request.background_profile)
    mappings = {x.task_id: x for x in request.task_mappings}
    expected_tasks = {assignment.task_id for candidate in base.get("valid_candidates", []) for assignment in candidate.task_assignments}
    unmapped = sorted(expected_tasks - mappings.keys())
    if unmapped:
        return {"evaluation_status": "deferred", "validation_status": "not_evaluable", "missing_required_inputs": [{"task_id": x, "field": "task_acoustic_mapping", "status": "unknown"} for x in unmapped], "candidates": [], "pareto_candidates": []}

    evaluated = []
    for candidate in base.get("valid_candidates", []):
        baseline = predict(request.scenario_id, request.analysis_date, candidate.task_assignments, background_profile=request.background_profile)["predictions"]
        baseline_index = {(row["receptor_id"], row["slot_start"]): row for row in baseline}
        slot_start = min(row["slot_start"] for row in baseline)
        slot_end = max(row["slot_end"] for row in baseline)
        energy = impact = 0.0
        sensitive_minutes = overlap_minutes = 0
        active_slot_flags = []
        slot_results = []
        deferred = []
        for start, end in slots(slot_start, slot_end):
            active_assignments = [x for x in candidate.task_assignments if x.start < end and start < x.end]
            active_slot_flags.append(bool(active_assignments))
            sources = []
            for assignment in active_assignments:
                mapping = mappings[assignment.task_id]
                deployed_start, deployed_end = max(start, assignment.start), min(end, assignment.end)
                deployed_minutes = (deployed_end - deployed_start).total_seconds() / 60
                sources.append(M1NoiseSource(
                    id=f"{candidate.id}:{assignment.task_id}:{start.isoformat()}", segment_id=mapping.segment_id,
                    source_type=mapping.source_type, equipment_category=mapping.equipment_category,
                    equipment_model=mapping.equipment_model, count=mapping.count,
                    sound_power_level_db=mapping.sound_power_level_db, lw_provenance=mapping.lw_provenance,
                    reference_scenario=mapping.reference_scenario, position=mapping.position,
                    deployment_start=deployed_start, deployment_end=deployed_end,
                    actual_active_minutes=deployed_minutes * (mapping.active_ratio or 0),
                    activity_provenance=mapping.activity_provenance,
                    simultaneous_group=mapping.simultaneous_group,
                    measurement_condition_verified=mapping.measurement_condition_verified,
                ))
            if not sources:
                continue
            for receptor in request.receptors:
                base_row = baseline_index.get((receptor.id, start))
                if base_row is None:
                    deferred.append({"receptor_id": receptor.id, "slot_start": start, "field": "matching_scenario_receptor"})
                    continue
                m1_request = M1PredictRequest(
                    slot_start=start, slot_end=end, sources=sources, receptors=[receptor],
                    background_laeq_db=base_row["existing_environment_db"], background_provenance="derived",
                    overlap_mode=request.overlap_mode,
                )
                result = predict_m1(m1_request)
                if result["calculation_status"] == "deferred":
                    deferred.extend(result["missing_required_inputs"])
                    continue
                row = result["results"][0]
                energy += row["new_project_energy_exposure_65db_ref_minutes"] or 0
                impact += row["incremental_impact_legacy_v1"] or 0
                if base_row["sensitivity"]["is_sensitive_time"]:
                    sensitive_minutes += 15
                if base_row["existing_event_ids"]:
                    overlap_minutes += 15
                slot_results.append(row)
        if deferred:
            evaluated.append({"id": candidate.id, "feasibility": False, "evaluation_status": "deferred", "missing_required_inputs": deferred})
            continue
        current = maximum_run = 0
        for active in active_slot_flags:
            current = current + 15 if active else 0
            maximum_run = max(maximum_run, current)
        axes = {
            "new_project_energy_exposure": round(energy, 6),
            "sensitive_exposure_receptor_minutes": sensitive_minutes,
            "maximum_continuous_exposure_upper_bound_minutes": maximum_run,
            "existing_event_overlap_receptor_minutes": overlap_minutes,
            "incremental_impact_legacy_v1": round(impact, 2),
            "schedule_change_minutes": candidate.metrics.schedule_change_minutes,
        }
        evaluated.append({
            "id": candidate.id, "feasibility": True, "evaluation_status": "simulated",
            "task_assignments": candidate.task_assignments, "objective_axes": axes,
            "slot_results": slot_results,
            "input_provenance": {"positions": sorted({x.position.provenance for x in request.task_mappings if x.position}), "activities": sorted({x.activity_provenance for x in request.task_mappings})},
        })
    feasible = [x for x in evaluated if x.get("feasibility")]
    pareto_axes = ["new_project_energy_exposure", "sensitive_exposure_receptor_minutes", "maximum_continuous_exposure_upper_bound_minutes", "schedule_change_minutes"]
    points = [{"id": x["id"], **x["objective_axes"]} for x in feasible]
    frontier_points = non_dominated_multi(points, pareto_axes)
    frontier_ids = {x["id"] for x in frontier_points}
    frontier = [x for x in feasible if x["id"] in frontier_ids]
    recommendation = min(frontier, key=lambda x: tuple(x["objective_axes"][axis] for axis in pareto_axes) + (x["id"],)) if frontier else None
    reasons = [] if recommendation is None else [
        {"code": "non_dominated_m1", "evidence_fields": [f"objective_axes.{axis}" for axis in pareto_axes]},
        {"code": "lexicographic_reference_without_cross_unit_sum", "axis_order": pareto_axes},
        {"code": "simulation_inputs_not_field_verified", "provenance": recommendation["input_provenance"]},
    ]
    return {
        "evaluation_status": "simulated", "validation_status": "not_evaluable",
        "scenario_id": request.scenario_id, "base_optimizer_unchanged": True,
        "generated_candidate_count": base["diagnostics"]["generated_candidate_count"],
        "feasible_candidate_count": len(feasible), "candidates": evaluated,
        "pareto_axes": pareto_axes, "pareto_candidates": frontier,
        "recommended_candidate": recommendation, "recommendation_reasons": reasons,
        "note": "M1 evaluates only existing optimizer-feasible candidates; no objective weights were adjusted.",
    }
