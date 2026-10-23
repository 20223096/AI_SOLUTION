# 프론트엔드 인계

기본 URL은 `http://127.0.0.1:8000`, Swagger는 `/docs`입니다. 권장 호출 순서는 health → scenarios → scenario detail → extract → optimize → 선택 후보 noise predict → compare/experiments입니다.

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
{"scenario_id":"scenario-b-congestion","analysis_date":"2026-10-26","sensitivity_enabled":true}
```

한 슬롯의 응답 형태:

```json
{"receptor_id":"residential-1","slot_start":"2026-10-26T07:00:00+09:00","slot_end":"2026-10-26T07:15:00+09:00","active_task_ids":["cut"],"construction_lp_db":72.52,"background_laeq_db":55.0,"existing_noise_lp_db":82.0,"existing_event_ids":["assumed-roadwork-b"],"total_estimated_db":82.46,"sensitivity":{"weight":1.0,"status":"assumed"},"source_metadata":{"existing_events":[{"status":"assumed","source":"PoC congestion experiment","unit":"Lp_dBA"}]}}
```

그래프는 `total_estimated_db`, 구성요소는 별도 범례로 표현합니다. null은 0이 아니라 누락입니다.

## Noise Slot 후보

```json
POST /api/schedules/optimize
{"scenario_id":"case-a","analysis_date":"2026-10-26","sensitivity_enabled":true}
```

```json
{"optimization_status":"optimal_enumeration","recommended_options":[{"character":["construction_convenience","resident_protection","balanced"],"candidate":{"id":"offset-0","feasibility":true,"task_assignments":[{"task_id":"cut","start":"2026-10-26T07:00:00+09:00","end":"2026-10-26T08:00:00+09:00"}],"objective_values":{"resident_cost":1472.53,"change_cost":0.0}}}],"diagnostics":{"generated_candidate_count":9,"feasible_candidate_count":9,"infeasible_candidate_count":0,"pareto_candidate_count":1}}
```

조정안이 하나면 카드 하나만 만들고 `character` 배열의 세 배지를 붙입니다. 서로 다른 세 후보처럼 복제하지 않습니다. 상세 후보표는 `GET /api/schedules/optimize/{scenario_id}/diagnostics`에서 조회합니다.

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

## 출처 표시

`verified_public`=검증 공공자료, `user_provided`=사용자 시나리오, `assumed`=실험 가정, `derived`=계산값, `missing`=누락으로 통일합니다. 색상 badge와 설명을 함께 쓰고 `legal_assessment=null`, disclaimer, 덤프트럭 경고를 숨기지 않습니다. B/C의 기존소음·시험기간은 반드시 `assumed`로 표시합니다.

422는 필드 오류, 404는 시나리오 없음, 415는 파일 유형, 503은 선택 PDF 의존성 문제입니다. CORS는 배포 origin 확정 전 열지 않았습니다.
