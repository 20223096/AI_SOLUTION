# 프론트엔드 인계

기본 URL은 `http://127.0.0.1:8000`, Swagger는 `/docs`입니다. 기존 필드는 삭제하거나 의미를 변경하지 않았습니다.

## 최종 호출 순서와 시나리오 선택

1. `GET /api/health`
2. `GET /api/noise/background-profiles`
3. `GET /api/poc/scenarios`
4. `GET /api/poc/scenarios/{scenario_id}`로 좌표·장비·출처 확인
5. `GET /api/public-data/catalog`로 실제 공사·행사 일정과 공식 장비 카탈로그 확인
6. 필요하면 `POST /api/notices/extract`
7. `POST /api/noise/predict`
8. `POST /api/schedules/optimize`
9. 선택 후보로 `POST /api/schedules/compare`
10. 개발 비교 화면은 `POST /api/experiments/run`

최종 시연 A는 `official_reference_equipment`와 `road_traffic_observed_profile`, 시연 B는 `final-demo-congestion`과 같은 프로파일을 사용합니다. A의 장비 모델도 실제 현장 확인값이 아니라 공식 분포 참고행입니다. B의 기존 이벤트 시간·Lp는 `assumed`입니다.

```json
GET /api/poc/scenarios/official_reference_equipment
{
  "id":"official_reference_equipment",
  "settings":{"recommended_background_profile":"road_traffic_observed_profile","demo_classification":"official_reference"},
  "receptors":[{"name":"창천중학교","distance_to_source_m":235.3,"latitude":37.55498958,"longitude":126.9392951,"coordinate_crs":"EPSG:4326","spatial_status":"verified_public"}],
  "equipment":[{"category":"브레이커","model_name":"GB525E(저소음)","sound_power_level_db":122.0,"acoustic_unit_type":"Lw_dBA","source_metadata":{"status":"verified_public","note":"Observed record nearest to category median; reference scenario, not confirmed site equipment"}}]
}
```

## 신고자료 구조화

```http
POST /api/notices/extract
Content-Type: application/json

{"text":"신촌 연세로 공사, 작업시간 07:00~18:00, 브레이커 2시간"}
```

```json
{"mode":"mock","is_actual_ai":false,"notice":{"id":"extracted-mock","location":"서울 서대문구 신촌역~현대백화점 인근 연세로 일대","original_work_window":{"start":"07:00:00","end":"18:00:00"},"tasks":[{"id":"break","equipment_id":"breaker","duration_minutes":120}]},"field_evidence":{"name":"연세로"},"warnings":["MockExtractor의 결정적 규칙 결과이며 실제 AI 추출이 아닙니다."]}
```

`mode`, `is_actual_ai`, null 필드와 warnings를 그대로 표시합니다. 파일은 multipart `POST /api/notices/extract-file`의 `file` 필드로 보냅니다.

## 수음점별 소음

```json
POST /api/noise/predict
{"scenario_id":"official_reference_equipment","analysis_date":"2026-10-26","sensitivity_enabled":true,"background_profile":"road_traffic_observed_profile"}
```

한 슬롯의 응답 형태:

```json
{"receptor_id":"school-changcheon","slot_start":"2026-10-26T08:00:00+09:00","slot_end":"2026-10-26T08:15:00+09:00","active_task_ids":["break"],"background_only_db":71.5,"existing_environment_db":71.5,"new_project_contribution_db":63.58,"with_new_project_db":72.15,"delta_total_db":0.65,"total_impact":30.46,"baseline_impact":29.38,"incremental_impact":1.08,"impact_saturation":{"score_at_ceiling":false,"level_component_at_ceiling":false,"incremental_zero_despite_physical_increase":false},"source_metadata":{"equipment":[{"source":{"status":"verified_public"}}]}}
```

그래프는 `total_estimated_db`, 구성요소는 별도 범례로 표현합니다. null은 0이 아니라 누락입니다.

5차 추가 필드는 다음처럼 분리해서 표시합니다.

```json
{
  "background_only_db": 70.9,
  "existing_environment_db": 70.9,
  "new_project_contribution_db": 72.47,
  "with_new_project_db": 74.76,
  "delta_total_db": 3.86,
  "baseline_impact": 25.73,
  "total_impact": 31.52,
  "incremental_impact": 5.79,
  "impact_saturation": {"level_component_at_ceiling": false,"incremental_zero_despite_physical_increase": false}
}
```

`new_project_contribution_db`와 `delta_total_db`는 다른 값입니다. 전자는 신규 음원 자체의 수음점 기여 레벨이고 후자는 기존 총환경 대비 물리적 증가입니다. 증분 Impact가 0이면서 포화 경고가 true이면 “영향 없음”으로 표시하지 말고 “점수 상한으로 추가 영향 구분 불가”로 표시합니다.

`GET /api/noise/background-profiles`의 `calculation_eligible`과 `quality_warnings`를 먼저 표시합니다. 요청에 `background_profile`을 생략하면 기존 `assumed_demo`가 유지됩니다. `road_traffic_observed_profile`은 명시 선택만 허용하고 과거 대표 패턴임을 표시하며, S-DoT 프로파일은 분석 전용이라 계산 요청 시 422가 정상입니다.

## Noise Slot 후보

```json
POST /api/schedules/optimize
{"scenario_id":"official_reference_equipment","analysis_date":"2026-10-26","sensitivity_enabled":true,"background_profile":"road_traffic_observed_profile","objective_mode":"incremental_impact"}
```

```json
{"optimization_status":"optimal_enumeration","recommended_options":[{"character":["construction_convenience","balanced"],"candidate":{"id":"offset-0","feasibility":true,"task_assignments":[{"task_id":"cut","start":"2026-10-26T07:00:00+09:00","end":"2026-10-26T08:00:00+09:00"}],"objective_values":{"resident_cost":13.72,"change_cost":0.0}}},{"character":["resident_protection"],"candidate":{"id":"offset-120","objective_values":{"resident_cost":13.20,"change_cost":480.0}}}],"diagnostics":{"generated_candidate_count":9,"feasible_candidate_count":9,"infeasible_candidate_count":0,"pareto_candidate_count":9}}
```

조정안이 하나면 카드 하나만 만들고 `character` 배열의 세 배지를 붙입니다. 서로 다른 세 후보처럼 복제하지 않습니다. 상세 후보표는 `GET /api/schedules/optimize/{scenario_id}/diagnostics`에서 조회합니다.

## 비교 결과

`before`와 `after`에는 optimize에서 받은 `task_assignments`를 그대로 넣습니다.

```json
POST /api/schedules/compare
{"scenario_id":"official_reference_equipment","analysis_date":"2026-10-26","background_profile":"road_traffic_observed_profile","before":[{"task_id":"cut","start":"2026-10-26T07:00:00+09:00","end":"2026-10-26T08:00:00+09:00"},{"task_id":"break","start":"2026-10-26T08:00:00+09:00","end":"2026-10-26T10:00:00+09:00"},{"task_id":"excavate","start":"2026-10-26T10:00:00+09:00","end":"2026-10-26T15:00:00+09:00"},{"task_id":"compact","start":"2026-10-26T15:00:00+09:00","end":"2026-10-26T16:00:00+09:00"}],"after":[{"task_id":"cut","start":"2026-10-26T09:00:00+09:00","end":"2026-10-26T10:00:00+09:00"},{"task_id":"break","start":"2026-10-26T10:00:00+09:00","end":"2026-10-26T12:00:00+09:00"},{"task_id":"excavate","start":"2026-10-26T12:00:00+09:00","end":"2026-10-26T17:00:00+09:00"},{"task_id":"compact","start":"2026-10-26T17:00:00+09:00","end":"2026-10-26T18:00:00+09:00"}]}
```

응답의 `before`, `after`, `delta`, `comparison_basis`를 그대로 사용합니다. 후보의 전체 assignment 배열을 전송해야 합니다.

## 기존 공사·행사 일정

`GET /api/public-data/catalog`의 `construction_events`와 `cultural_events`를 달력 레이어로 표시합니다. 공사의 `project_start_date/end_date`는 사업기간이지 일일 작업시간이 아닙니다. `work_start_time/end_time` 또는 `noise_db`가 빈 문자열이면 미확인 배지를 표시하고 소음 그래프에 합산하지 않습니다. 행사의 날짜별 시간이 `time_text`에만 있으면 원문은 표시하되 단일 시간으로 축약하지 않습니다.

`final-demo-congestion` 예측의 `existing_event_ids`와 `source_metadata.existing_events[].status=assumed`는 별도 “가정 실험” 레이어입니다. 서울시 원본 일정과 같은 색상이나 실측 배지를 쓰지 않습니다.

## 불가능 일정

```json
{"optimization_status":"infeasible","valid_candidates":[],"recommended_options":[],"infeasible_result":{"feasibility":false,"infeasibility_reasons":["순차 작업 540분이 일일 제한 480분을 초과"],"needs_confirmation":["덤프트럭 소음 원천값","미확정 공정 소요시간"]},"relaxation_guidance":["누락 공정시간을 확인","금지시간 또는 일일 제한을 담당자가 검토"]}
```

일정 카드를 만들지 말고 사유·확인사항·검토 가능한 완화 조건을 표시합니다. 시스템이 제약을 자동 완화한 것처럼 표현하지 않습니다.

## Before/After 지표

- `max_continuous_high_noise_minutes`: 분석 임계값 이상 최대 연속시간
- `longest_quiet_window_minutes`: 분석 구간 내 임계값 미만 최대 연속시간
- `sensitive_high_noise_minutes`: 민감도 1 초과이면서 고소음인 시간
- `max_impact_score`: 수음점-슬롯 최대 실험 점수
- `total_impact_score`: 모든 수음점-슬롯 점수 합계
- `schedule_change_minutes`: 작업별 원 시작시간과의 절대 차이 합계
- `delta`: after - before

`threshold_db=65`는 PoC 분석 임계값이며 법정 기준이 아닙니다.

추가 비교지표 `absolute_impact_cost`, `incremental_impact_cost`, `new_project_additional_high_noise_minutes`, `sensitive_new_project_exposure_minutes`를 별도 라벨로 표시합니다. 기본 추천 배지는 증분 목적이며, 절대 목적 비교가 필요하면 같은 요청을 `objective_mode=absolute_impact`로 재호출합니다. `policy_overlap_cost`는 진단용이고 현재 Pareto 비용에 포함되지 않습니다.

## 출처 표시

`verified_public`=검증 공공자료, `user_provided`=사용자 시나리오, `assumed`=실험 가정, `derived`=계산값, `missing`=누락으로 통일합니다. 색상 badge와 설명을 함께 쓰고 `legal_assessment=null`, disclaimer, 덤프트럭 경고를 숨기지 않습니다. B/C의 기존소음·시험기간은 반드시 `assumed`로 표시합니다.

도로 관측 프로파일도 수음점별 현장 실측이 아니라 특정 지점의 역사적 대표값이므로 `verified_public` 배지 옆에 공간 대표성 경고를 표시합니다. 포화 경고의 `level_component_at_ceiling` 또는 `incremental_zero_despite_physical_increase`가 true이면 증분 0을 “영향 없음”으로 번역하지 않습니다.

422는 필드 오류, 404는 시나리오 없음, 415는 파일 유형, 503은 선택 PDF 의존성 문제입니다. CORS는 배포 origin 확정 전 열지 않았습니다.
