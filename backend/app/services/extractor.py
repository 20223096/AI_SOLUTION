from abc import ABC, abstractmethod
from datetime import date, time

from app.models.domain import ConstructionNotice, ConstructionPeriod, ConstructionTask, SourceMetadata, TimeWindow


class Extractor(ABC):
    @abstractmethod
    def extract(self, text: str) -> dict: ...


class LLMExtractionError(RuntimeError):
    def __init__(self, category: str, message: str, http_status: int):
        super().__init__(message)
        self.category = category
        self.message = message
        self.http_status = http_status


class MockExtractor(Extractor):
    def extract(self, text: str) -> dict:
        def has(word): return word in text
        tasks = []
        known = [("cut", "콘크리트 절단", "cutter", 60), ("break", "포장 깨기", "breaker", 120), ("excavate", "터파기", "excavator", 300), ("compact", "되메우기 및 다짐", "roller", 60)]
        previous = None
        for task_id, name, equipment, duration in known:
            if has(name) or has({"콘크리트 절단": "절단기", "포장 깨기": "브레이커", "터파기": "굴착기", "되메우기 및 다짐": "롤러"}[name]):
                tasks.append(ConstructionTask(id=task_id, name=name, equipment_id=equipment, duration_minutes=duration, predecessors=[previous] if previous else []))
                previous = task_id
        notice = ConstructionNotice(id="extracted-mock", name="연세로2나길 20 일대 외 1개소 하수관로 개량공사" if "연세로" in text else None, location="서울 서대문구 신촌역~현대백화점 인근 연세로 일대" if "신촌" in text else None, construction_period=ConstructionPeriod(raw_text="2026년 8월~12월" if "2026년" in text else None), original_work_window=TimeWindow(start=time(7), end=time(18)) if "07:00" in text and "18:00" in text else None, tasks=tasks, constraints={}, source_provenance={"document": SourceMetadata(status="user_provided", source="request text"), "unfound_fields": SourceMetadata(status="missing", note="Fields not present remain null; mock uses no inference")})
        return {"mode": "mock", "is_actual_ai": False, "notice": notice, "field_evidence": {"name": "연세로" if "연세로" in text else None}, "warnings": ["MockExtractor의 결정적 규칙 결과이며 실제 AI 추출이 아닙니다."]}


class LLMExtractor(Extractor):
    def __init__(self, provider: str | None, model: str | None, api_key: str | None, base_url: str = "https://api.openai.com/v1"):
        self.provider, self.model, self.api_key, self.base_url = provider, model, api_key, base_url

    def request_payload(self, text: str) -> dict:
        if not all([self.provider, self.model, self.api_key]):
            raise LLMExtractionError("configuration", "LLM provider/model/API key configuration is incomplete", 503)
        if self.provider != "openai_compatible":
            raise LLMExtractionError("configuration", "Supported provider value: openai_compatible", 503)
        import json
        schema = ConstructionNotice.model_json_schema()
        prompt = (
            "You extract Korean construction notices into JSON. Use only facts explicitly written in the input. "
            "Never infer dates, addresses, durations, equipment, quantities, order, or restrictions. "
            "Return one JSON object with keys notice and field_evidence. notice must match the supplied ConstructionNotice schema. "
            "For absent values use null, empty lists, or SourceMetadata status=missing as allowed by the schema. "
            "Put exact short source excerpts in field_evidence. Record explicit equipment quantities under "
            "notice.constraints.equipment_counts, explicit equipment usage times under equipment_usage_times, and explicit "
            "non-adjustable statements under non_adjustable_conditions. Set task predecessors only when order is explicit. "
            "Do not turn an overall work window into an equipment-specific window. Output JSON only. Schema: "
            + json.dumps(schema, ensure_ascii=False)
        )
        return {
            "model": self.model,
            "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": text}],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }

    def extract(self, text: str) -> dict:
        import httpx, json
        from pydantic import ValidationError

        payload = self.request_payload(text)
        try:
            response = httpx.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 401:
                category, public_status = "authentication", 503
            elif status in {402, 429}:
                category, public_status = "billing_or_rate_limit", 503
            elif status == 403:
                category, public_status = "model_access", 503
            elif status == 400:
                category, public_status = "request_format", 502
            else:
                category, public_status = "provider_error", 502
            raise LLMExtractionError(category, f"OpenAI-compatible API request failed ({status})", public_status) from exc
        except httpx.RequestError as exc:
            raise LLMExtractionError("network", "OpenAI-compatible API could not be reached", 503) from exc
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            raw = json.loads(content)
            # Older JSON-mode models occasionally return the requested notice
            # object directly instead of retaining the envelope.
            notice_raw = raw.get("notice", raw)
            evidence = raw.get("field_evidence", {}) if "notice" in raw else {}
            notice = ConstructionNotice.model_validate(notice_raw)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as exc:
            raise LLMExtractionError("structured_response_parsing", "LLM response did not match the notice extraction schema", 502) from exc
        usage = body.get("usage") or {}
        return {
            "mode": "llm", "is_actual_ai": True, "provider": self.provider,
            "model": body.get("model") or self.model, "notice": notice,
            "field_evidence": evidence,
            "usage": {key: usage.get(key) for key in ("prompt_tokens", "completion_tokens", "total_tokens") if usage.get(key) is not None},
            "warnings": ["AI extraction is an unconfirmed draft; every value requires user confirmation."],
        }
