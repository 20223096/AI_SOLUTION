from __future__ import annotations

import re
from datetime import date, time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.domain import ConstructionNotice, ConstructionPeriod, ConstructionTask, SourceMetadata, TimeWindow


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LLMFieldEvidence(StrictModel):
    field: str
    quote: str | None


class LLMEquipmentFact(StrictModel):
    name: str
    count: int | None = Field(ge=1)
    usage_start: str | None
    usage_end: str | None
    model_name: str | None


class LLMTaskFact(StrictModel):
    name: str
    equipment_name: str | None
    duration_minutes: int | None = Field(gt=0)
    predecessors: list[str]


class LLMNoticeFacts(StrictModel):
    name: str | None
    location: str | None
    construction_start: str | None
    construction_end: str | None
    construction_period_text: str | None
    work_start: str | None
    work_end: str | None
    tasks: list[LLMTaskFact]
    equipment: list[LLMEquipmentFact]
    non_adjustable_conditions: list[str]
    evidence: list[LLMFieldEvidence]


EQUIPMENT_ALIASES: dict[str, tuple[str, ...]] = {
    "breaker": ("브레이커", "착암기", "해머"),
    "cutter": ("콘크리트 절단기", "콘크리트절단기", "절단기", "커터", "컷터"),
    "excavator": ("굴착기", "굴삭기", "포클레인", "백호"),
    "roller": ("롤러", "다짐기", "다짐기계"),
}
EQUIPMENT_CATEGORIES = {
    "breaker": "브레이커", "cutter": "콘크리트 절단기", "excavator": "굴착기", "roller": "롤러",
}
TASK_IDS = {"breaker": "break", "cutter": "cut", "excavator": "excavate", "roller": "compact"}


def equipment_id_for(name: str | None) -> str | None:
    if not name:
        return None
    compact = re.sub(r"\s+", "", name).casefold()
    for equipment_id, aliases in EQUIPMENT_ALIASES.items():
        if any(re.sub(r"\s+", "", alias).casefold() in compact for alias in aliases):
            return equipment_id
    return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None


def _minutes(start: str | None, end: str | None) -> int | None:
    left, right = _parse_time(start), _parse_time(end)
    if left is None or right is None:
        return None
    result = (right.hour * 60 + right.minute) - (left.hour * 60 + left.minute)
    return result if result > 0 else None


def normalize_llm_facts(text: str, facts: LLMNoticeFacts) -> tuple[ConstructionNotice, dict[str, Any], list[str]]:
    """Create trusted-domain data from LLM facts; the LLM never assigns provenance."""
    evidence_by_field: dict[str, str] = {}
    reviews: dict[str, Any] = {}
    issues: list[str] = []
    for item in facts.evidence:
        quote = item.quote.strip() if item.quote else None
        exists = bool(quote and quote in text)
        if exists:
            evidence_by_field[item.field] = quote  # duplicate keys intentionally keep the last exact quote
        reviews[item.field] = {
            "evidence": quote,
            "evidence_exists": exists,
            "needs_review": not exists,
            "issues": [] if exists else ["evidence_not_found_in_source"],
        }
        if quote and not exists:
            issues.append(f"evidence_not_found:{item.field}")

    def review_value(field: str, value: Any) -> None:
        row = reviews.setdefault(field, {"evidence": None, "evidence_exists": False, "needs_review": True, "issues": ["evidence_missing"]})
        row["extracted_value"] = value

    for field, value in {
        "name": facts.name, "location": facts.location,
        "construction_period": facts.construction_period_text,
        "original_work_window": f"{facts.work_start}~{facts.work_end}" if facts.work_start and facts.work_end else None,
        "tasks": [task.model_dump() for task in facts.tasks],
        "equipment": [item.model_dump() for item in facts.equipment],
        "non_adjustable_conditions": facts.non_adjustable_conditions,
    }.items():
        review_value(field, value)
    for field, value in {
        "name": facts.name, "location": facts.location, "construction_period": facts.construction_period_text,
    }.items():
        row = reviews[field]
        if value and row["evidence_exists"] and value not in (row["evidence"] or ""):
            row["needs_review"] = True
            row["issues"].append("value_not_supported_by_evidence")
            issues.append(f"value_not_supported_by_evidence:{field}")

    equipment_facts: dict[str, LLMEquipmentFact] = {}
    unmatched: list[str] = []
    for item in facts.equipment:
        equipment_id = equipment_id_for(item.name)
        if equipment_id is None:
            unmatched.append(item.name)
            continue
        if item.model_name and item.model_name not in text:
            issues.append(f"unverified_equipment_model:{item.name}")
            item = item.model_copy(update={"model_name": None})
        if item.count is not None and f"{item.count}대" not in text.replace(" ", ""):
            issues.append(f"unverified_equipment_count:{item.name}")
            item = item.model_copy(update={"count": None})
        if item.usage_start and item.usage_start not in text:
            issues.append(f"unverified_equipment_usage_start:{item.name}")
            item = item.model_copy(update={"usage_start": None})
        if item.usage_end and item.usage_end not in text:
            issues.append(f"unverified_equipment_usage_end:{item.name}")
            item = item.model_copy(update={"usage_end": None})
        equipment_facts[equipment_id] = item
    if unmatched:
        issues.extend(f"unmatched_equipment:{name}" for name in unmatched)

    tasks: list[ConstructionTask] = []
    task_ids_by_name: dict[str, str] = {}
    for index, item in enumerate(facts.tasks, 1):
        equipment_id = equipment_id_for(item.equipment_name) or equipment_id_for(item.name)
        task_id = TASK_IDS.get(equipment_id, "restore" if "복구" in item.name else f"task-{index}")
        if task_id in task_ids_by_name.values():
            task_id = f"{task_id}-{index}"
        task_ids_by_name[item.name] = task_id
        duration = item.duration_minutes
        if equipment_id and duration is None and equipment_id in equipment_facts:
            fact = equipment_facts[equipment_id]
            duration = _minutes(fact.usage_start, fact.usage_end)
        tasks.append(ConstructionTask(
            id=task_id, name=item.name, equipment_id=equipment_id, duration_minutes=duration,
            permitted_time_windows=[], predecessors=[],
        ))
        if item.equipment_name and equipment_id is None:
            issues.append(f"task_equipment_unmatched:{item.name}")
    for task, item in zip(tasks, facts.tasks):
        task.predecessors = [task_ids_by_name[name] for name in item.predecessors if name in task_ids_by_name]
        if len(task.predecessors) != len(item.predecessors):
            issues.append(f"predecessor_unmatched:{item.name}")

    linked = {task.equipment_id for task in tasks if task.equipment_id}
    for equipment_id, item in equipment_facts.items():
        if equipment_id not in linked:
            duration = _minutes(item.usage_start, item.usage_end)
            tasks.append(ConstructionTask(
                id=TASK_IDS[equipment_id], name=f"{EQUIPMENT_CATEGORIES[equipment_id]} 사용",
                equipment_id=equipment_id, duration_minutes=duration,
                permitted_time_windows=[], predecessors=[],
            ))
            issues.append(f"equipment_task_needs_confirmation:{equipment_id}")

    start, end = _parse_date(facts.construction_start), _parse_date(facts.construction_end)
    if facts.construction_start and start is None:
        issues.append("invalid_construction_start")
    if facts.construction_end and end is None:
        issues.append("invalid_construction_end")
    work_start, work_end = _parse_time(facts.work_start), _parse_time(facts.work_end)
    work_window = TimeWindow(start=work_start, end=work_end) if work_start and work_end and work_end > work_start else None
    if (facts.work_start or facts.work_end) and work_window is None:
        issues.append("invalid_work_window")

    counts = {key: item.count for key, item in equipment_facts.items() if item.count is not None}
    models = {key: item.model_name for key, item in equipment_facts.items() if item.model_name is not None}
    usage = {
        key: [{"start": item.usage_start, "end": item.usage_end}]
        for key, item in equipment_facts.items() if item.usage_start and item.usage_end
    }
    document_status = "user_provided"
    grounded_conditions = [condition for condition in facts.non_adjustable_conditions if condition in text]
    issues.extend(f"unverified_non_adjustable_condition:{condition}" for condition in facts.non_adjustable_conditions if condition not in text)
    notice = ConstructionNotice(
        id="extracted-llm", name=facts.name, location=facts.location,
        construction_period=ConstructionPeriod(start=start, end=end, raw_text=facts.construction_period_text),
        original_work_window=work_window, tasks=tasks,
        constraints={
            "equipment_counts": counts, "equipment_usage_times": usage, "equipment_models": models,
            "non_adjustable_conditions": grounded_conditions,
        },
        source_provenance={
            "document": SourceMetadata(status=document_status, source="request text", note="Server-assigned; not official verification"),
            "llm_output": SourceMetadata(status="derived", source="OpenAI-compatible extraction", note="Unconfirmed draft"),
        },
    )
    return notice, {key: {**value} for key, value in reviews.items()}, list(dict.fromkeys(issues))
