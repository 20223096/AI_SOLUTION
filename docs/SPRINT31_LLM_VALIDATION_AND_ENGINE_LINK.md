# Sprint 31 LLM 추출 검증 및 계산 엔진 연결

검증일: 2026-10-27  
기준: Sprint 30 `f4f6e398bdd34a2e597583a4bcb61f4531a4ecc8`

## 결론

실제 OpenAI API는 호출하지 않았다. Sprint 30의 실제 응답 형태를 반영한 오프라인 fixture로 Structured Outputs 요청, 원문 근거, 서버 provenance, 장비 표준화, S2 확인 폼, S3 일정 검증 및 S4 CP-SAT 입력 연결을 검증했다.

`gpt-4.1-mini`가 지원하는 Chat Completions Structured Outputs를 적용했다. LLM은 자유형 도메인 객체를 직접 작성하지 않고 제한된 `LLMNoticeFacts`만 반환한다. 서버가 원문 검증과 명시적 규칙을 적용해 기존 `ConstructionNotice`로 변환하므로 기존 API와 계산 모델은 하위 호환을 유지한다.

## Structured Outputs

- endpoint: `POST /v1/chat/completions`
- response format: `json_schema`
- schema name: `construction_notice_facts`
- `strict: true`
- schema source: Pydantic `LLMNoticeFacts.model_json_schema()`
- provider: 기존 `openai_compatible` 유지
- 실제 외부 호출: 0회
- 실패 처리: 분류된 오류를 반환하며 mock으로 대체하지 않음

기존 `ConstructionNotice.constraints`는 자유형 dictionary여서 strict schema에 직접 사용하지 않는다. LLM 전용 모델은 모든 키가 명시되고 `extra=forbid`이며, LLM이 provenance를 반환할 필드 자체가 없다.

## 원문 근거와 출처 검증

각 주요 필드에는 `extracted_value`, `evidence`, `evidence_exists`, `needs_review`, `issues`를 기록한다. evidence는 원문 안의 연속 부분 문자열인지 서버가 검사한다. 이름·위치·기간은 추출값이 evidence 안에도 포함되는지 추가 검사한다.

근거가 없거나 일치하지 않으면 `needs_review=true`이며 S1에 검토 필요가 표시된다. 장비 모델·수량·사용 시작/종료 시각과 조정 불가 조건은 원문에 없는 값이면 계산용 notice에서 제거하거나 검토 issue로 남긴다.

LLM 출력 스키마에는 provenance가 없다. `verified_public`을 추가한 fixture는 `extra=forbid` 검증에서 실패한다. 서버는 신고서 원문을 `user_provided`, LLM 변환물을 `derived`로만 부여한다. 공식 API 조회 없이 `verified_public`은 부여하지 않는다.

## 장비 표준화

| 표준 ID | 대표명 | 명시적 동의어 |
|---|---|---|
| `breaker` | 브레이커 | 브레이커, 착암기, 해머 |
| `cutter` | 콘크리트 절단기 | 콘크리트 절단기, 콘크리트절단기, 절단기, 커터, 컷터 |
| `excavator` | 굴착기 | 굴착기, 굴삭기, 포클레인, 백호 |
| `roller` | 롤러 | 롤러, 다짐기, 다짐기계 |

알 수 없는 장비는 자동으로 기존 카탈로그에 끼워 맞추지 않고 `unmatched_equipment`와 `task_equipment_unmatched`로 표시한다. 모델명이 원문에 없으면 제거한다. 대표 장비 모델이나 대표 소음값은 LLM 단계에서 자동 선택하지 않는다.

표준 장비는 기존 계산 task ID(`cut`, `break`, `excavate`, `compact`)에 연결된다. 명시된 장비별 사용시간은 task duration과 허용시간으로 전달되고, 수량은 S2 폼의 투입 대수로 전달된다. 원문에 장비만 있고 작업명이 없으면 확인이 필요한 장비 작업을 만들며 사용자에게 수정을 요구한다.

## S1~S4 전달과 차단

1. S1이 strict fixture를 파싱하고 근거 및 review 상태를 표시한다.
2. 서버가 장비명, 수량, 시간, 작업 순서를 정규화해 S2 planning draft를 생성한다.
3. S2에서 사용자가 주소·좌표, 작업별 장비, 수량, 작업시간, 복구 작업을 확인·수정한다.
4. 필수 장비 없음, 일반 작업의 장비 연결 없음, 작업시간 없음, 수량 초과, 장비 시간이 전체 작업시간 밖이면 확정을 막는다.
5. 사용자 확정 후 `task_duration_by_task`, `equipment_by_task`, `equipment_count_by_task`, predecessors가 S3와 S4에 동일하게 전달된다.
6. S3는 사용자가 확인한 task duration과 실제 assignment duration이 다르면 위반을 반환한다.
7. S4 CP-SAT은 `task_duration_by_task`가 있을 때 기존 시나리오 고정 duration 대신 확인된 duration으로 탐색한다. 기존 요청에 이 필드가 없으면 Sprint 29 baseline 방식으로 동작한다.

오프라인 통합 fixture에서 굴착기 120분, 브레이커 60분, 복구 60분을 확인값으로 전달했으며 CP-SAT은 해당 세 작업만 포함한 feasible 후보 집합을 생성했다. 지원 계산 task ID로 표준화할 수 없는 작업은 계산하지 않고 정확한 `unsupported calculation task ids` 사유로 실패한다.

## 데이터 경계

- Mock: 기존 결정적 시연 규칙이며 화면에 AI 아님으로 표시
- LLM: 원문에서 추출한 미확정 draft, 서버 검증 후에도 사용자 확인 필요
- 사용자 확인: S2 확정 폼에서 `user_provided / confirmed form`으로 승격
- 시나리오: 기존 소음·배경·수음점 계산 fixture; LLM 원문 사실로 가장하지 않음
- 공식 데이터: 실제 공식 조회 또는 기존 검증 데이터에만 `verified_public` 사용

## 회귀 결과

- 백엔드: 295 passed (최종 실행 기준)
- 프론트엔드: 17 passed
- TypeScript/Vite production build: 성공
- lint: 성공
- Chromium S1~S8 E2E: 1 passed, mock 추출 모드
- Sprint 29 비교실험: 재현 성공
- 2026-09-11: 기존 7.36, 495 후보, Pareto 35 유지
- 2026-10-07: 기존 offset 13.72 → 13.20, CP-SAT 13.72 → 13.12, 495 후보, Pareto 18 유지
- 실제 OpenAI 추가 호출: 없음

## 남은 문제

1. strict schema의 실제 provider 수용 여부는 사용자 승인 후 1회 실제 호출로 최종 확인해야 한다.
2. 원문 substring 검증은 의미적 진실성 검증이 아니라 최소 근거 검증이다.
3. 기타 장비는 카탈로그 선택 UI에서 사용자가 표준 ID와 음향 자료를 연결해야 한다.
4. 계산 엔진은 기존 시나리오가 아는 표준 task ID만 음향 계산할 수 있다. 새로운 작업·장비의 음향 모델 연결은 별도 개발이 필요하다.
5. 브라우저 E2E는 mock 기반 회귀이며 실제 LLM 호출을 포함하지 않는다.
