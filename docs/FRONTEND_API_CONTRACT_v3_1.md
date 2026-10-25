# 프론트엔드 API 확정 계약 v3.1

검증일: 2026-10-25. 기존 v3(25개 API) 계약과 경로는 보존하며 아래 2개만 추가한다. 규범 스키마는 `docs/openapi.json`, TypeScript는 `frontend-contract/types/api.d.ts`, 실제 HTTP 전문은 `frontend-contract/examples/26-*.json`, `27-*.json`이다.

## POST `/api/prd/planning/from-notice`

요청은 `notice: ConstructionNotice`, `extractor_mode`, `is_actual_ai`, 선택적 `field_evidence`다. 응답 `PRDPlanningDraftResponse`는 nullable `planning_draft`, `missing_fields`, `confirmation_required_fields`, provenance와 경고를 반환한다. `status=needs_confirmation`인 초안을 확정 계획으로 사용하면 안 된다.

```ts
type Request = components["schemas"]["PRDPlanningDraftRequest"];
type Response = components["schemas"]["PRDPlanningDraftResponse"];
```

## POST `/api/prd/recommendations/constraint-filtered`

요청은 확정 `planning`, 날짜, task별 선후행·장비·대수·복구 매핑이다. 지원 날짜는 2026-09-11과 2026-10-07이다. 응답은 입력 계획/출처, 정책 버전, 원 일정, 전체 후보의 PRD 적합성·위반·조건부 Pareto·변경량·Noise Impact, 추천 가능 ID, 추천 없음 사유, 결측과 caveat를 반환한다.

```ts
type Request = components["schemas"]["PRDConstraintRecommendationRequest"];
type Response = components["schemas"]["PRDConstraintRecommendationResponse"];
```

프론트엔드는 `recommendable_candidate_ids` 또는 후보의 `recommendable=true`만 추천으로 표시한다. `pareto_after_constraint_filter`는 입력 제약과 기존 9개 offset 후보에 한정되며 전역 최적해가 아니다.

## 오류와 CORS

Pydantic 입력 오류와 미지원 날짜는 422, 알 수 없는 시나리오/데이터는 404다. 개발 origin `http://localhost:5173`, `http://127.0.0.1:5173`의 JSON POST preflight가 허용된다. 두 API 모두 명시적 `response_model`을 갖는다.

## 공개하지 않은 기능

주민 안내문 생성·승인·공개와 주민 조회 API는 계약에 포함하지 않는다. 공식 좌표, geometry, 주거 외벽 수음점, 실측 정확도도 생성하지 않는다.
