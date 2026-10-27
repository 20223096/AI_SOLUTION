import json

import httpx
import pytest

from app.services.extractor import LLMExtractionError, LLMExtractor
from app.models.prd_v2_1 import PRDPlanningDraftRequest
from app.services.prd_v2_1 import planning_draft_from_notice


TEXT = """공사명: 신촌 보도 정비공사
위치: 서울특별시 서대문구 연세로 12 앞
공사기간: 2026-11-03 ~ 2026-11-05
작업시간: 08:00~17:00
장비: 굴착기 1대(09:00~11:00), 브레이커 2대(13:00~14:00)
작업순서: 굴착 후 포장 복구
조정 불가: 포장 복구는 당일 완료
민원 접수 전화번호는 추후 안내"""


def extractor() -> LLMExtractor:
    return LLMExtractor("openai_compatible", "gpt-4.1-mini", "test-secret")


def response_body() -> dict:
    return {
        "model": "gpt-4.1-mini-2025-04-14",
        "choices": [{"message": {"content": json.dumps({
            "notice": {
                "id": "extracted-llm", "name": "신촌 보도 정비공사",
                "location": "서울특별시 서대문구 연세로 12 앞",
                "construction_period": {"start": "2026-11-03", "end": "2026-11-05", "raw_text": "2026-11-03 ~ 2026-11-05"},
                "original_work_window": {"start": "08:00", "end": "17:00"},
                "tasks": [
                    {"id": "excavate", "name": "굴착", "equipment_id": "excavator", "duration_minutes": 120, "permitted_time_windows": [{"start": "09:00", "end": "11:00"}], "predecessors": []},
                    {"id": "restore", "name": "포장 복구", "equipment_id": None, "duration_minutes": None, "permitted_time_windows": [], "predecessors": ["excavate"]},
                ],
                "constraints": {"equipment_counts": {"excavator": 1, "breaker": 2}, "non_adjustable_conditions": ["포장 복구는 당일 완료"]},
                "source_provenance": {"document": {"status": "user_provided", "source": "request text"}},
            },
            "field_evidence": {"name": "공사명: 신촌 보도 정비공사"},
        }, ensure_ascii=False)}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }


def test_request_payload_is_offline_single_json_request_and_forbids_inference():
    payload = extractor().request_payload(TEXT)
    assert payload["model"] == "gpt-4.1-mini"
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["temperature"] == 0
    prompt = payload["messages"][0]["content"]
    assert "Never infer" in prompt and "field_evidence" in prompt and "equipment_counts" in prompt


def test_success_parses_schema_evidence_and_usage(monkeypatch):
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(200, request=request, json=response_body())
    calls = []
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or response)
    result = extractor().extract(TEXT)
    assert len(calls) == 1
    assert result["is_actual_ai"] is True
    assert result["notice"].tasks[1].predecessors == ["excavate"]
    assert result["notice"].constraints["equipment_counts"]["breaker"] == 2
    assert result["usage"]["total_tokens"] == 150
    draft = planning_draft_from_notice(PRDPlanningDraftRequest(
        notice=result["notice"], extractor_mode="llm", is_actual_ai=True,
        field_evidence=result["field_evidence"],
    ))
    assert draft["extractor_mode"] == "llm"
    assert draft["planning_draft"]["project_name"] == "신촌 보도 정비공사"
    assert "road_occupancy_permit_window" in draft["missing_fields"]


@pytest.mark.parametrize("status,category", [(401, "authentication"), (429, "billing_or_rate_limit"), (403, "model_access"), (400, "request_format")])
def test_provider_errors_are_classified_without_response_body(monkeypatch, status, category):
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(status, request=request, json={"error": {"message": "secret provider detail"}})
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response)
    with pytest.raises(LLMExtractionError) as caught:
        extractor().extract(TEXT)
    assert caught.value.category == category
    assert "secret provider detail" not in caught.value.message


def test_schema_mismatch_is_classified(monkeypatch):
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(200, request=request, json={"choices": [{"message": {"content": "{}"}}]})
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response)
    with pytest.raises(LLMExtractionError) as caught:
        extractor().extract(TEXT)
    assert caught.value.category == "structured_response_parsing"


def test_direct_notice_json_is_accepted_for_compatible_models(monkeypatch):
    body = response_body()
    wrapped = json.loads(body["choices"][0]["message"]["content"])
    body["choices"][0]["message"]["content"] = json.dumps(wrapped["notice"], ensure_ascii=False)
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(200, request=request, json=body)
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response)
    result = extractor().extract(TEXT)
    assert result["notice"].name == "신촌 보도 정비공사"
    assert result["field_evidence"] == {}
