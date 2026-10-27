# Sprint 26 프론트엔드·백엔드 통합 기록

검증일: 2026-10-27 (Asia/Seoul)

## 기준과 계보

- `origin/main`: `8d661866dec7432595b8a3705ddeebdabf109d8e`
- `origin/backend-process`: `837864c2d34458c99c8b4d225d42c63f15f041e7`
- `origin/feat/frontend-s1-s8`: `1c279f8f955ea6469405e61f81bdc6708f9750d6`
- 프론트 브랜치는 부모가 없는 root commit이며 백엔드와 merge-base가 없다.
- 통합 브랜치 `integration/frontend-backend-s1-s8`은 `837864c`에서 생성하고 `--allow-unrelated-histories --no-commit`으로 검토 후 수동 통합했다.

## 충돌과 보존 결정

동일 경로 57개 중 내용이 다른 파일은 `.env.example`, `.gitignore`, `README.md` 3개였다. 계약 문서와 `frontend-contract` 54개는 blob이 동일했다.

- `.env.example`: 백엔드/JUSO/CORS와 프론트 API origin 예시를 합쳤다.
- `.gitignore`: Python, 데이터, Node/Vite, IDE 규칙을 합쳤다.
- `README.md`: 양쪽 실행법과 S7/S8 제한을 합쳤다.
- 프론트가 추적한 `.env`는 커밋에서 제외했다. merge checkout 과정에서 기존 ignore된 로컬 `.env`가 프론트 localhost 값으로 덮여 JUSO 키가 사라진 것으로 확인됐다. 저장소 내 백업은 발견하지 못했다.
- 프론트 root commit에 있던 `AI_SOLUTION` gitlink(`8d66186`)는 현재 저장소를 다시 가리키는 중첩 항목이라 제외했다.
- 백엔드 계산·데이터·테스트 226개와 프론트 소스/목업을 보존했다.

## 통합 구조

```text
backend/             FastAPI 앱, 계산/데이터 서비스, 269 tests
data/                원천·가공·검증 데이터
docs/                API v3.4, 결과, Sprint 26 보고서
frontend-contract/   OpenAPI 생성 타입·예제·HTTP 재생기
scripts/             백엔드 데이터 처리 도구
src/
  api/               v3.4 HTTP client, 좌표, S7/S8, 계약 타입
  components/        공통 React UI
  screens/           S1~S8 화면 및 workflow tests
public/              Vite 정적 자산
```

## 검증 결과

- 백엔드: `JUSO_SEARCH_API_KEY=test-search JUSO_COORD_API_KEY=test-coord python3 -m pytest -q` → **269 passed**.
- 프론트: `npm test` → **2 files, 13 tests passed**.
- 정적 검사: `npm run lint` 성공.
- 프로덕션 빌드: `npm run build` 성공(Vite 8.3.5, 51 modules).
- 실제 HTTP: FastAPI `127.0.0.1:8765`와 Vite `127.0.0.1:5173`을 동시에 실행하고 Vite `/api` 프록시를 통해 13단계 S1~S8을 재생했다. snapshot은 `verified`, 확정 전 S8은 `not_published`, 확정 후 `published`였다.
- JUSO 실제 조회: 유효 키 소실로 `503 provider_auth_error (E0001)`. 좌표 성공 E2E는 미통과이며 mock 기반 다중 후보/실패/변환 회귀 테스트만 통과했다.
- 실제 브라우저 자동화: 수행하지 못했다. HTTP, React build, API unit test까지만 검증했다.

## 데이터 불변 확인

- 2026-09-11 원 일정 회귀 테스트 유지.
- 2026-10-07 Impact `13.72 → 13.20` 유지.
- 민감 수음점 노출 `1,620 receptor-minutes` 유지.
- 이는 모델 점수 trade-off이며 실제 주민 피해 감소 입증이 아니다.
- 공식 주소 점은 도로명주소 건물 출입구 대표점이며 공사 선형·공사 중심·외벽 수음점이 아니다.

## 동시 실행

```bash
cd backend
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

다른 터미널에서:

```bash
VITE_SHH_API_BASE_URL=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1 --port 5173
```

운영 origin은 `SHH_CORS_ALLOWED_ORIGINS`에 명시해야 한다. staff API는 기본 loopback host 제한만 있고 사용자 인증은 없으므로 인터넷에 직접 공개하면 안 된다.
