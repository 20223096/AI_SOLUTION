# Sprint 24 주민 안내문·공개 조회 구현 결과

검증일: 2026-10-26
기준 커밋: `5df173f0b6666d8c2c09ffd755fbaca358d79ad8`

## 저장소 조사와 선택

프로젝트에는 DB나 repository 계층이 없고 `backend/app/data/*.json` fixture를 읽는 방식이었다. 추천 응답은 `candidate_id`, assignments, PRD 적합성을 반환하지만 저장하지 않는다. 신규 DB 의존성을 추가하지 않고 동일한 JSON 계열의 `JsonNoticeRepository`를 구현했다.

운영 중 생성되는 데이터는 버전 관리 fixture와 분리해 기본 `runtime/resident_notices.json`에 원자적 temp-file replace로 저장하며 `runtime/`은 Git ignore다. process 내 read-modify-write는 재진입 lock으로 직렬화한다. `SHH_RESIDENT_NOTICE_STORE_PATH`로 제한 환경의 영속 경로를 지정할 수 있다.

## 구현

- deterministic 템플릿으로 공사명·위치·일정·시끄러운 시간·미배정 시간·문의처를 작성한다.
- 없는 정보는 만들지 않고 `missing_fields`에 기록하며 확정을 차단한다.
- revision 기반 optimistic concurrency와 schedule SHA-256 fingerprint를 저장한다.
- 수정은 문구만 바뀌어도 기존 확정본을 비공개로 전환한다.
- 중복 확정은 같은 publication version의 idempotent 성공이다.
- 확정 snapshot만 별도 주민 DTO로 생성한다.
- 담당자 API는 loopback/명시 허용 host로 제한하고 주민 API는 read-only로 분리한다.

## API와 검증

기존 28개 + 신규 5개 = 총 33개 operation이다. 신규 테스트는 초안, 수정, 비공개, 확정, 중복 확정, 결측, stale version, 일정 변경, 재시작, 공사 분리, quiet 계산, 3단계, DTO 누출, host 제한, CORS/OpenAPI를 포함한다.

S7→S8 실제 in-process HTTP 흐름은 생성 직후 주민 `not_published`, 확정 후 `published`를 확인했다. 저장소 객체를 새로 생성한 뒤에도 확정본이 유지되는 재시작 지속성을 검증했다. 기존 255개와 신규 13개를 합친 전체 `268 passed`를 확인했으며, 기존 9/11·10/7 및 M0/M1 고정값 테스트도 그대로 통과했다.

## 제한과 후속 결정

- 현재 추천 결과 자체가 서버에 저장되지 않으므로 `candidate_valid`와 high-noise 분류는 담당자 확인 입력이다. 향후 추천 snapshot 서버 저장과 서명/식별 연계를 결정해야 한다.
- loopback 제한은 인증이 아니다. 실제 배포에는 인증·인가, reverse proxy ACL, 사용자/행위 감사가 필요하다.
- 공지 취소·연기·긴급 변경 상태와 history 조회 UI는 기획 확정이 필요하다.
- 3단계는 일정 activity 표시이며 음향 정확도나 법적 준수를 뜻하지 않는다.
