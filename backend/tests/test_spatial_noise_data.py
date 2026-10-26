import math
from datetime import date

import pytest

from app.services.data import get_scenario
from app.services.optimizer import optimize
from app.services.public_data import public_catalog
from scripts.collect_public_data.validation import geodesic_distance_m, point_to_segment_distance_m, validate_acoustic_unit


def test_construction_coordinate_is_verified_and_exposed():
    rows = public_catalog()["receptor_distances"]
    assert len(rows) == 3
    assert {row["project_id"] for row in rows} == {"6132026083144"}
    assert all(row["project_geometry_type"] == "official_representative_point" for row in rows)
    assert all(row["status"] == "verified_public_coordinates" for row in rows)


def test_wgs84_distance_matches_processed_values():
    expected = geodesic_distance_m(37.5569842, 126.9384049, 37.55814305, 126.9334809)
    row = next(x for x in public_catalog()["receptor_distances"] if x["receptor_name"] == "서울창서초등학교")
    assert float(row["distance_m"]) == pytest.approx(expected, abs=0.1)
    with pytest.raises(ValueError):
        geodesic_distance_m(91, 127, 37, 127)


def test_linear_project_minimum_distance():
    # Point directly north of the midpoint of an east-west segment.
    distance = point_to_segment_distance_m(37.001, 127.001, 37.0, 127.0, 37.0, 127.002)
    assert 105 < distance < 115
    endpoint = point_to_segment_distance_m(37.0, 126.999, 37.0, 127.0, 37.0, 127.002)
    assert 85 < endpoint < 95


def test_missing_coordinate_is_deferred_not_invented():
    with pytest.raises(TypeError):
        geodesic_distance_m(None, 127.0, 37.0, 127.0)


def test_verified_spatial_scenario_is_separate_from_assumed_baseline():
    assumed = get_scenario("case-a")
    verified = get_scenario("sinchon-spatial-2026")
    assert assumed["receptors"][0].spatial_status is None
    assert all(x.spatial_status == "verified_public" for x in verified["receptors"])
    assert min(x.distance_to_source_m for x in verified["receptors"]) > 200


def test_official_equipment_has_explicit_lw_and_provenance():
    rows = public_catalog()["official_equipment_noise"]
    assert rows
    assert {"콘크리트 절단기", "브레이커", "굴착기", "롤러/다짐기계"} <= {x["equipment_category"] for x in rows}
    assert all(validate_acoustic_unit(x["acoustic_unit_type"]) == "Lw_dBA" for x in rows)
    assert all(x["model_name"] and float(x["noise_db"]) > 0 and x["source_url"] for x in rows)
    assert not any(x["equipment_category"] == "덤프트럭" for x in rows)


def test_existing_equipment_values_are_not_relabelled_official():
    scenario = get_scenario("sinchon-spatial-2026")
    assert all(e.source_metadata.status.value in {"user_provided", "missing"} for e in scenario["equipment"])


def test_existing_calculation_regression_and_new_scenario_runs():
    baseline = optimize("case-a", date(2026, 10, 26))
    spatial = optimize("sinchon-spatial-2026", date(2026, 10, 26))
    assert baseline["diagnostics"]["generated_candidate_count"] == 9
    assert spatial["diagnostics"]["generated_candidate_count"] == 9
    assert spatial["valid_candidates"]
