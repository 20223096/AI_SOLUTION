# Sprint 25 S1~S8 전체 통합 검증 결과

검증일: 2026-10-26
기준 커밋: `52017c89c1e6dbd46aa2033bcb65fb6cfabf7daa`

## 실제 HTTP 결과

localhost uvicorn 서버에 `verify_s1_s8_workflow.py`를 실행했다. 별도 API 호출 모음이 아니라 앞 단계 응답을 다음 요청에 전달하는 13단계 연결 흐름이다.

1. S1 mock 신고서 추출
2. S2 PRD 계획 초안과 결측 확인
3. 담당자 planning 수동 보완
4. 승인 JUSO의 실제 주소 좌표 조회(EPSG:5179 → EPSG:4326)
5. 원 일정 제약 검증
6. 제약 필터 추천과 서버 snapshot 저장
7. recommendable `offset-60` 선택
8. original/selected 일정 비교
9. snapshot-bound S7 초안 생성(`verified`)
10. 담당자 문구 수정
11. 확정 전 S8 `not_published`
12. 명시적 confirm
13. S8 `published`

수동 입력이 필요한 값은 결측 planning, high-noise 작업 분류, 공개 문의처, 안내문 편집·확정이다. 전체 전문은 `frontend-contract/examples/s1-s8-workflow.json`에 있다.

## 추천 일관성 보강

Sprint 24는 `candidate_valid`를 클라이언트가 제공해 추천 출처를 사칭할 수 있었다. Sprint 25는 추천 계산 직후 runtime JSON에 공사 ID·후보·task 시작/종료 snapshot을 원자적으로 저장한다. 추천 응답의 snapshot ID/version/fingerprint를 S7에서 다시 검증한다. assignment 조작, 다른 공사 재사용, version 불일치, snapshot 없음은 확정을 차단한다. 서버 재시작 뒤에도 추천 binding과 확정 공지가 유지된다.

수동 확정 일정은 `manual_confirmed_schedule` provenance로 별도 허용한다. 이는 추천 결과라는 주장을 하지 않는 담당자 입력 신뢰 모델이며, 실제 운영에서는 인증·감사와 일정 원장 연계가 추가로 필요하다.

## 주민 표시 검증

S8의 일정·시끄러운 시간·longest interval·문구·문의처·3단계가 모두 확정 snapshot에서 만들어진다. 실제 E2E에는 `quiet`, `moderate`, `loud` 세 상태가 모두 포함됐다. 11:00~18:00 longest interval은 high-noise 미배정 구간이며, 일반 작업이 포함될 수 있는 `moderate`와 모순되지 않도록 문구를 명시했다.

주민 JSON에서 dB, Noise Impact, 민감도, 수음점, 내부 제약, schedule fingerprint를 검사해 누출이 없음을 확인했다.

## 계약과 회귀

operation 수는 33개로 유지한다. v3.4는 추천 후보 snapshot 필드와 S7 검증 상태만 additive로 확장한다. OpenAPI·TypeScript·27번 실제 예시를 재생성하고 코드 schema와 비교했다. 기존 268개와 신규 조작 차단 테스트 1개를 합쳐 `269 passed`를 확인했다. 최종 ZIP hash는 완료 보고에 기록한다.
