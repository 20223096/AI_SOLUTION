import csv
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.data import get_scenario
from app.services.optimizer import optimize
from app.services.prediction import predict
from app.services.public_data import public_catalog

ROOT = Path(__file__).resolve().parents[2]


def test_official_reference_equipment_uses_observed_rows_not_averages():
    scenario = get_scenario("official_reference_equipment")
    official = {(x["equipment_category"], x["model_name"], float(x["noise_db"])) for x in public_catalog()["official_equipment_noise"]}
    mapped = {"콘크리트 절단기": "콘크리트 절단기", "브레이커": "브레이커", "굴착기": "굴착기", "롤러/다짐기계": "롤러/다짐기계"}
    for equipment in scenario["equipment"]:
        if equipment.sound_power_level_db is None:
            continue
        assert (mapped[equipment.category], equipment.model_name, equipment.sound_power_level_db) in official
        assert equipment.source_metadata.status.value == "verified_public"


def test_official_reference_scenario_retains_verified_spatial_receptors():
    scenario = get_scenario("official_reference_equipment")
    assert all(x.spatial_status == "verified_public" for x in scenario["receptors"])
    assert scenario["settings"]["recommended_background_profile"] == "road_traffic_observed_profile"


def test_congestion_event_is_explicitly_assumed():
    rows = __import__("json").loads((ROOT / "backend/app/data/existing_events.json").read_text(encoding="utf-8"))
    event = next(x for x in rows if x["scenario_group"] == "final-demo-congestion")
    assert event["provenance"]["status"] == "assumed"
    assert "unverified assumptions" in event["provenance"]["note"]


def test_background_profile_changes_values_but_not_metric_definitions():
    day = date(2026, 10, 26)
    assumed = predict("sinchon-spatial-2026", day, background_profile="assumed_demo")
    observed = predict("sinchon-spatial-2026", day, background_profile="road_traffic_observed_profile")
    a = assumed["predictions"][0]
    b = observed["predictions"][0]
    assert a["background_only_db"] != b["background_only_db"]
    assert a.keys() == b.keys()
    assert {x["background_only_db"] for x in observed["predictions"] if x["slot_start"].hour == 7} == {70.9}
    demo_metrics = optimize("case-a", day)["valid_candidates"][0].metrics.model_dump()
    spatial_metrics = optimize("sinchon-spatial-2026", day)["valid_candidates"][0].metrics.model_dump()
    assert demo_metrics.keys() == spatial_metrics.keys()


def test_final_demo_recommendation_is_deterministic():
    args = ("official_reference_equipment", date(2026, 10, 26))
    first = optimize(*args, background_profile="road_traffic_observed_profile")
    second = optimize(*args, background_profile="road_traffic_observed_profile")
    assert first == second


def test_public_schedules_remain_schedule_only():
    catalog = public_catalog()
    assert all(not x["noise_db"] for x in catalog["construction_events"] + catalog["cultural_events"])
    assert all(not x["work_start_time"] and not x["work_end_time"] for x in catalog["construction_events"])
    assert catalog["policy"]["schedule_only_events_are_energy_summed"] is False


def test_final_frontend_api_contract_is_backward_compatible():
    client = TestClient(app)
    assert client.get("/api/poc/scenarios/official_reference_equipment").status_code == 200
    request = {"scenario_id": "official_reference_equipment", "analysis_date": "2026-10-26", "background_profile": "road_traffic_observed_profile"}
    prediction = client.post("/api/noise/predict", json=request)
    optimization = client.post("/api/schedules/optimize", json=request)
    experiment = client.post("/api/experiments/run", json=request)
    assert prediction.status_code == optimization.status_code == experiment.status_code == 200
    assert {"background_only_db", "new_project_contribution_db", "delta_total_db", "incremental_impact"} <= prediction.json()["predictions"][0].keys()
    assert {"recommended_options", "pareto_candidates", "diagnostics"} <= optimization.json().keys()
