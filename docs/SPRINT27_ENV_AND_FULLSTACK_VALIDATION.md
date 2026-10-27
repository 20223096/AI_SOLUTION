# Sprint 27 환경변수 복구 및 전체 서비스 검증

검증일: 2026-10-27 (Asia/Seoul)

## 외부 API

비밀값은 출력·기록하지 않고 설정 여부와 응답 상태만 확인했다.

| 서비스 | 환경변수 | 실제 결과 |
|---|---|---|
| JUSO 검색 | `JUSO_SEARCH_API_KEY` | 200, 정확 주소 검색 성공 |
| JUSO 좌표 | `JUSO_COORD_API_KEY` | 200, EPSG:5179 및 EPSG:4326 좌표 응답 |
| JUSO 다중 후보 | 위 두 키 | 후보 10개, 명시 선택 후 `user_selected/resolved` |
| 서울 열린데이터광장 | `SEOUL_OPEN_DATA_API_KEY` | 200, `INFO-000` |
| 공공데이터포털 | `DATA_GO_KR_API_KEY` | 200, `00 NORMAL SERVICE` |
| VWorld | `VWORLD_API_KEY` | 200, `OK`, 좌표 응답 |

## 전체 흐름

- Vite `127.0.0.1:5173`과 FastAPI `127.0.0.1:8000` 동시 실행.
- 실제 HTTP 13단계: JUSO `resolved`, 추천 snapshot `verified`, 확정 전 `not_published`, 확정 후 `published`.
- Playwright Chromium: S1 입력부터 S8 공개까지 통과. 모든 관찰 API 응답 200, console error 없음.
- 모바일 iPhone 13 viewport에서 문서 가로 overflow 없음.
- 새로고침하면 담당자 UI workflow state는 S1로 초기화되지만, 서버에서 확정한 주민 공개 snapshot은 유지된다.

## 회귀 및 재현성

- 백엔드 계산·데이터 파일은 기준 `837864c`와 동일하게 유지한다.
- 전체 S-DoT 가공 CSV 대신 시연일 144행의 byte-for-byte 테스트 fixture를 추적해 clean clone에서도 테스트 가능하게 했다.
- 백엔드 269 tests, 프론트 13 unit tests, Chromium E2E 1 test, lint, production build를 검증한다.

## 환경파일 정책

- 서버 전용: `backend/.env`
- 브라우저 공개 설정: `frontend/.env.local`
- 기존 루트 `.env`: 마이그레이션 fallback. 신규 설정에는 사용하지 않는다.
- 실제 `.env*`는 Git에서 제외하고 example 파일만 추적한다.
