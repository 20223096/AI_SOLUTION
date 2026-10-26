# PRD v2.1 S1~S4 프론트엔드 연동 가이드

기준 커밋은 Sprint 21 `41097b4`, API는 27개다. 이 문서는 실제 Pydantic 모델, OpenAPI 3.1과 로컬 HTTP 재생 결과만 설명한다.

## 1. 화면별 호출 순서

| 화면 | 사용자 흐름 | API | 다음 단계로 전달할 값 |
|---|---|---|---|
| S1 신고서 입력 | 텍스트 입력 | `POST /api/notices/extract` | 응답의 `notice`, `mode`, `is_actual_ai`, `field_evidence` |
| S1 신고서 입력 | txt/PDF 업로드 | `POST /api/notices/extract-file` multipart `file` | 위와 동일 |
| S2 추출 확인 | PRD 초안 변환 | `POST /api/prd/planning/from-notice` | `planning_draft`, `missing_fields`, `confirmation_required_fields`, provenance |
| S2 추출 확인 | 사용자 수정·확정 | 클라이언트 폼 상태 | 완전한 `PRDNoticePlanningInput`, task 매핑 |
| S3 제약 확인 | 현재/선택 일정 검증 | `POST /api/prd/schedules/validate` | `feasible`, `violations`, `policy_version` |
| S4 후보 추천 | 후보 생성+제약 필터 | `POST /api/prd/recommendations/constraint-filtered` | `candidates`, `recommendable_candidate_ids`, `recommendation_status` |
| S4 비교 | 추천 후보 선택 | `POST /api/schedules/compare` | `before`, `after`, `delta`, 비교 근거 |

S2 초안과 확정 planning은 구조가 다르다. `planning_draft`의 nullable 값을 그대로 통합 API에 보낼 수 없다. 사용자가 결측값을 확인한 뒤 아래 변환을 명시적으로 수행해야 한다.

```text
planning_draft.project_name?          -> planning.project_name (required)
planning_draft.location?              -> planning.location (required)
planning_draft.construction_period    -> planning.construction_period (start/end 확인)
planning_draft.total_work_window?     -> planning.total_work_window (required)
planning_draft.road_excavation?       -> planning.road_excavation (required boolean)
draft equipment required_usage?       -> equipment_constraints[].required_usage_minutes (required)
draft equipment max_daily_count?      -> 확인 후 nullable 유지 가능
planning_draft.predecessors           -> request.predecessors
사용자 확인 task 매핑                -> equipment_by_task / equipment_count_by_task
사용자 확인 복구 task                 -> restoration_task_ids
```

규격, 점용시간, 고정작업, 당일복구 여부는 추출되지 않았으면 생성하지 않는다. 해당 제약이 실제로 존재할 때만 사용자 확인값과 provenance를 함께 넣는다.

## 2. TypeScript 타입

```ts
import type { components, paths } from "./types/api";

type ExtractRequest = components["schemas"]["ExtractRequest"];
type ExtractResponse =
  | components["schemas"]["MockNoticeExtractResponse"]
  | components["schemas"]["LLMNoticeExtractResponse"];
type DraftRequest = components["schemas"]["PRDPlanningDraftRequest"];
type DraftResponse = components["schemas"]["PRDPlanningDraftResponse"];
type ValidationRequest = components["schemas"]["PRDScheduleValidationRequest"];
type ValidationResponse = components["schemas"]["PRDScheduleValidationResponse"];
type RecommendationRequest = components["schemas"]["PRDConstraintRecommendationRequest"];
type RecommendationResponse = components["schemas"]["PRDConstraintRecommendationResponse"];
type CompareRequest = components["schemas"]["CompareRequest"];
type CompareResponse = components["schemas"]["CompareResponse"];

type RecommendationOperation = paths["/api/prd/recommendations/constraint-filtered"]["post"];
```

완전한 required/optional/nullable 정의는 패키지의 `openapi.json`과 `types/api.d.ts`가 규범이다. Python의 default가 있는 필드는 요청에서 optional일 수 있지만 응답 모델의 required 여부와 혼동하지 않는다.

## 3. 필수·선택·nullable 입력

- 확정 planning 필수: `notice_id`, `project_name`, `location`, `construction_period`, `total_work_window`, `road_excavation`, `provenance`.
- 목록 필수이나 빈 배열 허용: `equipment_constraints`, `fixed_tasks`, `non_adjustable_conditions`.
- nullable: `road_occupancy_permit_window`, `project_completion_date`, 장비 `specification`, `model_name`, `max_daily_count`.
- 장비 제약이 있으면 필수: `equipment_id`, `category`, `required_usage_minutes`, `source_metadata`.
- 통합 요청의 매핑은 기본 빈 객체/집합이지만, 실제 장비 제약 검증에는 `equipment_by_task`와 필요 시 `equipment_count_by_task`가 필요하다.
- assignment datetime은 timezone offset이 필수이며 시작일은 `analysis_date`와 같아야 한다.

## 4. UI 상태

| UI 상태 | 판정 | 화면 처리 |
|---|---|---|
| 초기 입력 전 | 요청 없음 | 입력/파일 선택 활성화 |
| 추출 중 | extract 요청 pending | 중복 제출 방지, 취소 가능 로딩 |
| 추출 성공 | HTTP 200 | 원문 근거, `mode`, `is_actual_ai`, 경고 표시 |
| 누락 필드 존재 | `missing_fields.length > 0` | 필드별 확인 입력. 추천 호출 금지 |
| 사용자 입력 수정 | 로컬 값이 마지막 검증값과 다름 | 기존 검증·추천·비교 결과 stale 처리 |
| 제약 검증 통과 | validate 200 + `feasible=true` | 원 일정 적합 표시 후 추천 호출 |
| 제약 검증 실패 | validate 200 + `feasible=false` | `violations` 표시 후 대안 탐색을 위해 추천 호출 가능. 서버 오류로 처리하지 않음 |
| 추천 후보 존재 | `recommendation_status=available` | `recommendable=true`만 선택 가능 |
| 일부 후보만 가능 | feasible/infeasible 후보가 모두 존재 | 불가능 후보 비활성화, 위반 사유 표시 |
| 단일 추천 후보 | `recommendable_candidate_ids.length===1` | 자동 강조 가능하나 사용자가 확인 후 선택 |
| 추천 후보 없음 | `recommendation_status=none_feasible` | 정상 업무 결과. 재입력 안내와 모든 위반 표시 |
| 서버·네트워크 오류 | fetch 실패 또는 non-2xx | 재시도 UI. 직전 성공 결과와 구분 |
| 실측값 미확보 | `validation_status=not_evaluable` 또는 caveat | 정확도 수치 표시 금지 |
| 현장 예측 보류 | `calculation_status/evaluation_status/official_prediction_status=deferred` | 예측값 대신 결측 입력 표시 |

`none_feasible`, `feasible=false`, `not_evaluable`, `deferred`는 HTTP 장애가 아니다.

## 5. 위반 코드 안내 문구

| 코드 | 권장 안내 |
|---|---|
| `construction_period_missing` | 공사 시작일과 종료일을 확인해 주세요. |
| `outside_construction_period` | 선택 날짜가 공사기간 밖입니다. |
| `outside_total_work_window` | 작업이 전체 공사 허용시간을 벗어납니다. |
| `outside_equipment_time_window` | 장비 작업이 장비별 허용시간을 벗어납니다. |
| `equipment_count_missing` | 작업별 투입 장비 대수를 입력해 주세요. |
| `equipment_daily_count_exceeded` | 입력한 장비 대수가 일 최대 대수를 초과합니다. |
| `equipment_concurrent_count_exceeded` | 동시에 사용하는 장비 대수가 한도를 초과합니다. |
| `equipment_required_usage_mismatch` | 배정된 장비 사용시간이 필요한 사용시간과 다릅니다. |
| `outside_road_occupancy_permit` | 작업이 도로점용 허가시간을 벗어납니다. |
| `fixed_task_missing` | 필수 고정 작업이 일정에 없습니다. |
| `fixed_task_start_changed` | 고정 작업 시작시각을 변경할 수 없습니다. |
| `fixed_task_end_changed` | 고정 작업 종료시각을 변경할 수 없습니다. |
| `predecessor_violation` | 선행 작업 완료 전에 후속 작업이 시작됩니다. |
| `same_day_restoration_missing` | 당일 복구 작업이 일정에 없습니다. |
| `same_day_restoration_violation` | 복구 작업이 당일 완료되지 않습니다. |
| `project_completion_date_exceeded` | 계획 완료일을 초과합니다. |

문구는 행정·법적 판정이 아니라 입력 계획과 명시 제약의 불일치 안내다.

## 6. 추천 선택과 재검증

1. `recommendable_candidate_ids`에 있고 해당 후보의 `recommendable=true`, `prd_feasible=true`인 것만 선택한다.
2. `pareto_after_constraint_filter=true`는 0~120분, 15분 offset 후보 안의 조건부 Pareto일 뿐 전역 최적해가 아니다.
3. 후보가 하나면 해당 후보를 강조하되 자동 확정하거나 자동 공개하지 않는다.
4. 후보가 없으면 `no_recommendation_reasons`와 후보별 `violations`를 보여주고 조건 수정을 유도한다.
5. 사용자가 planning, task 매핑, 날짜, 배정 중 하나라도 바꾸면 validate/recommend/compare 결과를 폐기하고 S3부터 다시 호출한다.
6. 비교 요청의 `before`는 `original_schedule.assignments`, `after`는 선택 후보 `assignments`를 사용한다.

## 7. 출처·시뮬레이션 배지

- `verified_public`: 검증된 공개 원천. 실제 현장 투입·운전을 의미하지는 않는다.
- `user_provided`: 사용자 입력/확인값.
- `assumed`: 가정값. 공식값과 색상·라벨을 분리한다.
- `derived`: 입력에서 계산된 값.
- `missing`: 미확인. 값처럼 표시하지 않는다.
- `simulation_status=simulated`: 시뮬레이션 결과.
- `not_evaluable`: 현장 관측과 짝지을 수 없어 정확도 평가 불가.
- `deferred`: 필수 좌표·geometry·수음점·현장 입력 미확보로 계산 보류.

S-DoT 관측은 맥락 정보이며 현장 LAeq나 물리 합성 입력으로 표시하지 않는다.

## 8. 실제 HTTP 검증 자료

전체 순차 실행 결과는 `frontend-contract/examples/prd-s1-s4-workflow.json`이다. 08:00~18:00 확인 계획에서 원 일정은 실패하고 `offset-0`~`offset-45`는 불가능, `offset-60`~`offset-120`은 PRD feasible, 조건부 추천은 `offset-60` 하나로 검증된다. API별 독립 예시는 `01`~`27` JSON에 있다.
