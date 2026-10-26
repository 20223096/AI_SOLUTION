# 프론트엔드 API 계약 v3.4

검증일: 2026-10-26. operation은 v3.3과 같은 33개이며 기존 요청 경로와 계산 로직을 유지한다.

## v3.3 대비 additive 변경

`POST /api/prd/recommendations/constraint-filtered`의 추천 가능 후보에 다음 필드를 추가했다.

- `schedule_snapshot_id`: 서버 저장 추천 snapshot 식별자
- `schedule_version`: 확정 연결용 불변 버전
- `schedule_fingerprint`: 공사·후보·task 시작/종료 binding SHA-256

추천 불가능 후보에는 세 필드가 `null`이다. `SelectedNoticeSchedule`은 선택적 `schedule_snapshot_id`를 받는다. 추천 API 출처를 사용하는 S7 요청은 snapshot ID가 필수이며, 공사 ID·후보·버전·assignment가 서버 snapshot과 일치해야 `recommendation_snapshot_status=verified`가 된다. 일치하지 않으면 초안 저장은 가능하지만 확정은 422로 차단한다. `manual_confirmed_schedule`은 담당자 수동 일정이라는 별도 provenance로 `not_required`다.

규범 파일은 `docs/openapi.json`, 생성 타입은 `frontend-contract/types/api.d.ts`다. 연결된 실제 HTTP 전문은 `frontend-contract/examples/s1-s8-workflow.json`이다.

## operation 수

- 기존 S1~S6 및 좌표: 28
- S7/S8: 5
- 합계: 33

신규 endpoint는 없다. 기존 v3.3 클라이언트는 추가 응답 필드를 무시할 수 있지만, 추천 기반 확정 UI는 반드시 snapshot ID와 schedule version을 S7로 전달해야 한다.
