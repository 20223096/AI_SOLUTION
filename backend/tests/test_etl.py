import csv
import shutil
from datetime import datetime

import pytest

from app.services import background_profiles
from app.services.background_profiles import profile_catalog, profile_level
from app.services.optimizer import optimize
from app.services.prediction import predict
from scripts.noise_etl import normalize_sdot_row, parse_sensor_time, process_sdot, sha256_file


def header():
    values = [f"unused-{i}" for i in range(59)]
    for _, (index, name) in __import__("scripts.noise_etl", fromlist=["SDOT_REQUIRED"]).SDOT_REQUIRED.items():
        values[index] = name
    return values


def row(neighborhood="Sinchon-dong", observed="2026-08-10_00:07:00", low="39", avg="40", high="43"):
    values = [""] * 59
    values[0:6] = ["SDOT001", "SERIAL-1", observed, "roads_and_parks", "Seodaemun-gu", neighborhood]
    values[24:27] = [high, avg, low]
    values[57:59] = ["2026-08-10 00:07:31", "1"]
    return values


def write_cp949(path, rows):
    with path.open("w", encoding="cp949", newline="") as stream:
        writer = csv.writer(stream); writer.writerow(header()); writer.writerows(rows)


def test_cp949_filter_time_duplicate_and_provenance(tmp_path):
    first = tmp_path / "one.csv"; duplicate = tmp_path / "two.csv"
    write_cp949(first, [row(), row(neighborhood="Yeonhui-dong")]); shutil.copyfile(first, duplicate)
    report, records = process_sdot([first, duplicate], tmp_path / "clean.csv")
    assert report["duplicate_files"] == 1
    assert report["sinchon_rows"] == 1 and len(records) == 1
    assert records[0]["observed_at"].endswith("+09:00")
    assert "verified_public" in records[0]["provenance"]
    assert sha256_file(first) == sha256_file(duplicate)


def test_logical_duplicate_missing_and_abnormal_are_held(tmp_path):
    path = tmp_path / "rows.csv"
    write_cp949(path, [row(), row(), row(observed="2026-08-10_00:12:00", low="", avg="40", high="43"), row(observed="2026-08-10_00:17:00", low="50", avg="40", high="43"), row(observed="2026-08-10_00:22:00", low="-1", avg="1", high="2")])
    report, records = process_sdot([path], tmp_path / "clean.csv")
    assert report["logical_duplicate_rows"] == 1
    assert report["missing_counts"]["noise_min"] == 1
    assert report["abnormal_counts"]["min_avg_max_order_violation"] == 1
    assert report["abnormal_counts"]["negative_noise_value"] == 1
    assert len(records) == 1


def test_profile_types_and_incompatible_metric_guard():
    profiles = profile_catalog()
    assert profiles["assumed_demo"]["source_metadata"]["status"] == "assumed"
    assert profiles["sdot_observed_profile"]["source_metadata"]["status"] == "verified_public"
    assert profiles["sdot_observed_profile"]["calculation_eligible"] is False
    with pytest.raises(ValueError):
        profile_level("sdot_observed_profile", datetime(2026, 10, 26, 7))


def test_observed_road_profile_is_explicit_and_not_default():
    default = predict("case-a", __import__("datetime").date(2026, 10, 26))
    observed = predict("case-a", __import__("datetime").date(2026, 10, 26), background_profile="road_traffic_observed_profile")
    assert default["background_profile"] == "assumed_demo"
    assert observed["background_profile"] == "road_traffic_observed_profile"
    assert any("과거 시간대별 중앙값" in warning for warning in observed["warnings"])


def test_observed_profile_changes_hourly_background_and_total_noise():
    day = __import__("datetime").date(2026, 10, 26)
    assumed = predict("case-a", day)
    observed = predict("case-a", day, background_profile="road_traffic_observed_profile")
    def at_hour(rows, hour):
        return next(x for x in rows["predictions"] if x["receptor_id"] == "residential-1" and x["slot_start"].hour == hour)
    assert at_hour(observed, 7)["background_laeq_db"] == 70.9
    assert at_hour(observed, 8)["background_laeq_db"] == 71.5
    assert at_hour(observed, 7)["total_estimated_db"] != at_hour(assumed, 7)["total_estimated_db"]
    assert 0 <= at_hour(observed, 7)["total_estimated_db"] < 200
    metadata = at_hour(observed, 7)["source_metadata"]["background"]
    assert metadata["value_status"] == "derived"
    assert metadata["spatial_application_status"] == "assumed"


def test_observed_profile_is_deterministic_and_keeps_period_source():
    day = __import__("datetime").date(2026, 10, 26)
    first = optimize("case-a", day, background_profile="road_traffic_observed_profile")
    second = optimize("case-a", day, background_profile="road_traffic_observed_profile")
    assert [(x.id, x.objective_values) for x in first["pareto_candidates"]] == [(x.id, x.objective_values) for x in second["pareto_candidates"]]
    profile = profile_catalog()["road_traffic_observed_profile"]
    assert profile["observation_period"] == {"start":"2025-01-01", "end":"2026-06-30"}
    assert profile["source_metadata"]["status"] == "verified_public"


def test_missing_profile_hour_returns_none_and_warning(monkeypatch):
    monkeypatch.setattr(background_profiles, "profile_catalog", lambda: {"partial":{"id":"partial","calculation_eligible":True,"hourly_values":[],"source_metadata":{"status":"derived"},"observation_period":None,"metric":"LEQ","quality_warnings":[]}})
    value, metadata, warnings = background_profiles.profile_level("partial", datetime(2026, 10, 26, 7))
    assert value is None and metadata["status"] == "derived"
    assert "no representative value" in warnings[0]
