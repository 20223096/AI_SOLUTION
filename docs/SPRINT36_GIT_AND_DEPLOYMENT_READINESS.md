# Sprint 36 Git 통합·배포 준비 보고서

검사 기준 브랜치: `integration/frontend-backend-s1-s8`

작업 시작 기준 커밋: `39786df49bafac5084dbc4fc33af53cc40653e22`

## Git 및 비밀값

- 작업 시작 시 브랜치는 지정 기준 커밋과 정확히 일치했고 기존 작업 트리는 깨끗했다.
- 로컬 `main`은 `93d461302d3f4ad759993b99ba1c17eca7a39221`이며 `git merge-base main HEAD`도 동일하다. 따라서 통합 브랜치는 로컬 `main`을 포함한다.
- `git ls-files -s`와 `git ls-tree HEAD AI_SOLUTION`에서 mode `160000` 항목이 없다. 과거 병합 부모 `1c279f8`에 추가됐던 `AI_SOLUTION` gitlink는 최종 통합 tree에 남아 있지 않다.
- 현재 추적 파일에는 실제 `.env`, 개인키(`*.pem`, `*.key`, `id_rsa`)가 없다. 추적 대상은 `backend/.env.example`, `frontend/.env.example`뿐이다. 과거 병합 부모 `1c279f8`의 루트 `.env`는 공개 frontend base URL 한 항목이었고 최종 통합 tree에서는 제외됐다. 비밀키 파일은 아니지만 운영 키를 같은 방식으로 커밋해서는 안 된다.
- `.gitignore`는 `.env`, `.env.*`, `*.local`, runtime/test 결과를 제외하며 두 예제 env만 명시적으로 허용한다.
- push, PR 생성, `main` 병합은 수행하지 않았다.

## 배포 차단 사항

staff API에는 운영 사용자 인증, 권한 관리(RBAC), 행위자 기반 감사가 없다. 현재 host/loopback 제한은 인증을 대체하지 않으므로 이 상태로 인터넷에 공개 배포해서는 안 된다. 인증·권한·운영 영속 DB·secrets manager·감사 로그를 갖추기 전까지 발표용 격리 mock 환경으로만 사용한다.

## 검증 결과

| 검사 | 결과 |
|---|---|
| 백엔드 | `SHH_EXTRACTOR_MODE=mock python3 -m pytest -q` → 296 passed |
| 프론트 단위 | `npm test` → 20 passed (기존 18 + 비교 UI 2) |
| Chromium E2E | `npm run test:e2e` → 3 passed (기존 2 + 비교 UI 1) |
| 빌드 | `npm run build` 성공 |
| 정적 검사 | `npm run lint` 성공 |
| 스크린샷 | 데스크톱·iPhone 13 확인, 모바일 가로 overflow 없음 |

새 clone을 `/tmp`에 만들고 lockfile 기반 `npm ci`, 프론트 20 tests, production build를 재실행해 모두 성공했다. 별도 Python venv에서도 `pip install -r backend/requirements.txt` 후 백엔드 296 tests가 통과했다. 설치 검증에는 패키지 다운로드 네트워크가 필요하다.

셸에 `SHH_EXTRACTOR_MODE=llm`이 남아 있으면 mock 계약 테스트가 503으로 실패한다. 새 clone 및 CI에서는 위와 같이 mock 모드를 명시해야 한다.

## 변경 보호

기존 CP-SAT 최적화 구현과 데이터셋은 변경하지 않았다. 변경 범위는 실험 결과의 provenance 메타데이터, 생성된 발표 JSON, 읽기 전용 UI·테스트·문서다. 기존 S1~S8 분석일과 snapshot 저장소도 변경하지 않았다.
