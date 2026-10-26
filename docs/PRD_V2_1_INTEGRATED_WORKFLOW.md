# PRD v2.1 통합 흐름

기준: Sprint 21, 2026-10-25, 기존 25개 API 보존.

## 호출 순서

1. `POST /api/notices/extract` 또는 `/extract-file`로 문서를 추출한다.
2. 추출 응답의 `notice`, `mode`, `is_actual_ai`, `field_evidence`를 `POST /api/prd/planning/from-notice`에 전달한다.
3. 프론트엔드는 `missing_fields`와 `confirmation_required_fields`를 사용자에게 확인받는다. 초안은 공식 신고 사실이 아니며 null을 임의 보완하지 않는다.
4. 확인 완료 값으로 `PRDNoticePlanningInput`과 task별 장비·대수·선후행·복구 매핑을 만든다.
5. 단일 일정 점검에는 기존 `POST /api/prd/schedules/validate`, 추천 흐름에는 `POST /api/prd/recommendations/constraint-filtered`를 호출한다.
6. 통합 API의 `recommendable=true`인 후보만 추천 UI에 표시한다. `recommendation_status=none_feasible`이면 추천 없음과 위반 코드를 표시한다.

## 추출 필드 연결

| 신고서 추출 | PRD 초안 | 처리 |
|---|---|---|
| `name`, `location`, `construction_period`, `original_work_window` | 동명 계획 필드 | 존재한 값만 복사 |
| task `equipment_id`, `name`, `duration_minutes`, `permitted_time_windows` | 장비 ID·종류·필요시간·허용시간 | 존재한 값만 복사 |
| task `predecessors` | `predecessors` | 그대로 복사 |
| `constraints.road_excavation`, `.same_day` | 굴착·당일복구 | 명시적 boolean일 때만 복사 |
| 규격, 최대 대수, 점용시간, 고정시각 | nullable 초안/결측 목록 | 자동 생성하지 않음 |
| `field_evidence`, `source_provenance` | 원문 근거·필드 provenance | 그대로 유지 |

Mock/LLM 추출값은 모두 확인 전 초안이다. 특히 LLM 생성값을 공식 문서 사실로 승격하지 않는다.

## 제약-추천 결합 범위

기존 optimizer는 07:00 원 일정에서 0~120분을 15분 간격으로 이동한 9개 후보를 생성한다. 순차 공정 총 540분과 기존 07:00~18:00 창에서는 이 offset 범위가 가능한 시작시각 전부다. 통합 서비스는 후보마다 실제 입력된 전체 작업창, 장비창/필요시간/대수/동시대수, 도로점용, 고정 작업, 선후행, 당일 복구, 완료일을 재검증한다.

PRD 통과 후보만 대상으로 기존 목적축의 Pareto를 다시 계산한다. 이는 `constraint_filtered_candidate_set_not_global_optimum`이며 범용 제약 최적화나 전역 최적해가 아니다. 공정 순서 변경, 병렬화, 기간 분할, 15분 미만 시작시각은 탐색하지 않는다. 입력하지 않은 제한을 생성하거나 제약을 완화하지 않는다.

## 좌표와 음향 상태

`JUSO_COORD_API_KEY` 승인 전에는 공식 공사 geometry, 공식 주거 외벽 수음점, 현장 음향 예측을 만들지 않는다. 실제 현장 정확도는 `not_evaluable`이며 S-DoT 날짜별 값도 물리 합성에 넣지 않는다.

## S7·S8 후속 설계

S7 안내문은 승인 전 초안/수정/검토 상태, 승인 주체, 공개 가능 여부, 사용 일정 버전, 공식 행정 안내와 실험 결과 구분이 필요하다. S8 공개 조회는 승인 자료만 제공하고 내부 점수·개인정보를 제외하며 위치 정밀도, 변경·철회 정책이 필요하다. 승인 주체·공개 범위·정밀도·철회 SLA는 기획 결정 전까지 구현하거나 활성화하지 않는다.
