# 쉿간표 20차 PRD v2.1 API 연결 및 시연 검증 보고서

검증일: 2026-10-24. 기존 21개 API의 path, 요청 및 응답은 유지했다. 이번 문서는 차기 프론트엔드 계약서 발행 전 검토본이며 `FRONTEND_API_CONTRACT_v2_1.md`를 대체하지 않는다.

## 1. 신규 공개 API

| Method | Path | 기능 | 성공 모델 |
|---|---|---|---|
| GET | `/api/prd/demo/2026-09-11` | 공식 설계, 시연 계획, 주변 공사·행사·수거 가정, 9/11·10/7 S-DoT 품질 조회 | `DemoFixtureResponse` |
| POST | `/api/prd/schedules/validate` | 명시된 공사·장비·점용·고정작업·선후행·복구 조건의 가능 여부 | `PRDScheduleValidationResponse` |
| GET | `/api/prd/recommendation-diagnostics` | 9/11 또는 10/7의 모든 offset 후보, 목적값, 중첩, Pareto 지배 사유 | `RecommendationDiagnosticsResponse` |
| POST | `/api/prd/sensitivity/experiment` | 두 날짜와 ×1.1/1.3/1.5 최댓값 민감도 정책 비교 | `PRDSensitivityExperimentResponse` |

모든 모델은 OpenAPI에 명시되어 있고 nullable 값은 JSON `null`로 반환한다. 인증은 기존과 같이 없으며 기존 CORS origin에서 GET/POST preflight가 통과한다.

## 2. 신고·제약 검증 계약

요청은 공사명, 위치, 공사기간, 공사 허용창, 장비 종류·규격·선택 모델명·최대 대수·필요시간·장비 허용창, 도로굴착과 점용 허가창, 고정 작업, 선후행, 당일 복구, 완료일, 원문 근거와 provenance를 받는다. 각 배정시각에는 timezone offset이 필수다.

검증 실패는 계산 오류가 아니라 정상적인 업무 결과이므로 HTTP 200과 `feasible=false`로 반환한다. `violations[].code`에는 `outside_total_work_window`, `outside_equipment_time_window`, `equipment_count_missing`, `equipment_daily_count_exceeded`, `equipment_concurrent_count_exceeded`, `equipment_required_usage_mismatch`, `outside_road_occupancy_permit`, `fixed_task_*`, `predecessor_violation`, `same_day_restoration_*`, `project_completion_date_exceeded`, `outside_construction_period` 등이 들어간다. JSON 형식·타임존·필드 자체가 잘못되면 HTTP 422다. 입력하지 않은 07~18시 또는 08~17시 규칙은 만들지 않는다.

## 3. 9/11과 10/7 데이터 역할

- 공식 설계 `R26BK01661205`: 수량과 기간 산정자료는 공식 문서지만 날짜별 공정, 일일 작업창, 실제 장비 운전 및 음향은 null이며 음향 예측은 `deferred`다.
- 9/11 시연 계획: `final-demo-congestion`, 07~18시 작업창과 07~09시 82 `Lp_dBA` 주변 공사 오버레이는 시연 가정이다.
- 주변 공사 두 건: 공식 사업기간만 확인되며 일일 운전시간과 `noise_db`는 null이다.
- 신촌글로벌대학문화축제: 9/11 공식 표기 17:30~20:00, 음향값 null이다.
- 폐기물 수거: 09:00~09:30, 75 dB는 실측이나 공식값이 아닌 가정이다.
- S-DoT: 각 날짜 72행이다. 두 센서는 각각 24 valid, V02Q1940585는 24 held/null이다. 지표 정의가 부족해 모델 합성에는 사용하지 않는다.
- 10/7 비교 계산은 9/11 전용 혼잡 가정을 반복하지 않으며 `official_reference_equipment`를 사용한다. 배경은 날짜별 S-DoT가 아니라 기존 역사적 대표 도로소음 프로파일이므로 날짜 간 실측 효과 비교로 표현하면 안 된다.

## 4. 실제 추천 진단

### 2026-09-11

`offset-0`만 Pareto이자 추천이다. 이동할수록 기존 가정 이벤트와의 중첩은 360 → 0 receptor-minutes로 감소하지만 선택 목적 `incremental_impact_cost`는 7.36 → 13.20으로 증가하고 작업별 시작 이동 합은 0 → 480분으로 증가한다. 높은 기존 가정소음과 Impact 절단/반올림 때문에 중첩 시 신규 공사의 계산상 증분 점수가 작아지는 마스킹 현상이다. 따라서 `offset-0`이 두 목적축에서 모든 이동안을 지배하며, 원 일정보다 좋은 추천안은 없다. 이를 좋게 보이기 위한 패널티는 추가하지 않았다.

### 2026-10-07

9/11 오버레이를 제외하면 9개 후보가 모두 Pareto다. `offset-0`은 변경량 최소안, `offset-120`은 주민 목적값 최소안이다. 후자는 `incremental_impact_cost`를 13.72에서 13.20으로 0.52 낮추지만 프로젝트 시작·종료를 120분 옮기고 네 작업의 시작 이동 합은 480분이다. 민감 수음점 노출은 양쪽 모두 1,620 receptor-minutes여서 노출시간 자체의 개선은 아니다. 이는 일정 변경과 계산 점수 사이의 trade-off다.

## 5. 민감도 실험

정책명은 `PRD v2.1 maximum-overlap sensitivity experiment`, 버전은 `prd_max_v2_1_experimental`, 중복 규칙은 `maximum_single_multiplier`다. 기존 M0/M1 기본 `legacy_v1`은 바뀌지 않는다.

| 날짜 | 배수 | 추천 | 순위 변경 | 추천안 민감 노출 | 가중 노출 | 일정 변경 |
|---|---:|---|---|---:|---:|---:|
| 9/11 | 1.1 | offset-0 | 없음 | 1,620 | 1,782 | 0분 |
| 9/11 | 1.3 | offset-0 | 없음 | 1,620 | 2,106 | 0분 |
| 9/11 | 1.5 | offset-0 | 없음 | 1,620 | 2,430 | 0분 |
| 10/7 | 1.1/1.3/1.5 | offset-0, offset-120 | 없음 | 첫 추천 기준 1,620 | 1,782/2,106/2,430 | 첫 추천 0분 |

두 날짜 모두 제약 탈락 후보는 0개다. API는 빈 `infeasible_candidate_ids`를 반환하며 후보를 꾸며내지 않는다. 모든 후보의 독립 목적값, 지배 관계, 중첩량과 전체 `ScheduleMetrics`는 `candidate_diagnostics`에 포함된다.

## 6. 프론트엔드 구현 가능 범위

즉시 구현 가능: 공식/가정 구분이 있는 9/11 데이터 패널, 센서 품질/결측 화면, 구조화 신고 제약 검증과 불가능 사유, 9/11·10/7 후보 비교, Pareto 제외 사유, 민감도 배수 비교.

아직 불가: 신고서 영구 저장·승인 수명주기, 실제 9/11 공사 운전 및 음향 재현, 주민 안내문 생성·승인, 주민 공개 조회, 자연어 조건 승인 적용, 법적 적합/위반 판정.

## 7. 검증 산출물

- OpenAPI: `docs/openapi.json` — 25 operation
- TypeScript: `frontend-contract/types/api.d.ts` — `openapi-typescript@7.10.1`
- 실제 HTTP 성공 예시: `frontend-contract/examples/01-*`~`25-*`
- 신규 오류 예시: `frontend-contract/examples/error-422-prd-date.json`
- 자동화 테스트: `backend/tests/test_prd_api.py`
