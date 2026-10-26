# Sprint 22 프론트엔드 연동 테스트 결과

검증일: 2026-10-25. 시작 커밋: `41097b4`.

## 실제 HTTP S1~S4 재생

로컬 uvicorn에 다음 5회 요청을 순서대로 실행했다.

1. `POST /api/notices/extract`: 텍스트 신고서 입력 및 mock 추출.
2. `POST /api/prd/planning/from-notice`: 누락 필드와 확인 필요 필드 수신.
3. 사용자가 전체/장비 허용시간을 08:00~18:00으로 확인하고 장비·기간·출처를 보완한 뒤 `POST /api/prd/schedules/validate` 호출.
4. `POST /api/prd/recommendations/constraint-filtered`: PRD feasible/infeasible 후보와 조건부 추천 구분.
5. `POST /api/schedules/compare`: 원 일정과 선택한 `offset-60` 비교.

결과는 `frontend-contract/examples/prd-s1-s4-workflow.json`에 요청·응답 전문으로 보존했다. 원 일정 검증은 `outside_total_work_window`로 실패했고, 후보 중 `offset-0/15/30/45`는 불가능, `offset-60/75/90/105/120`은 가능, 추천 가능한 조건부 Pareto 후보는 `offset-60` 하나였다. 이는 HTTP 200의 정상 업무 결과다.

## 자동 테스트

- 전체 pytest: 247 passed.
- 기존 27개 route 및 27개 성공 캡처 호환성.
- 추출→초안 변환, null/결측 유지, 사용자 수정 후 재검증.
- 제약 실패, `none_feasible`, 일부 feasible, 단일 조건부 Pareto.
- 9/11 `offset-0`, 10/7 13.72→13.20 및 노출시간 동일 회귀.
- OpenAPI와 체크인 파일 동일성, 생성 TypeScript 신규 모델 포함.
- 허용/비허용 origin CORS.

## 변경 여부

백엔드 API와 계산 코드는 변경하지 않았다. 테스트·문서·재생 스크립트·계약 패키지만 보강했다. 좌표, 공사선형, 실측 정확도, 주민 공개 기능도 생성하거나 활성화하지 않았다.
