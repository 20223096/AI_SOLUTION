# Sprint 32 실제 GPT Structured Outputs 최종 검증

검증일: 2026-10-27  
기준 커밋: `7c97a322a48a70013fe7108c6f6902211d593a66`

## 결론

비식별 신고서로 OpenAI API를 정확히 한 번 호출했다. HTTP 200을 받았고 `gpt-4.1-mini-2025-04-14`가 strict JSON Schema를 수용했으며 반환 JSON은 `LLMNoticeFacts` Pydantic 검증을 통과했다. 자동 재시도와 다른 LLM 호출은 없었다.

모델은 대부분의 명시 사실과 evidence를 정확히 반환했지만 브레이커를 `포장 복구` 작업에 연결한 오류가 있었다. 실제 응답을 오프라인 회귀 fixture로 추가하고 서버가 복구 작업의 장비·duration을 자동 승인하지 않도록 최소 후처리를 보완했다. 따라서 실제 GPT 결과는 S2 사용자 검토 전에는 S3~S4로 확정되지 않는다.

## 사전 점검

| 설정 | 결과 |
|---|---|
| `SHH_EXTRACTOR_MODE` | `llm` |
| `SHH_LLM_PROVIDER` | `openai_compatible` |
| `SHH_LLM_MODEL` | `gpt-4.1-mini` |
| `SHH_LLM_BASE_URL` | `https://api.openai.com/v1` |
| `SHH_LLM_API_KEY` | 설정됨; 값 미출력 |

Pydantic schema의 객체 4개 모두 `additionalProperties:false`이며 모든 property가 required다. 선택값은 null union으로 표현된다. 금지 조합 키워드는 없고 schema 크기는 2,751자, 객체 깊이와 property 수도 공식 제한 안이다.

## 실제 API 호출

- 호출 횟수: 1
- endpoint: `POST /v1/chat/completions`
- 요청 형식: `response_format.type=json_schema`, `strict=true`
- HTTP status: 200
- 요청 모델: `gpt-4.1-mini`
- 실제 모델 ID: `gpt-4.1-mini-2025-04-14`
- Pydantic 검증: 성공
- refusal: 없음
- 입력 토큰: 1,612
- 출력 토큰: 401
- 총 토큰: 2,013
- 추정 비용: 약 USD 0.0012864

추정 비용은 입력 USD 0.40/백만 토큰, 출력 USD 1.60/백만 토큰을 단순 적용했다. 실제 청구 내역이 최종 기준이다.

## 필드별 정확도

| 필드 | 실제 GPT 결과 | 판정 |
|---|---|---|
| 공사명 | 신촌 보도 정비공사 | 정확 |
| 주소 | 서울특별시 서대문구 연세로 12 앞 | 정확 |
| 기간 | 2026-09-11~2026-09-11 | 정확 |
| 전체 작업시간 | 08:00~17:00 | 정확 |
| 굴착기 | 1대, 09:00~11:00 | 정확 |
| 브레이커 | 2대, 13:00~14:00 | 정확 |
| 작업 순서 | 굴착 후 포장 복구 | 정확 |
| 당일 복구 | 포장 복구는 당일 완료 | 정확 |
| 굴착 작업 연결 | `excavate` / `excavator`, 120분 | 명시된 장비시간 기반 연결 가능 |
| 복구 작업 연결 | 브레이커/60분으로 반환 | 오류; 서버에서 거부 |
| 장비 모델 | null | 정확; 임의 모델 없음 |
| provenance | LLM schema에 없음 | 서버만 부여 |

서버 후처리 결과는 다음과 같다.

- 굴착: `excavate` → `excavator`, 120분
- 브레이커: 별도 `break` 작업, `breaker`, 60분, 사용자 작업 의미 확인 필요
- 포장 복구: `restore`, 장비 없음, duration 없음, 사용자 입력 필요
- 선후관계: `restore` predecessor `excavate`
- 당일 복구: `same_day=true`
- provenance: 원문 `user_provided`, LLM 변환 `derived`

## Evidence 검증

GPT가 반환한 evidence 10개는 모두 원문에 존재했다. 기간과 작업시간은 모델이 atomic field evidence를 반환했기 때문에 서버가 두 값을 모두 포함하는 정확한 원문 행을 찾아 기존 aggregate 필드인 `construction_period`, `original_work_window`로 묶는다.

후처리 전에는 aggregate 필드명이 달라 불필요한 `needs_review`가 발생했으나 수정 후 해소됐다. `tasks`는 잘못된 장비 연결이 감지되어 `needs_review=true`다. 나머지 명시 필드는 근거가 존재하며 검토 issue가 없다. 이는 사용자 확인 절차 자체를 생략한다는 뜻은 아니다.

## S1~S4 연계

### 실제 GPT 응답 경로

1. S1 strict 추출 및 Pydantic 검증: 성공
2. 서버 evidence/provenance 검증: 성공
3. S2 JUSO 주소 조회: `resolved`, `exact`
4. S2 자동 확정: 중단
5. 중단 사유: 복구 작업 duration 미확인, 브레이커 작업 의미 확인, 도로굴착 여부 확인 필요
6. S3/S4: 실제 사용자 확인 전 실행하지 않음

### 시험용 사용자 확인 fixture

사용자 확인값을 명시한 fixture에서는 굴착 120분, 브레이커 60분, 복구 60분과 장비·수량·선후관계를 S3로 전달했다. S3 duration 및 제약 검증을 거쳐 S4 CP-SAT이 feasible 후보 집합을 생성했다. 이는 실제 사용자의 승인을 대신하지 않으며 연결 회귀만 검증한다.

## 기존 결과 보호

- CP-SAT 알고리즘과 offset baseline 변경 없음
- 2026-09-11: Impact 7.36, CP-SAT 후보 495, Pareto 35 유지
- 2026-10-07: offset 13.72→13.20 유지
- 2026-10-07: CP-SAT 13.72→13.12, 후보 495, Pareto 18 유지
- JUSO 설정 변경 없음
- API 키 및 개인정보 tracked 파일 기록 없음

## 테스트 결과

- 백엔드: 296 passed
- 프론트엔드: 17 passed
- TypeScript/Vite production build: 성공
- lint: 성공
- mock 기반 Chromium S1~S8 E2E: 1 passed
- 실제 GPT 포함 브라우저 E2E: 미실행; 두 번째 GPT 호출 방지
- Sprint 29 비교실험: 기존 정량 결과 유지

## 변경 사항

- 실제 응답에서 확인된 복구 작업 장비 오연결 방지
- aggregate evidence를 원문 행으로 서버 집계
- 당일 복구 조건과 조정 불가 조건을 S2 초안까지 전달
- 실제 Sprint 32 응답 형태 회귀 테스트 추가
- OpenAPI, TypeScript 계약 및 planning example 갱신

## 남은 한계

1. 브레이커가 어떤 공정에 사용되는지는 원문에 없으므로 사용자 확인이 필요하다.
2. 포장 복구 duration은 원문에 없어 사용자가 입력해야 한다.
3. 도로 굴착 여부와 도로점용 허가시간은 주소 또는 `굴착` 단어만으로 확정하지 않는다.
4. Evidence substring 검증은 의미적 사실 검증 전체를 대체하지 않는다.
5. 실제 LLM을 포함한 전체 브라우저 E2E는 API 1회 제한 때문에 수행하지 않았다.
