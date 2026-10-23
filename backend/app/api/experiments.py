from fastapi import APIRouter, HTTPException

from app.models.domain import ExperimentRequest
from app.services.data import get_scenario
from app.services.metrics import compare
from app.services.optimizer import optimize
from app.services.prediction import default_assignments

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


@router.post("/run")
def experiments(request: ExperimentRequest):
    try:
        scenario = get_scenario(request.scenario_id)
        optimized = optimize(request.scenario_id, request.analysis_date, sensitivity_enabled=True, background_profile=request.background_profile, objective_mode=request.objective_mode)
        physical_optimized = optimize(request.scenario_id, request.analysis_date, sensitivity_enabled=False, background_profile=request.background_profile, objective_mode=request.objective_mode)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    original = default_assignments(scenario, request.analysis_date)
    options = optimized.get("recommended_options", [])
    experiment_a = compare(request.scenario_id, request.analysis_date, original, options[0]["candidate"].task_assignments, background_profile=request.background_profile) if options else {"status": "not_run", "reason": "no feasible recommendation"}
    physical_options = physical_optimized.get("recommended_options", [])
    experiment_b = {"status": "completed" if options else "not_run", "without_sensitivity": [{"candidate_id": x["candidate"].id, "objective_values": x["candidate"].objective_values} for x in physical_options], "with_sensitivity": [{"candidate_id": x["candidate"].id, "objective_values": x["candidate"].objective_values} for x in options], "recommendation_changed": [x["candidate"].id for x in physical_options] != [x["candidate"].id for x in options], "note": "Sensitivity changes impact only, never physical dB."}
    experiment_c = [{"character": x["character"], "candidate_id": x["candidate"].id, "resident_cost": x["candidate"].objective_values["resident_cost"], "change_cost": x["candidate"].objective_values["change_cost"]} for x in options]
    return {"scenario_id": request.scenario_id, "analysis_date": request.analysis_date, "objective_mode": request.objective_mode, "experiment_a": experiment_a, "experiment_b": experiment_b, "experiment_c": experiment_c, "disclaimer": "실험용 모델 비교이며 실제 주민 피해 감소의 입증이 아닙니다."}
