from __future__ import annotations

import math
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from app.models.domain import M1PredictRequest
from app.services.acoustics import energy_sum
from app.services.m1_acoustics import predict_m1

KST = timezone(timedelta(hours=9))
START = datetime(2026, 10, 26, 7, 0, tzinfo=KST)
END = START + timedelta(minutes=15)


def _payload(*, lw: float = 100, active_ratio: float = 1, count: int = 1, distance_m: float = 10, background_db: float = 50, source_x: float = 200000, receptor_x: float | None = None) -> dict:
    return {
        "slot_start": START, "slot_end": END, "background_laeq_db": background_db,
        "background_provenance": "assumed", "overlap_mode": "complete_concurrent",
        "sources": [{
            "id": "source-1", "segment_id": "segment-yeonse-ro-2na-gil", "source_type": "moving_work",
            "equipment_category": "굴삭기", "sound_power_level_db": lw, "lw_provenance": "assumed",
            "count": count, "position": {"x": source_x, "y": 550000, "z_m": 1, "crs": "EPSG:5186", "provenance": "assumed"},
            "deployment_start": START, "deployment_end": END,
            "actual_active_minutes": 15 * active_ratio, "activity_provenance": "assumed",
        }],
        "receptors": [{"id": "r1", "position": {"x": receptor_x if receptor_x is not None else source_x + distance_m, "y": 550000, "z_m": 1, "crs": "EPSG:5186", "provenance": "assumed"}}],
    }


def _row(payload: dict) -> dict:
    return predict_m1(M1PredictRequest.model_validate(payload))["results"][0]


def _case(variable: str, label: str, payload: dict, provenance: str = "assumed") -> dict:
    row = _row(payload)
    return {
        "variable": variable, "label": label, "provenance": provenance,
        "slot_laeq_dba": row["slot_laeq_dba"], "total_laeq_db": row["total_laeq_db"],
        "delta_total_db": row["delta_total_db"], "energy_exposure": row["new_project_energy_exposure_65db_ref_minutes"],
        "incremental_impact": row["incremental_impact_legacy_v1"],
        "maximum_concurrent_combined_level_db": row["maximum_concurrent_combined_level_db"],
    }


def physical_cross_checks() -> dict:
    full = _row(_payload())
    half = _row(_payload(active_ratio=0.5))
    double_distance = _row(_payload(distance_m=20))
    double_count = _row(_payload(count=2))
    expected_lp = 100 - 10 * math.log10(4 * math.pi * 10**2)
    return {
        "point_source_10m": {"hand_db": expected_lp, "model_db": full["slot_laeq_dba"], "difference_db": full["slot_laeq_dba"] - expected_lp},
        "half_activity": {"hand_db": expected_lp + 10 * math.log10(0.5), "model_db": half["slot_laeq_dba"]},
        "double_distance_change_db": double_distance["slot_laeq_dba"] - full["slot_laeq_dba"],
        "double_count_change_db": double_count["slot_laeq_dba"] - full["slot_laeq_dba"],
        "three_dimensional_distance_example_m": math.sqrt(3**2 + 4**2 + 12**2),
        "maximum_concurrent_is_measured_lafmax": False,
    }


def input_sensitivity_analysis() -> dict:
    cases = []
    for label, lw in (("low", 79), ("median", 100), ("high", 114)):
        cases.append(_case("official_reference_lw", label, _payload(lw=lw, distance_m=25), "official_reference+assumed_propagation"))
    for ratio in (0.25, 0.5, 0.75, 1.0):
        cases.append(_case("activity_ratio", f"{int(ratio*100)}%", _payload(active_ratio=ratio)))
    for count in (1, 2, 4):
        cases.append(_case("equipment_count", str(count), _payload(count=count)))
    for distance in (10, 20, 40):
        cases.append(_case("receptor_distance", f"{distance}m", _payload(distance_m=distance)))
    for source_x in (199970, 199990, 200000):
        cases.append(_case("work_position_shift", f"source_x_{source_x}", _payload(source_x=source_x, receptor_x=200010)))
    for background in (50, 65, 80):
        cases.append(_case("background_level", f"{background}dB", _payload(background_db=background)))
    # Existing-event presence changes the existing environment, not construction-only energy.
    event_environment = energy_sum([50, 75])
    cases.append(_case("existing_event", "absent", _payload(background_db=50)))
    cases.append(_case("existing_event", "75dB_event_present", _payload(background_db=event_environment or 75)))
    sequential = _payload(active_ratio=1 / 3)
    second = deepcopy(sequential["sources"][0]); second["id"] = "source-2"
    sequential["sources"].append(second); sequential["overlap_mode"] = "sequential_possible"
    concurrent = deepcopy(sequential); concurrent["overlap_mode"] = "complete_concurrent"
    cases.append(_case("simultaneity", "sequential_5m+5m", sequential))
    cases.append(_case("simultaneity", "concurrent_5m+5m", concurrent))

    groups = {}
    for variable in sorted({x["variable"] for x in cases}):
        rows = [x for x in cases if x["variable"] == variable]
        groups[variable] = {
            "cases": rows,
            "slot_laeq_span_db": max(x["slot_laeq_dba"] for x in rows) - min(x["slot_laeq_dba"] for x in rows),
            "total_laeq_span_db": max(x["total_laeq_db"] for x in rows) - min(x["total_laeq_db"] for x in rows),
            "incremental_impact_span": max(x["incremental_impact"] for x in rows) - min(x["incremental_impact"] for x in rows),
            "energy_ratio": max(x["energy_exposure"] for x in rows) / min(x["energy_exposure"] for x in rows),
            "maximum_concurrent_span_db": max(x["maximum_concurrent_combined_level_db"] for x in rows) - min(x["maximum_concurrent_combined_level_db"] for x in rows),
        }
    ranks = {
        metric: [x[0] for x in sorted(groups.items(), key=lambda item: (-item[1][metric], item[0]))]
        for metric in ("slot_laeq_span_db", "total_laeq_span_db", "incremental_impact_span", "energy_ratio", "maximum_concurrent_span_db")
    }
    return {
        "analysis_type": "one_factor_deterministic_sensitivity", "confidence_interval": None,
        "probability_distribution": None, "baseline": "Lw100, 1 unit, 100% activity, 10m, background 50dB",
        "groups": groups, "rankings": ranks,
        "excluded_from_physical_ranking": {
            "sensitive_time_assumption": "policy exposure axis, not an acoustic-energy input",
            "simultaneity": "changes concurrent combined level and continuity; fixed-duration slot LAeq is unchanged",
        },
    }
