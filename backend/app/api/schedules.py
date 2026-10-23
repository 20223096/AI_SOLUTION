from datetime import date
from fastapi import APIRouter, HTTPException, Query

from app.models.domain import CompareRequest, OptimizeRequest
from app.services.metrics import compare
from app.services.optimizer import optimize

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


@router.post("/optimize")
def optimize_schedule(request: OptimizeRequest):
    try: return optimize(request.scenario_id, request.analysis_date, request.sensitivity_enabled)
    except KeyError as exc: raise HTTPException(404, str(exc)) from exc


@router.post("/compare")
def compare_schedules(request: CompareRequest):
    try: return compare(request.scenario_id, request.analysis_date, request.before, request.after)
    except KeyError as exc: raise HTTPException(404, str(exc)) from exc


@router.get("/optimize/{scenario_id}/diagnostics")
def optimization_diagnostics(scenario_id: str, analysis_date: date = Query(date(2026, 10, 26)), sensitivity_enabled: bool = True):
    try:
        result = optimize(scenario_id, analysis_date, sensitivity_enabled)
        return {"scenario_id": scenario_id, "analysis_date": analysis_date, **result["diagnostics"]}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
