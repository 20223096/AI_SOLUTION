# S7·S8 주민 안내 발행 정책

검증일: 2026-10-26

## 확정 정책

Sprint 24의 안전 기본값은 **fail closed**다. 일정 버전, assignment 또는 안내 문구가 변경되면 현재 공개 snapshot을 즉시 비공개로 전환한다. 담당자가 변경본을 다시 명시적으로 확정하기 전까지 주민 API는 `not_published`만 반환한다.

이전 확정본은 주민 API에서 다시 노출하지 않는다. 내부 JSON 저장소의 `publication_history`에 확정 버전·확정 시각·일정 fingerprint·무효화 시각·사유와 snapshot을 감사 목적으로 보존한다. history는 담당자 API와 주민 DTO 모두에 직렬화하지 않는다.

이 정책은 안전한 PoC 기본값이다. 운영 전 기획팀은 다음을 확정해야 한다.

- 일정 변경이 경미할 때 기존 공지를 유지할 예외가 필요한지
- 이전 공지의 담당자용 이력 조회·복원 UI가 필요한지
- 공사 취소·연기·긴급 변경 전용 상태와 주민 알림 방식
- 실제 인증·권한·감사 로그·보존 기간

## 상태 전이

```text
없음 → draft(private) → confirmed(published)
          ↑                    │
          └──── 수정 ──────────┘  (기존 공개본 즉시 무효화)
```

- 생성된 초안은 `draft/private`다.
- 결측 필드, 빈 안내문, `candidate_valid=false`, schedule version 불일치는 확정할 수 없다.
- 같은 revision과 schedule version의 중복 확정은 같은 publication version을 반환하는 idempotent 성공이다.
- stale revision, 다른 schedule version, 중복 생성은 409다.
- 서로 다른 `project_id`는 저장소에서 독립 key로 관리한다.

## 접근 제한

담당자 생성·조회·수정·확정 API는 기본적으로 `127.0.0.1`, `::1`, `localhost`, 테스트 client만 허용한다. 제한 시연 환경은 `SHH_STAFF_API_ALLOWED_HOSTS` JSON 배열로 명시해야 한다. 이는 PoC 네트워크 제한이지 사용자 인증을 대체하지 않는다. 인터넷 배포 전에는 reverse proxy ACL과 실제 담당자 인증·인가를 추가해야 한다.

주민 API는 별도 read-only 경로이며 서버에 저장된 현재 확정 snapshot만 읽는다.

## 주민 공개 제한

별도 `ResidentPublicNotice` DTO는 다음만 포함한다: 오늘 일정, 시끄러운 작업 시간, 최장 quiet interval, 확정 문구, 공개 문의처, 시간대별 3단계, 공개 버전·출처 구분. dB 수치, Noise Impact, 민감도, 비교, 원본 신고서, 내부 메모, 제약 로그, 수음점, 비공개 연락처, 미확정 초안, publication history는 포함하지 않는다.

## 3단계와 quiet interval

`schedule_activity_v1`은 음향 측정 등급이 아니라 확정 일정의 작업 상태 표시다.

- `loud/시끄러움`: 해당 1시간 구간에 `high_noise=true`로 확인된 작업이 하나라도 겹침
- `moderate/보통`: 다른 예정 작업이 겹치지만 high-noise 작업은 없음
- `quiet/조용`: 예정 작업이 없음

dB 임계값, 법정 기준, 실측 검증을 사용하지 않는다. `measurement_validated=false`를 명시한다.

가장 긴 조용한 시간은 공개 시간창 안에서 `high_noise=true` 작업이 배정되지 않은 최장 연속 구간이다. 일반 작업이나 주변 환경 소음이 있을 수 있으므로 실제 정숙을 보장하지 않는다.
