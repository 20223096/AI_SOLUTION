import json
from datetime import date, time

import httpx
import pytest

from app.models.prd_v2_1 import PRDPlanningDraftRequest
from app.models.domain import ConstructionPeriod, SourceMetadata, TimeWindow
from app.models.prd_v2_1 import EquipmentPlanningConstraint, PRDNoticePlanningInput
from app.services.advanced_optimizer import optimize_advanced
from app.services.extractor import LLMExtractionError, LLMExtractor
from app.services.llm_extraction import LLMNoticeFacts, equipment_id_for, normalize_llm_facts
from app.services.prd_v2_1 import planning_draft_from_notice


TEXT = """공사명: 신촌 보도 정비공사
위치: 서울특별시 서대문구 연세로 12 앞
공사기간: 2026-09-11 ~ 2026-09-11
작업시간: 08:00~17:00
장비: 굴착기 1대(09:00~11:00), 브레이커 2대(13:00~14:00)
작업순서: 굴착 후 포장 복구
조정 불가: 포장 복구는 당일 완료"""


def facts(**updates) -> dict:
    value = {
        "name": "신촌 보도 정비공사", "location": "서울특별시 서대문구 연세로 12 앞",
        "construction_start": "2026-09-11", "construction_end": "2026-09-11",
        "construction_period_text": "2026-09-11 ~ 2026-09-11", "work_start": "08:00", "work_end": "17:00",
        "tasks": [
            {"name": "굴착", "equipment_name": "굴착기", "duration_minutes": None, "predecessors": []},
            {"name": "포장 복구", "equipment_name": None, "duration_minutes": None, "predecessors": ["굴착"]},
        ],
        "equipment": [
            {"name": "굴착기", "count": 1, "usage_start": "09:00", "usage_end": "11:00", "model_name": None},
            {"name": "브레이커", "count": 2, "usage_start": "13:00", "usage_end": "14:00", "model_name": None},
        ],
        "non_adjustable_conditions": ["포장 복구는 당일 완료"],
        "evidence": [
            {"field": "name", "quote": "공사명: 신촌 보도 정비공사"},
            {"field": "location", "quote": "위치: 서울특별시 서대문구 연세로 12 앞"},
            {"field": "construction_period", "quote": "공사기간: 2026-09-11 ~ 2026-09-11"},
            {"field": "original_work_window", "quote": "작업시간: 08:00~17:00"},
            {"field": "equipment", "quote": "장비: 굴착기 1대(09:00~11:00), 브레이커 2대(13:00~14:00)"},
            {"field": "tasks", "quote": "작업순서: 굴착 후 포장 복구"},
            {"field": "non_adjustable_conditions", "quote": "조정 불가: 포장 복구는 당일 완료"},
        ],
    }
    value.update(updates)
    return value


def extractor() -> LLMExtractor:
    return LLMExtractor("openai_compatible", "gpt-4.1-mini", "test-secret")


def response_body(payload: dict | None = None) -> dict:
    return {
        "model": "gpt-4.1-mini-2025-04-14",
        "choices": [{"message": {"content": json.dumps(payload or facts(), ensure_ascii=False)}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }


def test_request_payload_uses_strict_structured_outputs_offline():
    payload = extractor().request_payload(TEXT)
    response_format = payload["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"] == LLMNoticeFacts.model_json_schema()
    assert payload["temperature"] == 0
    assert "Do not assign provenance" in payload["messages"][0]["content"]


def test_success_normalizes_equipment_evidence_usage_and_s2_draft(monkeypatch):
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(200, request=request, json=response_body())
    calls = []
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or response)
    result = extractor().extract(TEXT)
    assert len(calls) == 1
    assert result["notice"].source_provenance["document"].status == "user_provided"
    assert result["notice"].tasks[0].equipment_id == "excavator"
    assert result["notice"].tasks[0].duration_minutes == 120
    assert result["notice"].tasks[-1].equipment_id == "breaker"
    assert result["notice"].constraints["equipment_counts"] == {"excavator": 1, "breaker": 2}
    assert result["field_evidence"]["name"]["evidence_exists"] is True
    assert result["usage"]["total_tokens"] == 150
    draft = planning_draft_from_notice(PRDPlanningDraftRequest(
        notice=result["notice"], extractor_mode="llm", is_actual_ai=True,
        field_evidence=result["field_evidence"],
    ))
    by_id = {row["equipment_id"]: row for row in draft["planning_draft"]["equipment_constraints"]}
    assert by_id["excavator"]["max_daily_count"] == 1
    assert by_id["breaker"]["required_usage_minutes"] == 60
    assert "equipment_constraints" not in draft["missing_fields"]


def test_missing_required_facts_are_reported_by_planning_draft():
    sparse = facts(name=None, location=None, construction_start=None, construction_end=None,
                   construction_period_text=None, work_start=None, work_end=None, tasks=[], equipment=[])
    notice, evidence, _ = normalize_llm_facts(TEXT, LLMNoticeFacts.model_validate(sparse))
    draft = planning_draft_from_notice(PRDPlanningDraftRequest(
        notice=notice, extractor_mode="llm", is_actual_ai=True, field_evidence=evidence,
    ))
    assert {"project_name", "location", "construction_period", "total_work_window", "equipment_constraints"} <= set(draft["missing_fields"])


@pytest.mark.parametrize("alias,expected", [
    ("브레이커", "breaker"), ("콘크리트 절단기", "cutter"), ("굴삭기", "excavator"),
    ("포클레인", "excavator"), ("다짐기", "roller"), ("알 수 없는 장비", None),
])
def test_explicit_equipment_aliases(alias, expected):
    assert equipment_id_for(alias) == expected


def test_unknown_equipment_and_connection_failure_require_review():
    payload = facts(
        tasks=[{"name": "특수 작업", "equipment_name": "초음파장비", "duration_minutes": 30, "predecessors": []}],
        equipment=[{"name": "초음파장비", "count": 1, "usage_start": None, "usage_end": None, "model_name": None}],
    )
    notice, _, issues = normalize_llm_facts(TEXT, LLMNoticeFacts.model_validate(payload))
    assert notice.tasks[0].equipment_id is None
    assert "unmatched_equipment:초음파장비" in issues
    assert "task_equipment_unmatched:특수 작업" in issues


def test_generated_equipment_model_is_removed_without_source_evidence():
    payload = facts(equipment=[{"name": "굴착기", "count": 1, "usage_start": "09:00", "usage_end": "11:00", "model_name": "ZX999"}])
    notice, _, issues = normalize_llm_facts(TEXT, LLMNoticeFacts.model_validate(payload))
    assert "unverified_equipment_model:굴착기" in issues
    assert "ZX999" not in json.dumps(notice.model_dump(mode="json"), ensure_ascii=False)


def test_quantity_and_usage_mismatch_are_not_silently_filled():
    payload = facts(equipment=[{"name": "굴착기", "count": None, "usage_start": "17:00", "usage_end": "09:00", "model_name": None}])
    notice, _, _ = normalize_llm_facts(TEXT, LLMNoticeFacts.model_validate(payload))
    assert notice.constraints["equipment_counts"] == {}
    assert notice.tasks[0].duration_minutes is None


def test_hallucinated_equipment_quantity_is_removed():
    payload = facts(equipment=[{"name": "굴착기", "count": 9, "usage_start": "09:00", "usage_end": "11:00", "model_name": None}])
    notice, _, issues = normalize_llm_facts(TEXT, LLMNoticeFacts.model_validate(payload))
    assert notice.constraints["equipment_counts"] == {}
    assert "unverified_equipment_count:굴착기" in issues


def test_forged_provenance_cannot_enter_strict_llm_schema():
    payload = facts()
    payload["source_provenance"] = {"document": {"status": "verified_public"}}
    with pytest.raises(ValueError):
        LLMNoticeFacts.model_validate(payload)


def test_evidence_not_in_source_is_flagged_for_review():
    payload = facts(evidence=[{"field": "name", "quote": "존재하지 않는 공사명"}])
    _, evidence, issues = normalize_llm_facts(TEXT, LLMNoticeFacts.model_validate(payload))
    assert evidence["name"]["needs_review"] is True
    assert evidence["name"]["evidence_exists"] is False
    assert "evidence_not_found:name" in issues


@pytest.mark.parametrize("status,category", [(401, "authentication"), (429, "billing_or_rate_limit"), (403, "model_access"), (400, "request_format")])
def test_provider_errors_are_classified_without_mock_fallback(monkeypatch, status, category):
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(status, request=request, json={"error": {"message": "secret provider detail"}})
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response)
    with pytest.raises(LLMExtractionError) as caught:
        extractor().extract(TEXT)
    assert caught.value.category == category
    assert "secret provider detail" not in caught.value.message


def test_schema_mismatch_is_classified_without_mock_fallback(monkeypatch):
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(200, request=request, json={"choices": [{"message": {"content": "{}"}}]})
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response)
    with pytest.raises(LLMExtractionError) as caught:
        extractor().extract(TEXT)
    assert caught.value.category == "structured_response_parsing"


def test_confirmed_llm_task_durations_reach_cp_sat_without_scenario_duration_substitution():
    source = SourceMetadata(status="user_provided", source="confirmed form")
    planning = PRDNoticePlanningInput(
        notice_id="extracted-llm", project_name="신촌 보도 정비공사", location="연세로",
        construction_period=ConstructionPeriod(start=date(2026, 9, 11), end=date(2026, 9, 11)),
        total_work_window=TimeWindow(start=time(8), end=time(17)), road_excavation=False,
        equipment_constraints=[
            EquipmentPlanningConstraint(equipment_id="excavator", category="굴착기", max_daily_count=1,
                required_usage_minutes=120, permitted_time_windows=[TimeWindow(start=time(9), end=time(11))], source_metadata=source),
            EquipmentPlanningConstraint(equipment_id="breaker", category="브레이커", max_daily_count=2,
                required_usage_minutes=60, permitted_time_windows=[TimeWindow(start=time(13), end=time(14))], source_metadata=source),
        ],
        same_day_restoration_required=True,
        field_provenance={"construction_period": source, "total_work_window": source, "road_excavation": source},
        provenance="user_provided",
    )
    result = optimize_advanced(
        "final-demo-congestion", date(2026, 9, 11), planning, {"restore": ["excavate"]},
        {"excavate": "excavator", "break": "breaker", "restore": None}, {"restore"},
        {"excavate": 120, "break": 60, "restore": 60}, solution_limit=50,
    )
    assert result["optimization_status"] == "feasible_solution_set"
    assert result["explored_candidate_count"] > 0
    assert {row.task_id for row in result["candidates"][0].task_assignments} == {"excavate", "break", "restore"}
