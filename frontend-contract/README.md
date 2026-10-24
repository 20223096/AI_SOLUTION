# 쉿간표 프론트엔드 계약 패키지

이 디렉터리는 백엔드 소스 변경 없이 FastAPI 앱의 실제 OpenAPI와 로컬 HTTP 응답을 캡처한 결과다. 기준 앱 버전은 `poc-0.1.0`, 검증일은 2026-10-24이다.

## 구성

- `../docs/openapi.json`: `app.openapi()`가 생성한 OpenAPI 3.1.0 원본
- `types/api.d.ts`: 위 파일에서 `openapi-typescript@7.10.1`로 자동 생성한 타입
- `examples/01-*.json` ~ `21-*.json`: 등록된 21개 API의 성공 요청/응답 전문
- `examples/error-*.json`: 실제 재현한 404, 415, 422 응답
- `examples/manifest.json`: 성공 검증 목록
- `examples/generate_examples.py`: 실행 중인 로컬 서버에 대해 예시를 재생성하는 스크립트
- `../docs/FRONTEND_API_CONTRACT_v1.md`: 프론트엔드용 확정 계약서

## 로컬 실행 및 재검증

```bash
cd backend
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

다른 터미널에서:

```bash
python3 frontend-contract/examples/generate_examples.py
npx --yes openapi-typescript@7.10.1 docs/openapi.json -o frontend-contract/types/api.d.ts
```

다른 주소를 쓸 때는 예시 생성기에만 `SHH_API_BASE_URL`을 지정한다.

```bash
SHH_API_BASE_URL=http://127.0.0.1:8000 python3 frontend-contract/examples/generate_examples.py
```

## 프론트엔드 환경변수

프론트엔드가 설정할 값은 배포 방식에 따른 API origin 하나뿐이다. 예: Vite는 `VITE_SHH_API_BASE_URL=http://127.0.0.1:8000`. 이 이름은 백엔드가 읽는 변수가 아니라 프론트엔드 측 관례이므로 필요에 맞게 바꿀 수 있다.

현재 백엔드는 인증 토큰을 요구하지 않는다. 또한 CORS 미들웨어가 없으므로 브라우저 앱과 API의 origin이 다르면 reverse proxy를 사용하거나, 백엔드에 별도 CORS 변경이 이루어지기 전에는 브라우저 직접 호출이 차단된다.

## 타입 사용

```ts
import type { components, paths } from "./types/api";

type PredictRequest = components["schemas"]["PredictRequest"];
type PredictOperation = paths["/api/noise/predict"]["post"];
```

주의: 현재 FastAPI 라우트에 `response_model`이 선언되지 않아 OpenAPI의 성공 응답 스키마는 빈 스키마 `{}`이고 생성 타입도 응답을 `unknown`으로 취급한다. 실제 응답 예시는 검증된 관찰값이지만 정적 응답 계약은 아니다. 프론트엔드에서 임의의 강한 응답 타입을 만들기보다 런타임 검증을 하거나 백엔드에 명시적 response model이 도입된 뒤 타입을 재생성해야 한다.

## 최소 fetch 예시

```ts
import type { components } from "./types/api";

type OptimizeRequest = components["schemas"]["OptimizeRequest"];

const API_BASE_URL = import.meta.env.VITE_SHH_API_BASE_URL;

export async function optimizeSchedule(body: OptimizeRequest): Promise<unknown> {
  const response = await fetch(`${API_BASE_URL}/api/schedules/optimize`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  const payload: unknown = await response.json();
  if (!response.ok) throw new Error(`API ${response.status}: ${JSON.stringify(payload)}`);
  return payload;
}
```
