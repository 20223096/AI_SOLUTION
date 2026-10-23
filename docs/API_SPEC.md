# API 명세

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
| POST | `/api/impact/calculate` | 실험 영향점수 |
| POST | `/api/schedules/optimize` | 실행 가능·Pareto 후보 |
| GET | `/api/schedules/optimize/{id}/diagnostics` | 개발용 전체 후보 진단 |
| POST | `/api/schedules/compare` | Before/After |
| POST | `/api/experiments/run` | A/B/C 실험 |

요청 예:

```json
POST /api/schedules/optimize
{"scenario_id":"case-a","analysis_date":"2026-10-26"}
```

응답 핵심 예:

```json
{"scenario_id":"case-a","optimization_status":"optimal_enumeration","valid_candidates":[{"id":"offset-0","feasibility":true,"objective_values":{"resident_cost":1472.53,"change_cost":0.0}}],"recommended_options":[{"character":["construction_convenience","resident_protection","balanced"],"candidate":{"id":"offset-0"}}],"diagnostics":{"generated_candidate_count":9,"feasible_candidate_count":9,"infeasible_candidate_count":0,"pareto_candidate_count":1},"solver":"exact_enumeration"}
```

텍스트 추출: `{"text":"신촌 ... 07:00~18:00 ... 브레이커"}`. 영향점수: `{"total_noise_db":70,"threshold_db":65,"duration_minutes":60,"continuous_minutes":30,"sensitivity_weight":1.5}`. 예측: `{"scenario_id":"case-a","analysis_date":"2026-10-26"}`. 비교 요청은 같은 본문에 `before`, `after` TaskAssignment 배열을 추가합니다.

대용량 `predictions`는 `receptor_id`, `[slot_start,slot_end)`, 활성 작업, construction Lp, background level, existing noise Lp와 event IDs, total estimated dB, sensitivity, 각 출처를 담습니다. `sensitivity_enabled=false`는 물리 dB를 유지한 채 실험용 민감도만 끕니다. `background_profile` 기본값은 `assumed_demo`; `road_traffic_observed_profile`은 명시 선택할 때만 과거 신촌 LEQ 시간 패턴을 적용합니다. `sdot_observed_profile`은 지표 호환성 미확인으로 선택 시 422를 반환합니다.
