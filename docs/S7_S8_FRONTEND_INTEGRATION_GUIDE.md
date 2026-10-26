# S7·S8 프론트엔드 연동 가이드

API 계약: v3.3, 검증일: 2026-10-26

## S7 담당자 화면

1. 추천 응답에서 담당자가 `candidate_id`와 assignments를 선택한다.
2. `POST /api/staff/resident-notices/drafts`로 공사 정보, 공개 시간창, 공개 문의처, 일정 식별자·버전, 작업별 `high_noise`와 provenance를 보낸다.
3. 응답의 `missing_fields`가 비어 있는지 확인한다. 초안은 아직 `publication_status=private`다.
4. `GET /api/staff/resident-notices/drafts/{project_id}`로 다시 읽고 편집 화면을 채운다.
5. `PUT`에는 현재 `revision`을 `expected_revision`으로 포함한다. 409이면 최신 초안을 다시 읽는다.
6. 담당자가 확정 버튼을 누를 때만 `POST .../{project_id}/confirm`을 호출한다. 현재 revision과 schedule version이 모두 필요하다.

추천 API assignment를 매핑할 때 task 이름과 high-noise 여부는 추천 응답이 제공하지 않는 경우가 있으므로 담당자가 확인해야 한다. 확인되지 않은 값을 실제 값으로 추정하지 말고 `classification_source=assumed|demo`로 표시한다.

## S8 주민 화면

`GET /api/public/construction/{project_id}/resident-notice`

- `status=not_published`: “확정된 주민 안내가 없습니다” 상태만 표시한다.
- `status=published`: `notice`를 렌더링한다.
- `today_schedule`: 시간순 작업 목록
- `noisy_work_intervals`: 시끄러운 작업 배정 구간
- `longest_quiet_interval`: high-noise 미배정 최장 구간과 limitation을 함께 표시
- `hourly_noise_levels`: `quiet`, `moderate`, `loud` 및 한글 label
- `publication_provenance.data_classification=demo`: 실제 공지처럼 보이지 않도록 시연 배지를 표시

주민 화면은 staff API나 초안 응답을 캐시·재사용하면 안 된다. 공개 GET을 다시 조회한 결과만 주민에게 표시한다. 일정 변경 후 GET은 즉시 `not_published`로 바뀔 수 있다.

## TypeScript

```ts
type DraftCreate = components["schemas"]["ResidentNoticeDraftCreateRequest"];
type Draft = components["schemas"]["ResidentNoticeDraftResponse"];
type ResidentRead = components["schemas"]["ResidentPublicResponse"];
```

담당자 endpoint는 로컬/제한 시연 환경 전용이다. 프론트엔드를 외부 origin에 배포하는 것만으로 staff API 접근이 허용되지는 않는다.
