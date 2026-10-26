from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def assignment_signature(assignments: list[Any]) -> list[dict[str, str]]:
    rows = []
    for item in assignments:
        if hasattr(item, "model_dump"):
            item = item.model_dump(mode="json")
        rows.append({"task_id": str(item["task_id"]), "start": str(item["start"]), "end": str(item["end"])})
    return sorted(rows, key=lambda row: (row["start"], row["task_id"]))


def schedule_binding_fingerprint(project_id: str, candidate_id: str, assignments: list[Any]) -> str:
    value = {"project_id": project_id, "candidate_id": candidate_id, "assignments": assignment_signature(assignments)}
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class RecommendationSnapshotRepository:
    _lock = threading.RLock()

    def __init__(self, path: Path):
        self.path = path

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": 1, "snapshots": {}}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("schema_version") != 1 or not isinstance(data.get("snapshots"), dict):
            raise RuntimeError("unsupported recommendation snapshot store schema")
        return data

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.path)

    def save_result(self, result: dict[str, Any]) -> dict[str, dict[str, str]]:
        project_id = result["input_planning"].notice_id if hasattr(result["input_planning"], "notice_id") else result["input_planning"]["notice_id"]
        metadata = {}
        with self._lock:
            data = self._read()
            for candidate in result["candidates"]:
                if not candidate["recommendable"]:
                    continue
                fingerprint = schedule_binding_fingerprint(project_id, candidate["candidate_id"], candidate["assignments"])
                snapshot_id = f"rec-{fingerprint[:24]}"
                version = f"recommendation-v1-{fingerprint[:12]}"
                data["snapshots"][snapshot_id] = {
                    "snapshot_id": snapshot_id, "project_id": project_id, "candidate_id": candidate["candidate_id"],
                    "schedule_version": version, "schedule_fingerprint": fingerprint,
                    "assignments": assignment_signature(candidate["assignments"]), "scenario_id": result["scenario_id"],
                    "analysis_date": str(result["analysis_date"]), "created_at": datetime.now(timezone.utc).isoformat(),
                    "source": "/api/prd/recommendations/constraint-filtered",
                }
                metadata[candidate["candidate_id"]] = {"schedule_snapshot_id": snapshot_id, "schedule_version": version, "schedule_fingerprint": fingerprint}
            self._write(data)
        return metadata

    def verify(self, snapshot_id: str | None, project_id: str, candidate_id: str, schedule_version: str, assignments: list[Any]) -> tuple[bool, str]:
        if not snapshot_id:
            return False, "recommendation snapshot id is required"
        with self._lock:
            snapshot = self._read()["snapshots"].get(snapshot_id)
        if not snapshot:
            return False, "recommendation snapshot not found"
        expected = schedule_binding_fingerprint(project_id, candidate_id, assignments)
        checks = (
            snapshot["project_id"] == project_id,
            snapshot["candidate_id"] == candidate_id,
            snapshot["schedule_version"] == schedule_version,
            snapshot["schedule_fingerprint"] == expected,
        )
        return (True, "verified") if all(checks) else (False, "recommendation snapshot does not match project, candidate, version, or assignments")
