# 쉿간표 프론트엔드 계약 패키지

이 디렉터리는 v3.2의 28개 API를 보존하고 Sprint 24 S7/S8 API 5개를 추가한 총 33개 FastAPI operation의 OpenAPI와 HTTP 응답 예시다. 기준 앱 버전은 `poc-0.1.0`, 검증일은 2026-10-26이다.

Sprint 22 전달 파일은 저장소 루트의 `shh-frontend-api-contract-v3_1.zip`이다. 이전 v3 대비 신규 PRD API 2개, 해당 타입/예시, S1~S4 순차 연동 가이드와 실제 HTTP 재생 결과가 추가됐다. 미구현 S7/S8 API는 포함하지 않는다.

## 구성

- `../docs/openapi.json`: `app.openapi()`가 생성한 OpenAPI 3.1.0 원본
- `types/api.d.ts`: 위 파일에서 `openapi-typescript@7.10.1`로 자동 생성한 타입
- `examples/01-*.json` ~ `27-*.json`: 등록된 27개 API의 성공 요청/응답 전문
- `examples/error-*.json`: 실제 재현한 404, 415, 422 응답
- `examples/manifest.json`: 성공 검증 목록
- `examples/generate_examples.py`: 실행 중인 로컬 서버에 대해 예시를 재생성하는 스크립트
- `examples/verify_prd_s1_s4_workflow.py`: S1~S4 순차 HTTP 재생 스크립트
- `examples/prd-s1-s4-workflow.json`: 사용자 확인·부분 feasible·단일 추천·비교까지의 실제 응답
- `examples/s2-address-coordinate.json`: 승인된 JUSO API의 S2 실제 주소 좌표 응답
- `examples/s7-s8-resident-notice-workflow.json`: 초안 생성·조회·수정·비공개 조회·확정·공개 조회 E2E 전문
- `examples/generate_s7_s8_example.py`: 위 E2E 전문 재생성 스크립트
- `../docs/FRONTEND_API_CONTRACT_v2_1.md`: 기존 계약서(보존)
- `../docs/FRONTEND_API_CONTRACT_v3_1.md`: Sprint 21 신규 API까지 실제 검증한 확정 계약서
- `../docs/FRONTEND_API_CONTRACT_v3_2.md`: Sprint 23 주소 좌표 확장 계약서
- `../docs/FRONTEND_API_CONTRACT_v3_3.md`: Sprint 24 S7/S8 확장 계약서
- `../docs/PRD_FRONTEND_INTEGRATION_GUIDE.md`: 화면 상태와 필드 전달 규칙

## 로컬 실행 및 재검증

```bash
cd backend
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

다른 터미널에서:

```bash
python3 frontend-contract/examples/generate_examples.py
python3 frontend-contract/examples/verify_prd_s1_s4_workflow.py
npx --yes openapi-typescript@7.10.1 docs/openapi.json -o frontend-contract/types/api.d.ts
```

다른 주소를 쓸 때는 예시 생성기에만 `SHH_API_BASE_URL`을 지정한다.

```bash
SHH_API_BASE_URL=http://127.0.0.1:8000 python3 frontend-contract/examples/generate_examples.py
```

## 프론트엔드 환경변수

프론트엔드가 설정할 값은 배포 방식에 따른 API origin 하나뿐이다. 예: Vite는 `VITE_SHH_API_BASE_URL=http://127.0.0.1:8000`. 이 이름은 백엔드가 읽는 변수가 아니라 프론트엔드 측 관례이므로 필요에 맞게 바꿀 수 있다.

현재 백엔드는 인증 토큰을 요구하지 않는다. 개발 CORS 기본 origin은 `http://localhost:5173`, `http://127.0.0.1:5173`이다. 운영에서는 백엔드 환경변수에 JSON 배열을 설정한다.

```env
SHH_CORS_ALLOWED_ORIGINS=["https://shh.example.com"]
```

## 타입 사용

```ts
import type { components, paths } from "./types/api";

type PredictRequest = components["schemas"]["PredictRequest"];
type PredictResponse = components["schemas"]["NoisePredictResponse"];
type PredictOperation = paths["/api/noise/predict"]["post"];
```

33개 API의 성공 응답은 모두 명시적 스키마로 생성된다. 최적화처럼 성공 분기가 둘인 응답은 TypeScript union으로 생성된다.

## PRD v2.1 전용 API

```text
GET  /api/prd/demo/2026-09-11
POST /api/prd/schedules/validate
GET  /api/prd/recommendation-diagnostics?analysis_date=2026-09-11
POST /api/prd/sensitivity/experiment
POST /api/prd/planning/from-notice
POST /api/prd/recommendations/constraint-filtered
```

추천 진단은 `analysis_date`로 `2026-09-11` 또는 `2026-10-07`만 받는다. 9/11에는 날짜 한정 가정 혼잡 오버레이가 있는 `final-demo-congestion`, 10/7에는 그 오버레이를 제외한 `official_reference_equipment`를 사용한다. S-DoT는 화면의 관측·품질 맥락이며 음향 합성 입력이 아니다.

현재 API로 시나리오 목록·상세, M0 소음 그래프, 최적화, 전후 비교, 공식자료/설계 시뮬레이션, M1 분석 화면을 구현할 수 있다. 주민 안내문 생성, 주민 전용 조회, 자연어 조건 수정, 법적 위반 판정 API는 존재하지 않는다. PoC 시나리오와 `/api/public-data/construction-design`의 공식 설계자료를 같은 데이터로 취급하지 않는다.

## 최소 fetch 예시

```ts
import type { components } from "./types/api";

type OptimizeRequest = components["schemas"]["OptimizeRequest"];
type OptimizeResponse = components["schemas"]["OptimizeSuccessResponse"] | components["schemas"]["OptimizeInfeasibleResponse"];

const API_BASE_URL = import.meta.env.VITE_SHH_API_BASE_URL;

export async function optimizeSchedule(body: OptimizeRequest): Promise<OptimizeResponse> {
  const response = await fetch(`${API_BASE_URL}/api/schedules/optimize`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(`API ${response.status}: ${JSON.stringify(payload)}`);
  return payload as OptimizeResponse;
}
```
