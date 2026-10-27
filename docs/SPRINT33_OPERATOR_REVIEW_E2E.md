# Sprint 33 담당자 확인 및 S1~S8 완결 검증

## 구현 범위

- S2는 LLM 원문 근거, 정규화 경고, 누락된 작업시간, 장비-작업 연결, 도로굴착 및 도로점용 허가조건을 담당자 검토 대상으로 표시한다.
- 값은 `LLM 추출`, `입력 필요`, `담당자 수정` 상태로 구분한다.
- 복구 작업시간, 작업명, 장비 수량과 작업별 장비, 당일 복구 조건, 허가시간을 화면에서 수정할 수 있다.
- 공식 주소 대표점 확인과 전체 담당자 검토 확인이 끝나지 않으면 S3로 진행할 수 없다.
- 확인 결과는 `user_review_completed`, `user_modified_fields`, `task_duration_by_task`, `task_name_by_task`, `equipment_by_task`로 S3/S4 요청에 전달된다. 기존 필드는 유지하고 필드만 하위 호환 방식으로 추가했다.

## 데이터 출처 구분

- LLM 반환값과 원문 근거는 추출 응답의 `source_evidence`와 evidence 검증 결과로 유지한다.
- 담당자가 확정한 계산 입력은 planning의 confirmed-form provenance로 유지한다.
- 실제로 변경한 필드 경로는 `user_modified_fields`에 별도로 기록한다.
- `user_review_completed=true`는 담당자가 전체 검토 체크박스를 명시적으로 선택한 경우에만 전송한다.
- Structured Outputs는 출력 형식을 보장하지만 내용의 의미적 정확성까지 보장하지 않으므로, 계산 전 사람의 확인을 필수 단계로 둔다.

## 비식별 실제 응답 fixture E2E

`e2e/fixtures/sprint32-llm-extract.json`은 Sprint 32 실제 GPT 응답에서 개인정보와 비밀정보를 제거한 고정 fixture다. 테스트는 `/api/notices/extract`만 이 fixture로 대체하고 S2 이후 planning, 주소·좌표, 일정 검증, CP-SAT 추천, 비교, 안내문 확정 및 주민 공개 API는 실행 중인 백엔드를 사용한다. 추가 OpenAI 호출은 없다.

검증한 흐름:

1. 누락된 포장 복구 duration과 장비 연결 검토 경고 표시
2. 미확인 상태의 S3 진행 차단 및 구체적 수정 위치 안내
3. 담당자가 복구 60분, 포장 파쇄 공정명, 굴착 여부, 허가시간 08:00~17:00을 입력
4. 공식 주소·좌표 및 원문/LLM/수정값 전체 확인
5. S3 일정에 수정 공정명과 작업시간 반영
6. S4 요청 payload에 수정 duration, 공정명, 장비 연결, 수정 필드 목록 반영
7. 후보 선택, 전후 비교, 안내문 저장·확정, S8 공개 완료

Chromium 결과: 기존 mock 흐름과 신규 GPT fixture 흐름 모두 통과(2 tests passed).

## 회귀 결과

- 백엔드: `SHH_EXTRACTOR_MODE=mock python3 -m pytest -q` — 296 passed
- 프론트엔드: `npm test -- --run` — 17 passed
- 빌드: `npm run build` — 성공
- lint: `npm run lint` — 성공
- Chromium E2E: `npx playwright test --workers=1` — 2 passed
- Sprint 29 정량 재실행:
  - 2026-09-11: 기존/개선 Noise Impact 7.36, CP-SAT 후보 495, Pareto 35
  - 2026-10-07: offset 13.72 → 13.20, CP-SAT 13.72 → 13.12, 후보 495, Pareto 18

백엔드 테스트는 개발자 `.env`의 LLM 모드에 의한 외부 호출을 막기 위해 명시적으로 mock 모드에서 실행했다. 제품 환경설정이나 API 키 파일은 변경하지 않았다.

## 한계

- fixture E2E는 과거 실제 GPT 응답을 재현하지만 이번 Sprint에서 GPT를 새로 호출한 검증은 아니다.
- 담당자 확인 주체와 확인 시각을 영구 감사 로그로 저장하는 기능은 없다. 현재는 계산 요청의 확인 여부와 수정 필드만 전달한다.
- 카탈로그에 없는 새 장비는 기존 정책대로 자동 모델 생성 없이 사용자의 수정·선택이 필요하다.
- 고정 construction ID fixture를 같은 영속 테스트 저장소에 반복 생성하면 기존 초안과 충돌할 수 있으므로 E2E는 격리된 임시 저장소에서 실행해야 한다.
