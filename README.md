# 쉿간표 (Shh Schedule) PoC backend

구청 담당자가 신규 공사 작업을 15분 슬롯으로 검토하고, 예상 소음·민감도·일정 변경비용을 함께 비교하는 **행정 참고용** FastAPI PoC입니다. 법적 허가, 소음 준수 인증 또는 실제 피해 감소의 증명이 아닙니다.

## 실행

Python 3.11 이상에서:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Swagger: `http://127.0.0.1:8000/docs`, 상태 확인: `GET /api/health`.

```bash
cd backend
pytest -q
```

기본 `SHH_EXTRACTOR_MODE=mock`이며 API 키 없이 전 기능이 실행됩니다. `.env.example`을 `.env`로 복사해 설정할 수 있습니다. `llm` 모드는 제공업체별 전송 구현과 키를 요구하며 설정 불완전 시 명시적으로 실패합니다.

## 설계 요약

- `app/models`: Pydantic v2 입력·출력 도메인
- `app/services`: 음향, 민감도, 점수, 최적화, Pareto, 비교, 추출
- `app/api`: FastAPI 라우터
- `app/data`: 출처 상태가 포함된 JSON 설정·시나리오
- `tests`: 손계산, 물리식, 제약, API 회귀 테스트

개발용 후보 진단은 `GET /api/schedules/optimize/{scenario_id}/diagnostics`에서 확인합니다. 기본 CASE A와 별도로 소음 집중, 시험기간, 제약 강화 실험 시나리오가 제공됩니다.

작은 시나리오에는 모든 15분 시작 오프셋을 정확 평가합니다. `requirements.txt`에 OR-Tools가 포함되어 있으나 현재 PoC 실행 경로는 재현성과 설명 가능성을 위해 정확 열거를 사용합니다.
