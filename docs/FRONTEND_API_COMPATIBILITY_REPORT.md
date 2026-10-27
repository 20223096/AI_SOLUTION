# Frontend API Compatibility Report — v3.4

검증일: 2026-10-27. 규범 파일은 `docs/openapi.json`이며 **33 operations**이다. 프론트 타입은 `frontend-contract/types/api.d.ts`와 동기화했다.

## 화면별 실제 호출

| 화면 | Method / URL | 상태 |
|---|---|---|
| S1 | POST `/api/notices/extract` | 연결 |
| S1 | POST `/api/notices/extract-file` multipart `file` | 연결 |
| S2 | POST `/api/prd/planning/from-notice` | 연결, nullable/missing 유지 |
| S2 | POST `/api/locations/address-coordinate` | UI 연결, 다중 후보 명시 선택, 실키 E2E 차단 |
| S3 | POST `/api/prd/schedules/validate` | 연결 |
| S4 | POST `/api/prd/recommendations/constraint-filtered` | 연결, none-feasible 처리 |
| S5 | 서버 응답에서 명시 선택 | allow-list + recommendable + feasible 검사 |
| S6 | POST `/api/schedules/compare` | 연결 |
| S7 | POST/GET/PUT `/api/staff/resident-notices/drafts...` | 연결(화면은 POST/PUT 사용, GET client 제공) |
| S7 | POST `/api/staff/resident-notices/drafts/{id}/confirm` | snapshot/version/revision 연결 |
| S8 | GET `/api/public/construction/{id}/resident-notice` | 공개 API만 재조회 |

나머지 21 operations는 계산·진단·실험·카탈로그용이며 S1~S8 기본 화면에서 호출하지 않는다. “33개 API 모두를 UI가 호출한다”는 의미가 아니라, 33개 계약 중 화면에 필요한 12개 경로가 호환된다는 뜻이다.

## 계약 점검

- URL/HTTP method: OpenAPI와 일치.
- 요청/응답 필드: v3.4 생성 타입 사용. 추천의 `schedule_snapshot_id`, `schedule_version`은 S7에 전달한다.
- nullable: S2 결측값을 자동 추정하지 않고 사용자 보완을 요구한다. 추천 snapshot nullable은 S7 확정 차단 조건이다.
- 순서: extract → planning/coordinate → validate → recommend → select → compare → draft/update/confirm → public read.
- CORS: dev는 Vite proxy. production은 `SHH_CORS_ALLOWED_ORIGINS` 필요.
- 환경변수: 프론트는 `VITE_SHH_API_BASE_URL`만 사용. JUSO 키는 백엔드 전용.
- 인증/host: staff API는 loopback/allow-list 제한이며 실제 인증·인가가 아니다.
- Mock: 추출기 기본값은 백엔드의 명시적 `mock` 모드이며 UI가 이를 표시한다. 화면 자체에 추천/비교/공개 API 성공 mock fallback은 없다.

## 예외 검증

| 항목 | 결과 |
|---|---|
| 신고서 누락 필드 | 백엔드 + 프론트 guard 통과 |
| JUSO 다중 후보 | 첫 후보 자동 선택 금지, backend mock test 통과 |
| 좌표 실패/공급자 오류 | 상태 유지 및 UI 오류 표시 통과 |
| 모든 후보 제약 위반 | `none_feasible` backend test 통과 |
| 후보 1개 | backend + frontend 선택 guard 통과 |
| 서버/네트워크 오류 | ApiError test 통과 |
| snapshot 불일치 | 확정 422 backend test 통과 |
| S7 미확정→S8 비공개 | 실제 HTTP `not_published` |
| S7 확정→S8 공개 | 실제 HTTP `published` |
| 일정 수정 후 재확정 | 기존 공개 즉시 무효화 backend test 통과 |
| 주민 내부 수치 미노출 | 공개 DTO backend test 및 frontend test 통과 |

## 불일치와 미완성

1. 원본 프론트는 v3.1/27 API라고 표시하고 좌표 및 S7/S8 서버 API를 사용하지 않았다. 통합에서 v3.4로 수정했다.
2. 유효 JUSO 키가 없어 실제 공식 주소 좌표 성공, 다중 후보 실서비스 응답은 검증하지 못했다.
3. 실제 브라우저 자동화와 접근성/반응형 육안 검증은 미수행이다.
4. staff API에는 운영 인증이 없으며 loopback 제한은 인증 대체가 아니다.
5. S7 high-noise 분류는 서버 추정 대신 담당자 체크 입력이며, 실제 현장 확인 기능은 아니다.
