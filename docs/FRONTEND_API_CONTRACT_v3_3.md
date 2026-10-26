# 프론트엔드 API 계약 v3.3

검증일: 2026-10-26. v3.2의 28개 operation을 변경하지 않고 S7/S8 5개 operation을 추가해 총 33개다.

## 신규 operation

| 구분 | Method | Path | 성공 모델 |
|---|---|---|---|
| 초안 생성 | POST | `/api/staff/resident-notices/drafts` | `ResidentNoticeDraftResponse` |
| 초안 조회 | GET | `/api/staff/resident-notices/drafts/{project_id}` | `ResidentNoticeDraftResponse` |
| 초안 수정 | PUT | `/api/staff/resident-notices/drafts/{project_id}` | `ResidentNoticeDraftResponse` |
| 담당자 확정 | POST | `/api/staff/resident-notices/drafts/{project_id}/confirm` | `ResidentNoticeDraftResponse` |
| 주민 공개 조회 | GET | `/api/public/construction/{project_id}/resident-notice` | `ResidentPublicResponse` |

staff API 오류는 `NoticeErrorResponse`로 403, 404, 409, 422 상태를 명시한다. Pydantic request 자체가 유효하지 않은 경우도 422이며 FastAPI validation detail 형식이다. 주민 조회는 확정본이 없어도 200과 `status=not_published`를 반환한다.

규범 스키마는 `docs/openapi.json`, TypeScript는 `frontend-contract/types/api.d.ts`, 전체 S7→S8 요청·응답은 `frontend-contract/examples/s7-s8-resident-notice-workflow.json`이다.

기존 v3.2 좌표 계약과 28개 operation의 경로·모델·계산 결과는 보존한다. 저장·상태·공개 제한은 `S7_S8_PUBLICATION_POLICY.md`, 화면 연결은 `S7_S8_FRONTEND_INTEGRATION_GUIDE.md`를 따른다.
