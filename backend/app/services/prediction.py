from datetime import date, datetime, time, timedelta

from app.models.domain import TaskAssignment
from app.services.acoustics import energy_sum, sound_power_to_pressure, source_noise
from app.services.background_profiles import profile_level
from app.services.data import get_scenario, load_json_rows
from app.services.impact import calculate_impact
from app.models.domain import ImpactRequest
from app.services.sensitivity import sensitivity
from app.services.public_data import calendar_overlaps, is_exam_period
from app.services.timegrid import TZ, at, overlaps, slots


def default_assignments(scenario: dict, day: date) -> list[TaskAssignment]:
    notice = scenario["notice"]
    cursor = at(day, notice.original_work_window.start)
    out = []
    tasks = {x.id: x for x in notice.tasks}
    for task in notice.tasks:
        if task.duration_minutes is None:
            continue
        end = cursor + __import__("datetime").timedelta(minutes=task.duration_minutes)
        out.append(TaskAssignment(task_id=task.id, start=cursor, end=end))
        cursor = end
    return out


def _within_windows(moment: datetime, windows: list[dict]) -> bool:
    for window in windows:
        start = at(moment.date(), datetime.strptime(window["start"], "%H:%M").time())
        end = at(moment.date(), datetime.strptime(window["end"], "%H:%M").time())
        if start <= moment < end:
            return True
    return False


def predict(scenario_id: str, day: date, assignments: list[TaskAssignment] | None = None, sensitivity_enabled: bool = True, background_profile: str = "assumed_demo") -> dict:
    scenario = get_scenario(scenario_id)
    assignments = default_assignments(scenario, day) if assignments is None else assignments
    equipment = {x.id: x.model_dump(mode="json") for x in scenario["equipment"]}
    tasks = {x.id: x for x in scenario["notice"].tasks}
    catalog = load_json_rows("equipment_noise.json")
    backgrounds = load_json_rows("background_noise.json")
    existing_events = load_json_rows("existing_events.json")
    settings = scenario.get("settings", {})
    event_group = settings.get("existing_event_group")
    allow_assumed_event_acoustics = bool(settings.get("allow_assumed_event_acoustics", False))
    analysis_start, analysis_end = at(day, time(7)), at(day, time(18))
    results, warnings = [], []
    for eq in equipment.values():
        if eq["sound_power_level_db"] is None:
            warnings.append(f"{eq['category']}: source noise missing; excluded from numeric prediction")
    for receptor in scenario["receptors"]:
        for start, end in slots(analysis_start, analysis_end):
            construction_levels, active = [], []
            sources = []
            for assignment in assignments:
                if not overlaps(start, end, assignment.start, assignment.end):
                    continue
                task = tasks[assignment.task_id]
                if not task.equipment_id:
                    continue
                value, meta = source_noise(equipment[task.equipment_id], catalog)
                sources.append({"equipment_id": task.equipment_id, "source": meta})
                if value is not None:
                    construction_levels.append(sound_power_to_pressure(value, receptor.distance_to_source_m))
                    active.append(task.id)
            construction_db = energy_sum(construction_levels)
            bg_hit = next((x for x in backgrounds if x["receptor_id"] == receptor.id and x["time"] == start.strftime("%H:%M")), None) if background_profile == "assumed_demo" else None
            if background_profile == "assumed_demo":
                background_db = float(bg_hit["laeq_db"]) if bg_hit else settings.get("default_background_laeq_db")
                background_meta = bg_hit["source_metadata"] if bg_hit else settings.get("source_metadata", {"status": "missing", "note": "No background value for slot", "unit": "LAeq_dBA"})
            else:
                background_db, background_meta, profile_warnings = profile_level(background_profile, start)
                warnings.extend(profile_warnings)
            if background_db is None:
                warnings.append(f"{receptor.id} {start.strftime('%H:%M')}: background noise missing; no fallback value inserted")
            event_levels, event_ids, event_sources = [], [], []
            for event in existing_events:
                if event.get("scenario_group") != event_group or receptor.id not in event.get("receptor_ids", []):
                    continue
                event_start = at(day, datetime.strptime(event["start_time"], "%H:%M").time())
                event_end = at(day, datetime.strptime(event["end_time"], "%H:%M").time())
                if overlaps(start, end, event_start, event_end):
                    level = event.get("source_noise_data", {}).get("level_db")
                    if level is None:
                        warnings.append(f"{event['id']}: existing noise level missing; excluded")
                    elif event.get("provenance", {}).get("status") != "verified_public" and not allow_assumed_event_acoustics:
                        warnings.append(f"{event['id']}: unverified acoustic event excluded; calendar/context only")
                    else:
                        acoustic_basis = "verified_observation" if event.get("provenance", {}).get("status") == "verified_public" else "assumed_simulation_opt_in"
                        event_levels.append(float(level)); event_ids.append(event["id"]); event_sources.append(event["provenance"] | {"acoustic_basis": acoustic_basis})
            existing_db = energy_sum(event_levels)
            baseline_levels = ([background_db] if background_db is not None else []) + ([existing_db] if existing_db is not None else [])
            existing_environment_db = energy_sum(baseline_levels)
            numeric_levels = baseline_levels + ([construction_db] if construction_db is not None else [])
            total_db = energy_sum(numeric_levels)
            calendar_institution = settings.get("public_data_calendar_institution")
            calendar_exam = is_exam_period(day, calendar_institution) if calendar_institution else False
            exam_active = (bool(settings.get("exam_period")) or calendar_exam) and _within_windows(start, settings.get("exam_windows", [{"start":"00:00", "end":"23:59"}]))
            sensitivity_data = sensitivity(start, receptor.type, exam_period=exam_active) if sensitivity_enabled else {"time_period":"disabled", "base_weight":1.0, "adjustments":{}, "weight":1.0, "is_sensitive_time":False, "weight_status":"disabled", "status":"disabled_for_experiment"}
            if sensitivity_enabled and calendar_exam and receptor.type == "university":
                sensitivity_data = {**sensitivity_data, "status": "derived", "calendar_source_status": "processed", "calendar_institution": calendar_institution}
            total_impact = baseline_impact = incremental_impact = 0.0
            saturation = {"score_at_ceiling": False, "level_component_at_ceiling": False, "incremental_zero_despite_physical_increase": False}
            delta_total_db = 0.0
            if total_db is not None and existing_environment_db is not None:
                delta_total_db = max(0.0, total_db - existing_environment_db) if construction_db is not None else 0.0
                total_result = calculate_impact(ImpactRequest(total_noise_db=total_db, threshold_db=65, duration_minutes=15 if total_db >= 65 else 0, continuous_minutes=15 if total_db >= 65 else 0, sensitivity_weight=sensitivity_data["weight"]))
                baseline_result = calculate_impact(ImpactRequest(total_noise_db=existing_environment_db, threshold_db=65, duration_minutes=15 if existing_environment_db >= 65 else 0, continuous_minutes=15 if existing_environment_db >= 65 else 0, sensitivity_weight=sensitivity_data["weight"]))
                total_impact, baseline_impact = total_result["score"], baseline_result["score"]
                incremental_impact = max(0.0, round(total_impact - baseline_impact, 2)) if construction_db is not None else 0.0
                saturation = {"score_at_ceiling": total_impact >= 100, "level_component_at_ceiling": total_result["components"]["level"] >= 1, "incremental_zero_despite_physical_increase": delta_total_db > 0 and incremental_impact == 0}
                if saturation["incremental_zero_despite_physical_increase"]:
                    warnings.append(f"{receptor.id} {start.strftime('%H:%M')}: incremental Impact is zero despite positive physical dB increase due to score clipping/rounding")
            results.append({"receptor_id": receptor.id, "slot_start": start, "slot_end": end, "active_task_ids": active, "construction_lp_db": None if construction_db is None else round(construction_db, 2), "new_project_contribution_db": None if construction_db is None else round(construction_db, 2), "background_laeq_db": background_db, "background_only_db": background_db, "existing_noise_lp_db": None if existing_db is None else round(existing_db, 2), "existing_environment_db": None if existing_environment_db is None else round(existing_environment_db, 2), "existing_event_ids": event_ids, "total_estimated_db": None if total_db is None else round(total_db, 2), "with_new_project_db": None if total_db is None else round(total_db, 2), "delta_total_db": round(delta_total_db, 2), "total_impact": total_impact, "baseline_impact": baseline_impact, "incremental_impact": incremental_impact, "impact_saturation": saturation, "sensitivity": sensitivity_data, "source_metadata": {"background": background_meta, "equipment": sources, "existing_events": event_sources}})
    return {"scenario_id": scenario_id, "analysis_date": day, "model_version": "poc-0.1.0", "scoring_version": "legacy_v1", "timezone": "Asia/Seoul", "slot_minutes": 15, "background_profile": background_profile, "public_data_calendar_institution": settings.get("public_data_calendar_institution"), "calendar_overlaps": calendar_overlaps(day), "existing_event_acoustic_policy": {"verified_events_allowed": True, "assumed_events_allowed": allow_assumed_event_acoustics, "assumed_event_use": "simulation_only" if allow_assumed_event_acoustics else "excluded"}, "predictions": results, "warnings": sorted(set(warnings)), "legal_assessment": None, "disclaimer": "예측 모델값이며 법적 측정·평가값 또는 적합 판정이 아닙니다."}
