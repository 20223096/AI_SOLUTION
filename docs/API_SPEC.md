# API 명세

## 공공데이터 카탈로그

`GET /api/public-data/catalog`는 수집 매니페스트, 정규화 행과 통합 정책을 반환한다. `status`, `source_url`, `fetched_at`으로 실패와 출처를 그대로 노출한다. 일정만 있고 `noise_db`, 실제 시작·종료시각이 없는 이벤트는 소음 합성 대상이 아니다.

```json
{
  "manifest": {"collector_version": "1.0.0", "results": []},
  "academic_calendar": [
    {"institution": "sogang", "event_type": "exam", "start_date": "2026-10-20", "end_date": "2026-10-26", "status": "processed"}
  ],
  "policy": {"schedule_only_events_are_energy_summed": false, "coordinate_crs_required_for_distance": true, "unverified_values_used_for_acoustic_calculation": false}
}
```

`sinchon-public-2026-10` 시나리오는 2026-10-20~26에 서강대 공식 시험일정으로부터 대학 유형 민감도를 파생한다. 가중치 자체는 정책 가정이며 다른 대학 일정으로 일반화하지 않는다.

기본 JSON, 날짜 `YYYY-MM-DD`, 날짜시간 ISO 8601(+09:00)입니다. 오류는 FastAPI 표준 4xx 형식입니다.

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/health` | 버전과 extractor 모드 |
| GET | `/api/poc/scenarios` | CASE A/B 목록 |
| GET | `/api/poc/scenarios/{id}` | 모델·출처 포함 상세 |
| POST | `/api/notices/extract` | JSON 텍스트 구조화 |
| POST | `/api/notices/extract-file` | UTF-8 text/PDF 업로드 |
| POST | `/api/noise/predict` | 슬롯·수음점 예상치 |
| GET | `/api/noise/background-profiles` | 가정/관측 프로파일과 사용 가능 여부 |
| GET | `/api/public-data/catalog` | 공공데이터 수집 상태·정규화 결과·통합 정책 |
| POST | `/api/impact/calculate` | 실험 영향점수 |
| POST | `/api/schedules/optimize` | 실행 가능·Pareto 후보 |
| GET | `/api/schedules/optimize/{id}/diagnostics` | 개발용 전체 후보 진단 |
| POST | `/api/schedules/compare` | Before/After |
| POST | `/api/experiments/run` | A/B/C 실험 |

요청 예:

```json
POST /api/schedules/optimize
{"scenario_id":"case-a","analysis_date":"2026-10-26","background_profile":"road_traffic_observed_profile","objective_mode":"incremental_impact"}
```

응답 핵심 예:

```json
{"scenario_id":"case-a","optimization_status":"optimal_enumeration","valid_candidates":[{"id":"offset-0","feasibility":true,"objective_values":{"resident_cost":297.52,"absolute_impact_cost":3907.32,"incremental_impact_cost":297.52,"change_cost":0.0,"policy_overlap_cost":0.0}}],"diagnostics":{"generated_candidate_count":9,"feasible_candidate_count":9,"pareto_candidate_count":9,"objective_mode":"incremental_impact","policy_overlap_cost_included_in_pareto":false},"solver":"exact_enumeration"}
```

텍스트 추출: `{"text":"신촌 ... 07:00~18:00 ... 브레이커"}`. 영향점수: `{"total_noise_db":70,"threshold_db":65,"duration_minutes":60,"continuous_minutes":30,"sensitivity_weight":1.5}`. 예측: `{"scenario_id":"case-a","analysis_date":"2026-10-26"}`. 비교 요청은 같은 본문에 `before`, `after` TaskAssignment 배열을 추가합니다.

대용량 `predictions`는 `receptor_id`, `[slot_start,slot_end)`, 활성 작업, construction Lp, background level, existing noise Lp와 event IDs, total estimated dB, sensitivity, 각 출처를 담습니다. `sensitivity_enabled=false`는 물리 dB를 유지한 채 실험용 민감도만 끕니다. `background_profile` 기본값은 `assumed_demo`; `road_traffic_observed_profile`은 명시 선택할 때만 과거 신촌 LEQ 시간 패턴을 적용합니다. 이때 background metadata는 원자료 `status=verified_public`, 대표값 `value_status=derived`, 가상 수음점 적용 `spatial_application_status=assumed`를 구분합니다. `sdot_observed_profile`은 지표 호환성 미확인으로 선택 시 422를 반환합니다.

예측 슬롯에는 하위 호환 필드 `total_estimated_db`, `construction_lp_db`와 함께 `background_only_db`, `existing_environment_db`, `with_new_project_db`, `new_project_contribution_db`, `delta_total_db`, `total_impact`, `baseline_impact`, `incremental_impact`, `impact_saturation`이 추가됩니다. `new_project_contribution_db`는 신규 음원의 수음점 기여 Lp이고 `delta_total_db`가 총소음의 산술 증가량입니다.

`POST /api/impact/calculate`는 선택적으로 `baseline_noise_db`를 받습니다. 기존 요청은 기존 응답을 유지하고, baseline을 보내면 `baseline_score`, `incremental_score`, `saturation`을 추가합니다. 최적화의 `objective_mode`는 `incremental_impact`(기본) 또는 `absolute_impact`입니다.
