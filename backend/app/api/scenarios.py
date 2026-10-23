from fastapi import APIRouter, HTTPException

from app.services.data import get_scenario, scenarios

router = APIRouter(prefix="/api/poc/scenarios", tags=["scenarios"])


@router.get("")
def list_scenarios():
    return [{"id": x["id"], "title": x["title"], "expected_feasibility": x["expected_feasibility"]} for x in scenarios().values()]


@router.get("/{scenario_id}")
def scenario_detail(scenario_id: str):
    try:
        return get_scenario(scenario_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
