from abc import ABC, abstractmethod
from datetime import date, time

from app.models.domain import ConstructionNotice, ConstructionPeriod, ConstructionTask, SourceMetadata, TimeWindow


class Extractor(ABC):
    @abstractmethod
    def extract(self, text: str) -> dict: ...


class MockExtractor(Extractor):
    def extract(self, text: str) -> dict:
        def has(word): return word in text
        tasks = []
        is_final_demo = "연세로2나길 20 일대 외 1개소 하수관로 개량공사" in text
        known = [("cut", "콘크리트 절단", "cutter", 60), ("break", "포장 깨기", "breaker", 120), ("excavate", "터파기", "excavator", 180 if is_final_demo else 300), ("compact", "되메우기·다짐" if is_final_demo else "되메우기 및 다짐", "roller", 60)]
        previous = None
        for task_id, name, equipment, duration in known:
            alias = {"cut": "절단기", "break": "브레이커", "excavate": "굴착기", "compact": "롤러"}[task_id]
            if has(name) or has(alias):
                windows = [TimeWindow(start=time(8), end=time(17))] if is_final_demo else []
                tasks.append(ConstructionTask(id=task_id, name=name, equipment_id=equipment, duration_minutes=duration, permitted_time_windows=windows, predecessors=[previous] if previous else []))
                previous = task_id
        period = ConstructionPeriod(start=date(2026, 8, 31), end=date(2026, 12, 18), raw_text="2026.08.31 ~ 2026.12.18") if is_final_demo else ConstructionPeriod(raw_text="2026년 8월~12월" if "2026년" in text else None)
        constraints = {"road_excavation": True, "same_day": True, "equipment_count": 1} if is_final_demo else {}
        notice = ConstructionNotice(id="extracted-mock", name="연세로2나길 20 일대 외 1개소 하수관로 개량공사" if "연세로" in text else None, location="서울특별시 서대문구 연세로2나길 20 일대 외 1개소" if is_final_demo else ("서울 서대문구 신촌역~현대백화점 인근 연세로 일대" if "신촌" in text else None), construction_period=period, original_work_window=TimeWindow(start=time(7), end=time(18)) if "07:00" in text and "18:00" in text else None, tasks=tasks, constraints=constraints, source_provenance={"document": SourceMetadata(status="user_provided", source="request text"), "unfound_fields": SourceMetadata(status="missing", note="Fields not present remain null; mock uses no inference")})
        return {"mode": "mock", "is_actual_ai": False, "notice": notice, "field_evidence": {"name": "연세로" if "연세로" in text else None}, "warnings": ["MockExtractor의 결정적 규칙 결과이며 실제 AI 추출이 아닙니다."]}


class LLMExtractor(Extractor):
    def __init__(self, provider: str | None, model: str | None, api_key: str | None, base_url: str = "https://api.openai.com/v1"):
        self.provider, self.model, self.api_key, self.base_url = provider, model, api_key, base_url

    def extract(self, text: str) -> dict:
        if not all([self.provider, self.model, self.api_key]):
            raise RuntimeError("LLM provider/model/API key configuration is incomplete")
        if self.provider != "openai_compatible":
            raise RuntimeError("Supported provider value: openai_compatible")
        import httpx, json
        schema = ConstructionNotice.model_json_schema()
        prompt = "Extract only explicitly present values. Use null/missing for absent data. Return JSON matching this schema: " + json.dumps(schema, ensure_ascii=False)
        response = httpx.post(f"{self.base_url.rstrip('/')}/chat/completions", headers={"Authorization": f"Bearer {self.api_key}"}, json={"model": self.model, "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": text}], "response_format": {"type": "json_object"}}, timeout=30)
        response.raise_for_status()
        raw = json.loads(response.json()["choices"][0]["message"]["content"])
        return {"mode": "llm", "is_actual_ai": True, "provider": self.provider, "model": self.model, "notice": ConstructionNotice.model_validate(raw), "warnings": []}
