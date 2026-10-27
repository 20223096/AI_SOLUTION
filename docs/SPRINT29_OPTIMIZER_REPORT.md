# Sprint 29 개선 추천 엔진 보고서

기준 커밋: `3d6fbb9`

구현일: 2026-10-27

엔진 버전: `cp_sat_v2`

## 구현 결과

기존 `offset_v1`은 API 기본값과 회귀 baseline으로 그대로 보존했다. S4 프론트엔드는 새 선택 필드 `recommendation_engine=cp_sat_v2`를 명시적으로 전송한다. 이전 클라이언트가 필드를 보내지 않으면 기존 0~120분/15분 offset 9개 결과가 유지된다.

새 엔진은 `backend/app/services/advanced_optimizer.py:optimize_advanced`에서 OR-Tools CP-SAT을 실제 호출한다. 작업별 시작시각을 서로 독립된 정수변수로 만들고 15분 grid에서 feasible schedule을 열거한 뒤, 기존 `schedule_metrics`로 음향·Impact를 평가한다. CP-SAT 내부에서 비선형 음향식을 근사하지 않는다.

## 제약 모델

| 요구 제약 | 구현 | 근거/한계 |
|---|---|---|
| 신고 공사기간 | 분석일이 확인 기간 안인지 선검사 | 기간 밖이면 해 없음 |
| 전체 작업 허용시간 | 각 작업 start domain에 적용 | 사용자 확인값이며 법령 자동조회 아님 |
| 장비 08~17시 등 | `equipment_constraints.permitted_time_windows` 적용 | 구청 답변 기반 가정/사용자 확인 입력으로만 취급 |
| 도로점용 허가시간 | `road_excavation=true`일 때 start/end domain과 교집합 | 공식 허가 API 연동 아님 |
| 작업 선후관계 | `start(successor) >= end(predecessor)` | 구현 완료 |
| 당일 복구 | 복구 필수인데 task ID가 없으면 infeasible; 당일 window 내 종료 | 복구 작업 duration이 없으면 임의 생성하지 않음 |
| 필수 작업시간 | scenario task duration과 equipment required usage 일치 확인 | 작업시간과 장비시간을 별도 입력으로 검사 |
| 공유 자원 | 동일 `required_resources`에 CP-SAT `NoOverlap` | 구현 완료 |
| 고정 작업 | fixed start/end를 start domain에 적용 | 구현 완료 |
| 행사·수거·주변 공사 | feasible schedule을 삭제하지 않고 별도 중첩 목적축으로 평가 | 현재 9/11 이벤트 시간/dB는 assumed; 공공 일정은 검증된 음향값이 없어 미사용 |

15분 grid에 맞지 않는 작업시간은 자동 반올림하지 않고 현재 v2에서 infeasible 사유로 반환한다.

## 다목적 및 Pareto

탐색한 각 feasible schedule에 다음 네 축을 적용한다.

1. `incremental_impact_cost`
2. 작업별 시작 변경량 합
3. `max_continuous_high_noise_minutes`
4. `existing_noise_overlap_receptor_minutes`

`non_dominated_multi`가 네 축 모두 작거나 같고 하나 이상 작은 후보가 있는지를 검사한다. API에는 frontier만 반환하지만 `explored_candidate_count`로 실제 평가한 해 수를 함께 제공한다.

- 9/11: 495 feasible schedules, 35 Pareto schedules
- 10/7: 495 feasible schedules, 18 Pareto schedules
- `search_complete=true`는 설정한 2,000해 한도 안에서 CP-SAT feasible set 열거가 끝났다는 뜻이다.
- `global_optimality_guaranteed=false`다. 15분 grid, 현재 task/duration/입력 범위 밖의 전역 최적성을 주장하지 않는다.
- 후보가 정확히 하나면 그 하나만 반환하고, infeasible이면 가상 후보 없이 빈 목록과 사유를 반환한다.

## API 하위 호환성

`POST /api/prd/recommendations/constraint-filtered`에 다음 필드를 추가했다.

- request: `recommendation_engine: offset_v1 | cp_sat_v2`, 기본 `offset_v1`
- response: `solver`, `explored_candidate_count`, `pareto_candidate_count`, `pareto_axes`, `search_complete`, `global_optimality_guaranteed`
- `candidate_generation_mode`에 `ortools_cp_sat_task_start_enumeration` 추가

기존 response 필드는 삭제하거나 의미를 변경하지 않았다. OpenAPI, 공용 TypeScript 선언, 프론트 사본, 계약 예제를 함께 재생성했다. API 수는 33개로 유지된다.

## 기존 계산 보호

- `acoustics.py:sound_power_to_pressure`의 구면확산식과 약 -10.99 dB 상수를 변경하지 않았다.
- `energy_sum`, Impact 식, background profile, 데이터 fixture를 변경하지 않았다.
- 기존 offset 엔진의 9/11 결과 7.36, 10/7 결과 13.72→13.20, 1,620 receptor-minutes가 유지된다.
- 새 10/7 엔진의 13.12는 작업별 유휴시간 배치를 추가 탐색해서 얻은 별도 버전 결과이며 기존 13.20을 덮어쓰지 않는다.

## 실제 데이터와 가정

| 구분 | 사용 상태 |
|---|---|
| 도로교통소음 | 2025-01~2026-06 과거 시간대별 대표 LEQ를 background로 사용 |
| S-DoT | 실제 관측 자료이나 지표·교정·공간 호환성 미확인으로 합성 제외 |
| 공식 장비 자료 | 모델/분포 참조값 사용; 실제 현장 장비 확인값 아님 |
| 학교·병원 거리 | 공식 대표점 간 수평거리; 공사 선형/외벽 전달경로 아님 |
| 공공 공사·행사 | 날짜 문맥만; 검증된 일일 시간+dB가 없어 음향 계산 미사용 |
| 9/11 주변 공사 | 07:00~09:00, 82 dB assumed overlay |
| 수거 | 공식 처리행 0; 기존 시연값은 assumed |
| fallback | scenario 기본 55 dB는 `assumed_demo` 선택 시에만 사용; Sprint 29 실험은 road traffic profile을 명시 |

## 구현하지 않은 기능

- 공정의 다일 분할, 연속시간이 아닌 가변 duration, 15분 미만 grid
- 검증된 행사/수거 시간의 hard exclusion
- 자연어 제약 추출, 주민 신고 피드백
- 실제 공사 선형·외벽 수음점 기반 전파경로
- 동시 고소음의 독립 wall-clock metric. 현재 제공되는 값은 receptor-minutes이므로 시간으로 오인하지 않는다.
- 통계적 불확실성 또는 피해 감소 검증

## 테스트

- CP-SAT task-level 탐색 및 실제 Pareto 재계산
- 정확히 한 해인 작업창
- 해 없음
- existing-event on/off
- API default offset 호환 및 명시적 CP-SAT 선택
- 전체 backend 274 passed(기존 269 + 신규 5)
- frontend 14 passed(기존 13 + 신규 1)
- production build 성공
- Chromium S1~S8 실제 HTTP E2E 1 passed

브라우저 E2E에서는 JUSO 주소/좌표, 제약 검증, CP-SAT 추천, 비교, 비공개 초안, snapshot 확정, 주민 공개, 새로고침 후 서버 publication, 모바일 overflow와 console error를 검증했다.
