# 최종 S1~S8 프론트엔드 통합 가이드

계약 버전: v3.4

## 화면별 연결

| 화면 | API | 다음 단계로 전달할 값 |
|---|---|---|
| S1 신고서 | `POST /api/notices/extract` | `notice`, mode, field evidence |
| S2 확인 | `POST /api/prd/planning/from-notice` | 계획 초안과 `missing_fields` |
| S2 지도 | `POST /api/locations/address-coordinate` | 공식 주소와 EPSG:4326 주소 핀 |
| S3 제약 | `POST /api/prd/schedules/validate` | 보완된 planning, 위반 목록 |
| S4 추천 | `POST /api/prd/recommendations/constraint-filtered` | 선택 후보, assignments, snapshot ID/version |
| S5 선택 | 프론트 상태 | recommendable 후보 하나를 명시적으로 선택 |
| S6 비교 | `POST /api/schedules/compare` | original/selected assignments 비교 결과 |
| S7 안내 | staff draft POST/GET/PUT/confirm | project ID, 선택 schedule snapshot, revision |
| S8 주민 | `GET /api/public/construction/{project_id}/resident-notice` | 확정 snapshot만 표시 |

`s1-s8-workflow.json`은 위 호출을 하나의 데이터 체인으로 재생한 전문이다. S1 추출값에는 결측이 있으므로 S3 전에 담당자가 planning을 보완한다. 주소 핀은 공사 geometry가 아니다. high-noise 분류, 공개 문의처, 안내 문구 수정과 확정도 담당자 입력이다.

## 추천 일정 binding

추천 후보를 고를 때 `candidate_id`, `assignments`, `schedule_snapshot_id`, `schedule_version`을 함께 보관한다. S7 요청에서 task 이름과 공개 분류를 붙일 수 있지만 task ID·시작·종료는 바꾸면 안 된다. 서버는 이 세 필드만 정규화해 snapshot fingerprint와 비교한다. 임의 시간 변경, 다른 공사 snapshot 재사용, 오래된 버전은 확정되지 않는다.

## quiet 표시

- 시간대별 `quiet`: 그 1시간 구간에 예정 작업 자체가 없음
- `moderate`: 예정 작업은 있으나 high-noise 작업은 없음
- `loud`: high-noise 작업과 겹침
- `longest_quiet_interval`: high-noise 작업이 없는 최장 연속 구간

따라서 longest interval 안에 `moderate` 시간이 포함될 수 있다. 화면 명칭은 “시끄러운 작업이 없는 최장 구간”을 권장하고 limitation 문구를 함께 표시한다. 이를 “실제 조용함 보장”으로 표현하면 안 된다.

## 빈 상태와 오류

- planning `needs_confirmation`: 누락 필드를 입력하기 전 추천 진행 금지
- 좌표 `selection_required`: 후보 선택 UI; 첫 후보 자동 선택 금지
- 추천 `none_feasible`: 추천 없음 표시
- 주민 `not_published`: 초안이나 과거 확정본을 대신 표시하지 않음
- staff 403: 로컬/허용 시연 host 밖에서 접근
- 409: stale revision, 상태 또는 schedule version 충돌; 최신 초안 재조회
- 422 `verified_recommendation_snapshot`: 추천 binding 불일치; S4부터 다시 선택
- 502/503: JUSO 공급자 또는 설정 오류

## 환경변수

프론트엔드에는 API origin만 둔다.

```env
VITE_SHH_API_BASE_URL=http://127.0.0.1:8765
```

백엔드 운영 설정 예시:

```env
SHH_CORS_ALLOWED_ORIGINS=["https://demo.example"]
SHH_STAFF_API_ALLOWED_HOSTS=["127.0.0.1"]
SHH_RESIDENT_NOTICE_STORE_PATH=/restricted/runtime/resident_notices.json
SHH_RECOMMENDATION_SNAPSHOT_STORE_PATH=/restricted/runtime/recommendation_snapshots.json
```

JUSO 키는 백엔드 `.env`에만 두고 프론트 번들에 넣지 않는다. 무인증 staff API를 인터넷에 직접 공개하지 않는다.
