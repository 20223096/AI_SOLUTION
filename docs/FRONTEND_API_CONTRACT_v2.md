# 쉿간표 프론트엔드 API 계약 v2

검증 기준: 2026-10-24, 백엔드 `poc-0.1.0`, OpenAPI 3.1.0. 이 문서는 `backend/app/main.py`, 21개 명시적 Pydantic 응답 모델, `app.openapi()` 결과와 Uvicorn 로컬 서버의 실제 HTTP 응답을 대조해 작성했다. 기존 계산·시나리오·URL·요청·응답 JSON은 변경하지 않았다.

## 1. 연결 규칙

| 항목 | 확정 내용 |
|---|---|
| 앱 진입점 | `backend/app/main.py`의 `app` |
| 로컬 Base URL | 실행 명령에 따라 결정. 검증에는 `http://127.0.0.1:8765` 사용. 일반 실행 예시는 `http://127.0.0.1:8000` |
| API prefix/version | 모든 업무 API는 `/api` 아래에 있으나 URL 버전 prefix는 없음. 앱 버전은 `poc-0.1.0` |
| 인증 | 없음. OpenAPI security scheme도 없음 |
| CORS | 기본 허용 origin은 `http://localhost:5173`, `http://127.0.0.1:5173`. 그 외 origin은 허용 헤더가 없고 preflight는 400. credentials는 비허용 |
| 요청/응답 | JSON. 파일 추출만 `multipart/form-data` |
| 날짜 | `YYYY-MM-DD` (`format: date`) |
| 시간 | `HH:mm:ss` (`format: time`) |
| 일시 | ISO 8601 (`format: date-time`). 예시는 `2026-10-26T07:00:00+09:00` |
| 타임존 | 설정값과 M0 응답은 `Asia/Seoul`; 설계 시뮬레이션은 `+09:00`을 생성. Pydantic은 일부 입력에서 offset 없는 datetime도 스키마상 막지 않으므로 클라이언트는 반드시 `+09:00` 포함 권장 |
| 슬롯 | 15분. M1 단일 예측은 정확히 900초이어야 함 |
| 소음 단위 | 필드명 `_db`, `_dba`, `_laeq_db`, `_laeq_dba`는 dB/LAeq dBA. `sound_power_level_db`는 Lw 계열이며 수음점 레벨과 동일하지 않음 |
| 정밀도 | M0/M1 표시 레벨은 주로 소수 둘째 자리, M1 거리 소수 셋째 자리, 에너지 노출은 소수 여섯째 자리. 입력 자체에 전역 소수 자릿수 제한은 없음 |
| null | `null`은 미측정·미확정·계산 불가를 뜻하며 0으로 대체 금지. 빈 배열은 “항목 없음”. 누락된 선택 필드는 기본값 적용 |

프론트엔드 환경변수는 API origin 하나면 된다. 예: `VITE_SHH_API_BASE_URL=http://127.0.0.1:8000`. 백엔드 운영 origin은 JSON 배열로 지정한다.

```env
SHH_CORS_ALLOWED_ORIGINS=["https://shh.example.com"]
```

개발 기본값은 두 Vite origin이다. `GET`, `POST`, `OPTIONS`, `Accept`, `Content-Type`만 허용하며 credentials는 false다. JSON 요청과 multipart 업로드 preflight를 모두 검증했다. 기본 mock 모드에서는 프론트엔드가 API 키를 알 필요가 없다.

## 2. OpenAPI 보장 범위

실제 [OpenAPI 원본](openapi.json)은 21개 operation 모두에 요청 스키마, 명시적 200 응답 스키마, 422 검증 오류 스키마를 제공한다. [TypeScript 타입](../frontend-contract/types/api.d.ts)은 `openapi-typescript@7.10.1`로 이 파일에서 자동 생성했으며 성공 응답은 더 이상 일괄 `unknown`이 아니다.

- 모든 라우트는 `response_model`을 가진다.
- 알려진 필드는 구체 타입·nullable·status literal로 검증한다.
- 데이터 출처처럼 제공기관별로 확장 가능한 객체는 `dict[str, Any]`로 보존해 기존 필드를 제거하지 않는다.
- 조건부 응답은 union 또는 optional 필드로 표현한다. `response_model_exclude_unset`을 사용하는 분기에서는 원래 없던 키를 추가하지 않는다.
- response model 적용 전 21개 HTTP 캡처와 적용 후 JSON을 완전 동일 비교했다.
- 전체 요청 스키마와 Method/Path는 v1 OpenAPI와 호환된다.

Swagger UI는 `/docs`, OpenAPI JSON HTTP 주소는 `/openapi.json`이다.

## 3. 전체 API 목록

21개 모두 로컬 Uvicorn 서버에서 실제 200 응답을 검증했다.

| # | Method | Path | 기능 | 요청 | 실제 200 응답 최상위 |
|---:|---|---|---|---|---|
| 1 | GET | `/api/health` | 상태/버전 | 없음 | `status`, `model_version`, `extractor_mode` |
| 2 | GET | `/api/poc/scenarios` | 시나리오 목록 | 없음 | 배열: `id`, `title`, `expected_feasibility` |
| 3 | GET | `/api/poc/scenarios/{scenario_id}` | 시나리오 상세 | path `scenario_id` 필수 | `id`, `title`, `settings`, `notice`, `equipment`, `receptors` |
| 4 | POST | `/api/notices/extract` | 텍스트 공고 추출 | `ExtractRequest` | `mode`, `is_actual_ai`, `notice`, `field_evidence`, `warnings` |
| 5 | POST | `/api/notices/extract-file` | txt/PDF 공고 추출 | multipart `file` 필수 | 4와 동일 |
| 6 | POST | `/api/noise/predict` | M0 슬롯별 예측 | `PredictRequest` | `scenario_id`, `analysis_date`, `timezone`, `predictions`, `warnings` 등 |
| 7 | GET | `/api/noise/background-profiles` | 배경소음 프로필 | 없음 | `profiles`, `default` |
| 8 | POST | `/api/noise/predict-m1` | M1 단일 슬롯 예측 | `M1PredictRequest` | `calculation_status`, `validation_status`, `results`, `missing_required_inputs` |
| 9 | POST | `/api/noise/compare-m0-m1` | 동일 M1 입력의 M0/M1 비교 | `M1PredictRequest` | `comparison_status`, `comparisons`, `m0`, `m1` |
| 10 | POST | `/api/noise/m1-uncertainty` | 결정론적 민감도 범위 | `M1UncertaintyRequest` | `analysis_type`, `cases`, `ranges`; 확률/CI는 null |
| 11 | POST | `/api/noise/evaluate-m1-candidates` | 최적화 후보 M1 평가 | `M1ScheduleEvaluationRequest` | `evaluation_status`, `candidates`, `pareto_candidates`, `recommended_candidate` |
| 12 | POST | `/api/noise/validate-m1-field` | M1 실측 정합/오차 평가 | `FieldValidationRequest` | `validation_status`, `mae`, `rmse`, `bias`, 오류 목록 |
| 13 | GET | `/api/noise/design-simulation/catalog` | 설계 기반 입력 카탈로그 | 없음 | 공식 설계/소음 참조, `official_prediction_status`, `validation_status` |
| 14 | POST | `/api/noise/design-simulation/reschedule` | 설계 기반 가정 재스케줄링 | `DesignBasedSimulationRequest` | `simulation_status`, 후보/추천, 부분 음향 결과 |
| 15 | POST | `/api/impact/calculate` | 실험용 impact 지수 | `ImpactRequest` | `score`, `components`, `weights`, 선택적 baseline/incremental |
| 16 | POST | `/api/schedules/optimize` | M0 일정 최적화 | `OptimizeRequest` | `valid_candidates`, `pareto_candidates`, `recommended_options`, `diagnostics` |
| 17 | POST | `/api/schedules/compare` | 두 배정의 지표 비교 | `CompareRequest` | `before`, `after`, `delta`, `schedule_change_details` |
| 18 | GET | `/api/schedules/optimize/{scenario_id}/diagnostics` | 최적화 진단 | path + query | 후보 수, 목적축, 후보별 metrics |
| 19 | POST | `/api/experiments/run` | 민감도/추천 실험 | `ExperimentRequest` | `experiment_a`, `experiment_b`, `experiment_c` |
| 20 | GET | `/api/public-data/catalog` | 전체 공개데이터 카탈로그 | 없음 | manifest, 설비/행사/수음점/공식 설계와 정책 |
| 21 | GET | `/api/public-data/construction-design` | 공식 공사 설계자료 | 없음 | 사업명, 구간, 물량, 장비 매칭, 일정 메타, 계산 준비도 |

요구 목록 밖에서 실제 등록된 API는 #12 `/api/noise/validate-m1-field`다.

### 200 응답 모델 매핑

| API | OpenAPI 200 schema |
|---|---|
| health | `HealthResponse` |
| scenarios 목록/상세 | `ScenarioListResponse` / `ScenarioDetailResponse` |
| notice text/file | `MockNoticeExtractResponse | LLMNoticeExtractResponse` |
| M0 predict | `NoisePredictResponse` |
| background profiles | `BackgroundProfilesResponse` |
| M1 predict | `M1PredictResponse` |
| M0/M1 compare | `M0M1CompareResponse` |
| M1 uncertainty | `M1UncertaintyResponse` |
| M1 candidates | `M1CandidateEvaluationResponse` |
| field validation | `FieldValidationResponse` |
| design catalog/reschedule | `DesignSimulationCatalogResponse` / `DesignSimulationResponse` |
| impact | `ImpactResponse` |
| optimize | `OptimizeSuccessResponse | OptimizeInfeasibleResponse` |
| schedule compare | `CompareResponse` |
| diagnostics | `DiagnosticsResponse` |
| experiments | `ExperimentResponse` |
| public catalog/construction design | `PublicDataCatalogResponse` / `ConstructionDesignResponse` |

각 모델의 모든 필드 타입·required·nullable·enum은 [openapi.json](openapi.json)의 `components.schemas`가 규범적 정의다. 아래 표와 설명은 화면 연결에 필요한 의미를 제공하며, 각 API의 완전한 성공 JSON은 10절 파일에 있다.

## 4. 요청 모델 계약

표기: **필수**는 JSON 키가 반드시 필요함, `nullable`은 명시적 `null` 허용, 선택 필드 미전송 시 표의 기본값 적용.

### 기본 및 일정 API

| 모델 | 필드: 타입 | 필수/nullable | 기본값·제약 |
|---|---|---|---|
| `ExtractRequest` | `text: string` | 필수, non-null | 최소 1자 |
| `PredictRequest` | `scenario_id: string`; `analysis_date: date`; `assignments: TaskAssignment[]`; `sensitivity_enabled: boolean`; `background_profile: string` | 전부 선택; `assignments`만 nullable | `case-a`; `2026-10-26`; null; true; `assumed_demo` |
| `TaskAssignment` | `task_id: string`; `start: datetime`; `end: datetime` | 모두 필수, non-null | 도메인 서비스가 작업 ID/시간 유효성 추가 검증 |
| `OptimizeRequest` | `scenario_id`; `analysis_date`; `sensitivity_enabled`; `background_profile`; `objective_mode` | 모두 선택, non-null | 앞 네 값은 Predict와 동일. objective 기본 `incremental_impact` |
| `CompareRequest` | `scenario_id`; `analysis_date`; `before: TaskAssignment[]`; `after: TaskAssignment[]`; `background_profile` | `before`, `after` 필수; 나머지 선택; non-null | `case-a`; `2026-10-26`; `assumed_demo` |
| `ExperimentRequest` | `scenario_id`; `analysis_date`; `background_profile`; `objective_mode` | 모두 선택, non-null | Optimize와 동일 |
| `ImpactRequest` | `total_noise_db: number`; `duration_minutes: integer`; `continuous_minutes: integer`; `sensitivity_weight: number`; `threshold_db: number`; `cumulative_burden: number`; `baseline_noise_db: number` | 앞 4개 필수; `baseline_noise_db` nullable; 나머지 선택 | duration/continuous ≥0, sensitivity >0, threshold 65, burden 0(≥0), baseline null |

`objective_mode` enum: `incremental_impact | absolute_impact | physical_energy | sensitive_exposure | continuous_burden | multi_axis`.

진단 GET의 query는 `analysis_date=2026-10-26`, `sensitivity_enabled=true`, `background_profile=assumed_demo`, `objective_mode=incremental_impact`가 기본이다. `objective_mode`는 이 GET에서 Pydantic enum이 아니라 단순 string으로 OpenAPI에 노출되지만 서비스는 지원하지 않는 값을 422로 거부한다.

### M1 공통 모델

| 모델 | 필수 필드 | 선택/nullable 필드 및 기본값 |
|---|---|---|
| `M1Point` | `x:number`, `y:number`, `crs`, `provenance` | `z_m:number=0`; 전부 non-null |
| `M1Receptor` | `id:string` | `position:M1Point|null = null` |
| `M1ActiveInterval` | `start:datetime`, `end:datetime` | end > start |
| `M1NoiseSource` | `id`, `segment_id`, `source_type`, `equipment_category`, `deployment_start`, `deployment_end` | `equipment_model|null`, `sound_power_level_db|null`, `reference_scenario|null`, `position|null`, `actual_active_minutes|null(0..15)`, `simultaneous_group|null`; `count=1`, `lw_provenance=unknown`, `activity_provenance=unknown`, `active_intervals=[]`, `measurement_condition_verified=false` |
| `M1PredictRequest` | `slot_start`, `slot_end`, `sources[]`, `receptors[]` | `background_laeq_db|null`, `background_provenance=unknown`, `overlap_mode=overlap_unknown`, `corrections={}`. 슬롯은 정확히 15분 |
| `M1PropagationCorrection` | 없음 | `value_db:null`, `status:not_modelled`, `source:null`. status가 not_modelled이면 value는 null이어야 하고, 그 외에는 숫자 필수 |
| `M1SensitivityCase` | `id`, `varied_variable`, `request:M1PredictRequest` | non-null |
| `M1UncertaintyRequest` | `cases:M1SensitivityCase[]` | 최소 1개 |
| `M1TaskAcousticMapping` | `task_id`, `segment_id`, `source_type`, `equipment_category` | source와 유사; `active_ratio:null(0..1)`, `position:null`, `count=1`, provenance 기본 unknown |
| `M1ScheduleEvaluationRequest` | `scenario_id`, `receptors[]`, `task_mappings[]` | `analysis_date=2026-10-26`, `background_profile=assumed_demo`, `overlap_mode=overlap_unknown` |

Enums:

- `segment_id`: `segment-yeonse-ro-2na-gil | segment-chungjeong-ro`
- `crs`: `EPSG:4326 | EPSG:5179 | EPSG:5186`
- point provenance: `official_design | field_verified | derived | assumed | unknown`
- source type: `fixed | moving_work | moving_vehicle | impulsive`
- Lw/background provenance: `official_reference | field_verified | derived | assumed | unknown` (Lw에는 `derived` 없음)
- source activity provenance: `field_verified | derived | assumed | unknown`
- reference scenario: `low | median | high | null`
- M1 overlap: `exact | complete_concurrent | sequential_possible | overlap_unknown`; 후보 평가는 `exact` 제외
- correction key: `ground | atmospheric | barrier | building | reflection | meteorology`
- correction status: `field_verified | derived | assumed | not_modelled`
- varied variable: `equipment_lw | activity_ratio | simultaneous_operation | source_position | receptor_position_or_height | background_profile | propagation_correction_availability`

### 실측 검증 모델

`FieldValidationRequest`는 선택 배열 `observations=[]`, `predictions=[]`를 받는다.

- `FieldObservation` 필수: `id`, `receptor_id`, `receptor_position`, `start`, `end`, `laeq_dba`, `measurement_duration_minutes>0`, `equipment_active`(string→boolean map), `instrument`, `calibration_before`, `calibration_after`, 비어 있지 않은 `weather`, `source`.
- 선택: `physical_location_id:string|null=null`, `acoustic_scope=total_environment`.
- `FieldPredictionRecord` 필수: `receptor_id`, `receptor_position`, `start`, `end`, `predicted_laeq_dba`.
- 선택: `physical_location_id:null`, `acoustic_scope=total_environment`, `equipment_ids=[]`, `metric=LAeq_dBA`(상수).
- acoustic scope enum: `total_environment | new_project_contribution`.
- 관측의 start/end 간격과 `measurement_duration_minutes`가 일치해야 한다.

### 설계 시뮬레이션 모델

`DesignBasedSimulationRequest` 필수는 `segment_id`, `receptor_id`(최소 1자), `receptor_segment_id`, `distance_m>0`이다. 선택 기본값은 `background_laeq_db=55`, `workday_start=07:00:00`, `workday_end=18:00:00`, `sensitive_start=08:00:00`, `sensitive_end=11:00:00`, `simulation_date=2026-10-26`이다. segment와 receptor_segment는 같아야 하고 두 시간 구간은 종료가 시작보다 늦어야 한다.

파일 추출은 multipart `file` 하나가 필수다. `text/*`, `.txt`, 또는 텍스트 추출 가능한 PDF만 허용한다. 텍스트는 UTF-8이어야 한다.

## 5. 실제 응답에서 사용하는 필드

### 공사 선택 및 상세

- 목록: `GET /api/poc/scenarios`의 각 항목에서 `id`, `title`, `expected_feasibility`.
- 상세: `notice.name`(공사명), `notice.location`, `notice.construction_period`, `notice.original_work_window`, `notice.tasks[]`, `equipment[]`, `receptors[]`, `settings.source_metadata`.
- nullable: 추출 결과에서는 공사명, 위치, 기간 날짜, 원 작업창 등이 null일 수 있다. 시나리오 상세의 현재 case-a는 값이 존재하지만 OpenAPI 응답 계약은 없음.

### M0 슬롯별 소음 예측

`POST /api/noise/predict`의 `predictions[]`에서 화면에 사용할 수 있는 실제 필드:

| 필드 | 관찰 타입/null | 의미 |
|---|---|---|
| `receptor_id` | string | 수음점 연결 키 |
| `slot_start`, `slot_end` | ISO datetime string | 시간대 |
| `active_task_ids` | string[] | 해당 슬롯 작업 |
| `construction_lp_db`, `new_project_contribution_db` | number 또는 null | 신규 공사 기여. 활성 소음원 값이 없으면 null |
| `background_laeq_db`, `background_only_db` | number | 배경소음 |
| `existing_noise_lp_db` | number 또는 null | 기존 이벤트 기여 |
| `existing_environment_db` | number | 배경+기존 환경 |
| `total_estimated_db`, `with_new_project_db` | number 또는 null | 전체 합성소음 |
| `delta_total_db` | number | 기존 환경 대비 총소음 증가 |
| `total_impact`, `baseline_impact`, `incremental_impact` | number | 실험용 impact 지수 |
| `impact_saturation` | object | 지수 포화 정보 |
| `sensitivity` | object | 민감도 계산 결과 |
| `source_metadata` | object | 배경/장비/기존 이벤트 출처 |

최상위 `warnings`, `legal_assessment:null`, `disclaimer`, `background_profile`, `calendar_overlaps`도 표시해야 한다. `legal_assessment`가 null이므로 법적 적합 판정을 만들면 안 된다.

### 최적화와 전후 비교

- 최적화: `valid_candidates[].task_assignments`가 시작/종료 작업표, `recommended_options[].candidate`가 추천 후보다.
- 후보 주요값: `id`, `feasibility`, `infeasibility_reasons`, `needs_confirmation`, `metrics`, `objective_values`, `schedule_change_details`, `provenance`.
- 추천 사유: `recommended_options[].character`, `.recommendation_reasons`.
- 전후 비교: `before`, `after`, `delta`는 같은 `ScheduleMetrics` 구조. 개선 방향은 지표별 의미에 따라 판단하며 무조건 음수/양수를 “개선”으로 일반화하지 않는다.
- 일정 변경: `schedule_change_details.task_start_shift_minutes`, `total_task_start_shift_minutes`, `project_start_shift_minutes`, `project_end_shift_minutes`, 두 project end.

`ScheduleMetrics`의 관찰 필드는 `max_continuous_high_noise_minutes`, `longest_quiet_window_minutes`, `sensitive_high_noise_minutes`, `max_impact_score`, `total_impact_score`, `absolute_impact_cost`, `incremental_impact_cost`, `new_project_additional_high_noise_minutes`, `sensitive_new_project_exposure_minutes`, `sensitive_new_project_receptor_minutes`, `sensitivity_weighted_new_project_receptor_minutes`, `new_project_receptor_minutes`, `new_project_inactive_minutes`, `max_continuous_new_project_minutes`, `new_project_energy_exposure_65db_ref_minutes`, `cumulative_delta_db_minutes`, `existing_noise_overlap_receptor_minutes`, `max_total_estimated_db`, `max_new_project_contribution_db`, `saturation_slot_count`, `schedule_change_minutes`, `project_start_change_minutes`, `project_end_change_minutes`다.

### M1 및 공식 설계 데이터

- M1 단일 슬롯: `calculation_status`, `validation_status`, `background`, `corrections`, `results[]`, `missing_required_inputs`.
- M1 결과: 신규 기여 `new_project_contribution_laeq_db`/`slot_laeq_dba`, 합성 `total_laeq_db`, 증가 `delta_total_db`, 에너지 노출, 동시성 범위, source별 Lw 출처와 거리.
- M0/M1 비교: `comparisons[]`, 완전한 `m0`, `m1`; `accuracy_improvement_claimed`는 false로 검증됨.
- 후보 평가: `evaluation_status`, `candidates`, `pareto_candidates`, `recommended_candidate`, `recommendation_reasons`, `input_provenance`.
- 공식 자료: construction-design의 `project_name`, `segments`, `work_packages`, `equipment_reference_matching`, `schedule_metadata`, `calculation_readiness`.
- 공식 구간의 `geometry`와 `representative_point`는 현재 null이며 `calculation_readiness.acoustic_prediction`과 `.distance_calculation`은 deferred다.
- 설계 기반 reschedule은 공식 형상을 채우지 않고 요청 `distance_m`로 만든 `simulation_geometry`를 별도 반환한다.

## 6. 상태값 처리

| 값 | 실제 필드/상황 | 프론트엔드 처리 |
|---|---|---|
| `deferred` | M1 `calculation_status`; 후보 `evaluation_status`; 공식 설계 `calculation_readiness`; 설계 시뮬레이션 `official_field_prediction_status` | 결과 숫자가 null/빈 배열일 수 있다. `missing_required_inputs`를 표시하고 계산 완료처럼 시각화하지 않는다 |
| `simulated` | M1 후보 `evaluation_status`; 설계 reschedule `simulation_status`; 구간 simulation status | 공식 실측값이 아닌 가정 입력 결과로 라벨링. `input_provenance`/`data_quality.simulation_assumption` 병기 |
| `partial` | 설계 후보 `acoustic_completeness` | 알려진 장비만 계산됨. `_partial` 지표만 제한적으로 표시하고 누락 장비 목록을 함께 표시. 전체 공사값으로 표현 금지 |
| `not_evaluable` | `validation_status`(M1, 실측 검증, 설계 카탈로그/시뮬레이션) | 정확도/MAE/RMSE/bias 판정 불가. 해당 값은 null이며 “0 오차”로 표시 금지 |

실제 성공 캡처에서 M1 단일 예측은 `calculation_status=calculated`, `validation_status=not_evaluable`; 후보 평가는 `evaluation_status=simulated`; 설계 reschedule은 `official_field_prediction_status=deferred`, `simulation_status=simulated`, `validation_status=not_evaluable`, 후보 `acoustic_completeness=partial`이었다.

## 7. M0/M1 구분

M0 `/api/noise/predict`는 저장된 PoC 시나리오, 장비 소음과 수음점 거리를 이용한 기존 슬롯 예측이다. `model_version=poc-0.1.0`, `scoring_version=legacy_v1`이며 민감도/impact와 최적화 흐름에 직접 연결된다.

M1 `/api/noise/predict-m1`은 소음원 위치, 수음점 좌표, 실제 활성시간, 동시성, 전파 보정의 provenance를 명시적으로 받는다. 입력이 부족하면 임의 보완하지 않고 deferred/null을 반환한다. 현재 `validation_status=not_evaluable`이며 M0보다 정확하다고 주장하지 않는다.

공식 설계 데이터는 공사 구간·물량·문서 출처에는 공식 provenance가 있으나 실제 장비 모델/운전시간/공식 형상/수음점 거리가 없다. 따라서 공식 데이터 자체의 음향 예측은 deferred다. 설계 기반 reschedule은 공식 물량을 시간으로 자동 변환하지 않으며 별도 simulation assumption을 사용하는 가정 실험이다.

## 8. 오류 계약

실제로 재현한 오류 전문은 `examples/error-*.json`에 있다.

| HTTP | 실제 조건 | 응답 구조 |
|---:|---|---|
| 404 | 없는 scenario ID (`predict`, optimize/compare/experiment/M1 후보 평가, scenario detail) | `{"detail":"'unknown scenario: missing'"}` 형태의 string detail |
| 415 | extract-file에 지원하지 않는 content type | `{"detail":"Only UTF-8 text or text-extractable PDF is supported"}` |
| 422 | Pydantic 필수/타입/범위/enum/모델 검증 | `HTTPValidationError`: `detail[]`에 `type`, `loc`, `msg`, `input`, 선택 `ctx` |
| 422 | 서비스 도메인 오류(없는 background profile, 불가능한 동시성 등) | `{"detail":"..."}` 형태의 string detail. OpenAPI의 배열형 422와 다르므로 둘 다 처리 |
| 503 | PDF 요청 시 런타임에 `pypdf`가 설치되지 않은 경우에만 코드상 가능 | string `detail`; 현재 환경에는 설치되어 있어 재현 대상 아님 |
| 500 | 문서화된 명시적 handler 없음 | 표준 FastAPI 500. 기본 mock 모드의 21개 정상 호출에서는 발생하지 않음. LLM 모드 설정 누락/외부 실패는 catch되지 않아 500 가능 |

명시적으로 발생시키는 400 응답은 현재 코드에 없다. 프론트엔드는 400을 특정 스키마로 가정하지 말고 일반 비정상 응답으로 처리한다. 404/415/서비스 422는 `detail:string`, Pydantic 422는 `detail:array`다.

## 9. 전체 프론트엔드 연동 흐름

1. `GET /api/poc/scenarios`에서 `id/title`을 선택 목록에 표시한다.
2. `GET /api/poc/scenarios/{id}`에서 `notice`, `tasks`, `equipment`, `receptors`, provenance를 표시한다.
3. `POST /api/noise/predict`에 `{scenario_id, analysis_date}`를 보낸다. `predictions[]`를 `receptor_id`와 슬롯으로 그룹화해 배경, 신규 기여, 전체, impact를 그린다.
4. `POST /api/schedules/optimize`에 같은 scenario/date/profile을 보낸다. `recommended_options[0].candidate.task_assignments`를 추천 시간표로 사용하되 `needs_confirmation`과 provenance를 함께 표시한다.
5. 원 일정은 `valid_candidates`에서 `id=offset-0` 후보를 선택하고, 추천 후보와 함께 `POST /api/schedules/compare`의 `before`/`after`에 전달한다.
6. `delta`와 `schedule_change_details`로 변경 전후를 표시한다. 실제 재현 가능한 전체 요청은 [17-schedule-compare.json](../frontend-contract/examples/17-schedule-compare.json)에 있다.

```ts
import type { components } from "../frontend-contract/types/api";

type PredictRequest = components["schemas"]["PredictRequest"];
type PredictResponse = components["schemas"]["NoisePredictResponse"];
type OptimizeRequest = components["schemas"]["OptimizeRequest"];
type OptimizeResponse =
  | components["schemas"]["OptimizeSuccessResponse"]
  | components["schemas"]["OptimizeInfeasibleResponse"];
type CompareRequest = components["schemas"]["CompareRequest"];
type ApiError = { detail: string } | components["schemas"]["HTTPValidationError"];

const base = import.meta.env.VITE_SHH_API_BASE_URL;

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${base}${path}`, init);
  const body = await response.json();
  if (!response.ok) throw { status: response.status, body: body as ApiError };
  return body as T;
}

const predictBody: PredictRequest = { scenario_id: "case-a", analysis_date: "2026-10-26" };
const prediction = await call<PredictResponse>("/api/noise/predict", {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(predictBody),
});

const optimizeBody: OptimizeRequest = { scenario_id: "case-a", analysis_date: "2026-10-26" };
const optimize = await call<OptimizeResponse>("/api/schedules/optimize", {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(optimizeBody),
});

if (optimize.optimization_status === "optimal_enumeration") {
  const before = optimize.valid_candidates.find(candidate => candidate.id === "offset-0")!;
  const after = optimize.recommended_options[0].candidate;
  const compareBody: CompareRequest = {
    scenario_id: "case-a", analysis_date: "2026-10-26",
    before: before.task_assignments, after: after.task_assignments,
  };
  await call<components["schemas"]["CompareResponse"]>("/api/schedules/compare", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(compareBody),
  });
}
```

## 10. 실제 요청·응답 예시 인덱스

각 파일은 Method, 전체 URL, headers, query가 포함된 URL, request body/multipart, 실제 HTTP status, content-type, response body 전문을 포함한다.

- [성공 검증 manifest](../frontend-contract/examples/manifest.json)
- [01 health](../frontend-contract/examples/01-health.json), [02 scenarios](../frontend-contract/examples/02-scenarios.json), [03 detail](../frontend-contract/examples/03-scenario-detail.json)
- [04 text extract](../frontend-contract/examples/04-notice-extract.json), [05 file extract](../frontend-contract/examples/05-notice-extract-file.json)
- [06 M0 predict](../frontend-contract/examples/06-noise-predict.json), [07 profiles](../frontend-contract/examples/07-background-profiles.json)
- [08 M1 predict](../frontend-contract/examples/08-noise-predict-m1.json), [09 M0/M1](../frontend-contract/examples/09-noise-compare-m0-m1.json), [10 uncertainty](../frontend-contract/examples/10-m1-uncertainty.json)
- [11 M1 candidates](../frontend-contract/examples/11-evaluate-m1-candidates.json), [12 field validation](../frontend-contract/examples/12-validate-m1-field.json)
- [13 design catalog](../frontend-contract/examples/13-design-simulation-catalog.json), [14 design reschedule](../frontend-contract/examples/14-design-simulation-reschedule.json)
- [15 impact](../frontend-contract/examples/15-impact-calculate.json), [16 optimize](../frontend-contract/examples/16-schedule-optimize.json), [17 compare](../frontend-contract/examples/17-schedule-compare.json), [18 diagnostics](../frontend-contract/examples/18-optimization-diagnostics.json), [19 experiments](../frontend-contract/examples/19-experiments-run.json)
- [20 public catalog](../frontend-contract/examples/20-public-data-catalog.json), [21 construction design](../frontend-contract/examples/21-construction-design.json)
- [404](../frontend-contract/examples/error-404-scenario.json), [415](../frontend-contract/examples/error-415-upload.json), [422 schema](../frontend-contract/examples/error-422-validation.json), [422 domain](../frontend-contract/examples/error-422-domain.json)

## 11. 미확정 사항

- 운영 배포 Base URL과 운영 CORS origin은 배포 담당자가 확정해 `SHH_CORS_ALLOWED_ORIGINS`에 지정해야 한다.
- API URL 버전 정책이 없다.
- naive datetime의 거부 규칙이 없으므로 타임존 강제가 스키마 수준에서 보장되지 않는다.
- 공식 구간 geometry/source point, 실제 장비 모델·운전시간, 현장 배경소음과 정렬된 실측값이 없어 공식 음향 계산과 정확도 검증은 deferred/not_evaluable이다.
- LLM 추출 모드는 외부 제공자·모델·키·네트워크에 의존하며 이번 기본 mock 서버의 성공 계약에는 포함하지 않았다.
- API별 400/404/415/422/503/500 응답을 OpenAPI responses에 명시하지 않아 문서 스키마와 런타임 오류가 완전히 일치하지 않는다.
