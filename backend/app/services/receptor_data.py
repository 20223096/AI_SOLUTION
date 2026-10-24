from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def residential_receptor_dataset() -> dict:
    report_path = ROOT / "data/processed/receptor_coverage_report.json"
    candidates_path = ROOT / "data/processed/receptor_candidates.csv"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    with candidates_path.open(encoding="utf-8-sig", newline="") as handle:
        candidates = list(csv.DictReader(handle))
    anchors_path = ROOT / "data/processed/official_address_anchors.json"
    return {
        "dataset_status": "official_identity_verified_osm_geometry_partial",
        "official_construction_prediction_status": "deferred",
        "validation_status": "not_evaluable",
        "report": report,
        "candidates": candidates,
        "official_address_anchors": json.loads(anchors_path.read_text(encoding="utf-8")) if anchors_path.exists() else None,
        "m1_policy": "Building centroids and address-anchor distances are not measurement receptors or construction-source distances.",
    }
