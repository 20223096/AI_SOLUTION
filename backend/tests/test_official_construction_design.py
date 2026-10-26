from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.services.data import get_scenario
from app.services.prediction import predict
from app.services.public_data import (
    construction_design_distance_ready,
    official_construction_design,
    public_catalog,
)


def _items(design):
    return [item for package in design["work_packages"] for item in package["items"]]


def test_two_official_segments_are_separate_without_shared_coordinates():
    design = official_construction_design()
    assert [x["id"] for x in design["segments"]] == [
        "segment-yeonse-ro-2na-gil",
        "segment-chungjeong-ro",
    ]
    assert all(x["geometry"] is None and x["representative_point"] is None for x in design["segments"])
    assert {x["nominal_address"] for x in design["segments"]} == {"연세로2나길 20 일대", "충정로 35-17 일대"}


def test_segment_lengths_sum_to_official_total():
    design = official_construction_design()
    assert sum(x["route_length_m"] for x in design["segments"]) == 483
    assert design["route_length_total_m"] == {
        "value": 483,
        "provenance": "derived",
        "derivation": "328 + 155; 공사설명서와 물량내역서 갑지의 공식 총연장 483m와 일치",
    }


def test_design_quantities_preserve_value_unit_and_source_cell():
    design = official_construction_design()
    items = _items(design)
    asphalt_cut = next(x for x in items if x["name"] == "포장절단(아스팔트)")
    pumping = next(x for x in items if x["name"] == "물푸기")
    assert (asphalt_cut["quantity"], asphalt_cut["unit"], asphalt_cut["source_reference"]) == (1095, "m", "물량내역서!A15:D15")
    assert (pumping["quantity"], pumping["unit"], pumping["source_reference"]) == (328, "hr", "물량내역서!A95:D95")
    assert "자동 변환하지 않음" in pumping["quantity_interpretation"]


def test_actual_equipment_models_and_operating_times_remain_unknown():
    equipment = [e for item in _items(official_construction_design()) for e in item["equipment"]]
    assert equipment
    assert all(e["actual_model"] is None and e["actual_operating_time"] is None for e in equipment)


def test_official_noise_is_not_assigned_to_wrong_equipment_classes():
    matches = {x["design_equipment"]: x for x in official_construction_design()["equipment_reference_matching"]}
    assert matches["램머 80kg"]["match_status"] == "classification_mismatch"
    assert matches["램머 80kg"]["direct_noise_assignment_allowed"] is False
    assert matches["덤프트럭 2.5/4.5/15/24t"]["reference_count"] == 0
    assert matches["디젤펌프 D150mm 20hp"]["reference_category"] is None
    assert all(x["direct_noise_assignment_allowed"] is False for x in matches.values())


def test_67_day_estimate_is_not_a_daily_work_schedule():
    schedule = official_construction_design()["schedule_metadata"]
    assert schedule["working_days"]["value"] == 67
    assert sum(schedule[key]["value"] for key in ("earthwork_and_backfill_days", "pipe_installation_days", "paving_days")) == 67
    assert schedule["daily_work_window"] == {"value": None, "provenance": "unknown"}
    assert schedule["calendar_schedule"] == {"value": None, "provenance": "unknown"}


def test_existing_single_day_demo_remains_assumed_and_regression_stable():
    scenario = get_scenario("case-a")
    assert scenario["settings"]["source_metadata"]["status"] == "assumed"
    assert str(scenario["notice"].original_work_window.start) == "07:00:00"
    assert str(scenario["notice"].original_work_window.end) == "18:00:00"
    assert sum(task.duration_minutes or 0 for task in scenario["notice"].tasks) == 540
    result = predict("case-a", date(2026, 10, 26))
    assert result["scenario_id"] == "case-a"
    assert result["predictions"]
    assert official_construction_design()["assumed_demo_schedule_reference"]["isolated_from_official_schedule"] is True


def test_distance_and_acoustic_prediction_are_deferred_without_gis():
    design = official_construction_design()
    assert all(not construction_design_distance_ready(segment) for segment in design["segments"])
    readiness = design["calculation_readiness"]
    assert readiness["distance_calculation"] == "deferred"
    assert readiness["acoustic_prediction"] == "deferred"
    assert "segment_geometry_or_source_point" in readiness["missing_required_inputs"]


def test_catalog_and_dedicated_endpoint_add_fields_without_breaking_catalog():
    client = TestClient(app)
    catalog = client.get("/api/public-data/catalog")
    endpoint = client.get("/api/public-data/construction-design")
    assert catalog.status_code == endpoint.status_code == 200
    assert endpoint.json()["data_version"] == "official-construction-design-v1"
    assert catalog.json()["official_construction_design"] == endpoint.json()
    assert public_catalog()["policy"]["official_design_is_acoustic_scenario"] is False

