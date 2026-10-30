# Render FastAPI 백엔드 배포

기준 브랜치: `deploy/render-fastapi-backend`

이 문서는 `shh-schedule-api`를 Render Python Web Service로 배포하는 절차다. 실제 서비스 생성, Git push, API 키 등록은 이 작업에 포함하지 않는다.

## 1. 저장소 조사 결과

- FastAPI 진입점: `backend/app/main.py`의 `app`
- 의존성: `backend/requirements.txt` (`pip`)
- 배포 Python: `3.13.5` (`render.yaml`의 `PYTHON_VERSION`)
- Health check: `GET /api/health`
- 핵심 시나리오 데이터: `backend/app/data/*.json`
- 추가 공개자료·설계·M1 데이터: 저장소 루트 `data/processed/*`, `data/reports/*`
- 데이터베이스: 없음
- 런타임 쓰기: 주민 안내 초안과 추천 snapshot을 JSON으로 기록
- 외부 통신: OpenAI Chat Completions, JUSO 주소 검색·좌표 API

`public_data.py`, `design_simulation.py`, `m1_acoustics.py`, `receptor_data.py`가 저장소 루트의 `data/processed`를 읽는다. 따라서 Render **Root Directory는 비워 두어 저장소 루트로 유지**해야 한다. `backend`만 Root Directory로 지정하면 일부 공개자료·설계·수음점 API 데이터가 누락된다.

배포에 필요한 추적 데이터는 Git에 포함되어 있다. 현재 크기는 대략 `backend/app/data` 72KB, `data/processed` 28MB, `data/reports` 16KB다. `data/raw` 전체는 필요하지 않으며 추적된 메타데이터만 배포된다.

## 2. Render Dashboard 입력값

저장소 루트의 `render.yaml` Blueprint를 사용하는 것이 권장된다. Dashboard에서 직접 Web Service를 만들 때는 다음 값을 그대로 입력한다.

| Render 항목 | 입력값 |
|---|---|
| Service Type | Web Service |
| Name | `shh-schedule-api` |
| Region | `Singapore` |
| Branch | 배포할 GitHub 브랜치 (`deploy/render-fastapi-backend` 검증 후 팀 정책에 맞는 브랜치) |
| Runtime / Language | Python 3 |
| Root Directory | **비워 둠** |
| Build Command | `pip install -r backend/requirements.txt` |
| Start Command | `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/api/health` |
| Auto-Deploy | 팀 정책에 맞게 선택; 첫 시연은 수동 배포 권장 |
| Compute | 시연은 Free 가능, 지속 저장이 필요하면 유료 인스턴스와 Disk 사용 |

Render는 Web Service가 `0.0.0.0`과 `$PORT`에 바인딩되기를 요구한다. 프로덕션 명령에는 `--reload`를 사용하지 않는다.

공식 참고:

- <https://render.com/docs/deploy-fastapi>
- <https://render.com/docs/python-version>
- <https://render.com/docs/blueprint-spec>
- <https://render.com/docs/regions>

## 3. 환경변수 체크리스트

비밀값은 Render Dashboard의 Environment에 직접 입력한다. `.env`는 Git에 올리지 않는다.

| 변수 | 분류 | Render 값/설명 |
|---|---|---|
| `PYTHON_VERSION` | 필수·배포 시 지정 | `3.13.5` |
| `SHH_EXTRACTOR_MODE` | 필수 | 실제 LLM 시연은 `llm`, 장애 격리/무료 시연은 `mock` |
| `SHH_LLM_PROVIDER` | LLM 모드 필수 | `openai_compatible` |
| `SHH_LLM_MODEL` | LLM 모드 필수 | `gpt-4.1-mini` |
| `SHH_LLM_BASE_URL` | LLM 모드 필수 | 공식 OpenAI는 `https://api.openai.com/v1` |
| `SHH_LLM_API_KEY` | LLM 모드 필수·Secret | OpenAI 프로젝트 키. 브라우저/프론트 변수로 설정 금지 |
| `JUSO_SEARCH_API_KEY` | JUSO 기능 필수·Secret | 도로명주소 검색 승인키 |
| `JUSO_COORD_API_KEY` | JUSO 기능 필수·Secret | 좌표제공 검색 승인키 |
| `SHH_JUSO_TIMEOUT_SECONDS` | 선택 | 기본 `5`; 필요할 때만 변경 |
| `SHH_CORS_ALLOWED_ORIGINS` | 배포 시 필수 | JSON 배열. 예: `["https://frontend.example"]`; 실제 프론트 Origin 확정 후 교체 |
| `SHH_STAFF_API_ALLOWED_HOSTS` | S7 담당자 API 사용 시 필수 | JSON 배열. 아래 접근 제한 주의사항 참고 |
| `SHH_RESIDENT_NOTICE_STORE_PATH` | 배포 시 지정 | `/opt/render/project/src/runtime/resident_notices.json` |
| `SHH_RECOMMENDATION_SNAPSHOT_STORE_PATH` | 배포 시 지정 | `/opt/render/project/src/runtime/recommendation_snapshots.json` |
| `SHH_SLOT_MINUTES` | 선택 | 기본 `15`; 기존 계산 유지 시 생략 |
| `SEOUL_OPEN_DATA_API_KEY` | 로컬 수집 스크립트 전용 | 런타임 API는 이미 처리된 파일을 읽으므로 Render에 불필요 |
| `DATA_GO_KR_API_KEY` | 로컬 수집 스크립트 전용 | Render에 불필요 |
| `VWORLD_API_KEY` | 현재 런타임에 불필요 | Render에 불필요 |

`SHH_CORS_ALLOWED_ORIGINS`는 와일드카드가 아니라 정확한 `scheme://host[:port]`만 넣는다. 여러 프론트가 있으면 JSON 배열에 각각 추가한다. OpenAI와 JUSO 키는 백엔드에만 존재하며 프론트 빌드 변수로 복사하지 않는다.

### S7 담당자 API 접근 제한

`/api/staff/*`는 CORS와 별개로 `request.client.host`가 `SHH_STAFF_API_ALLOWED_HOSTS`에 있어야 한다. 현재는 인증 시스템 없이 담당자 쓰기 API를 공개하지 않기 위한 보호다.

- 시연자의 고정 공인 IP가 FastAPI에 client host로 전달되는 구성이 확인되면 그 IP만 배열에 추가한다.
- Render 프록시 때문에 다른 client host가 보이면 Render 로그/403 응답으로 실제 값을 확인한 뒤 해당 값만 추가한다.
- `*` 허용이나 Origin만으로 담당자 권한을 대체하지 않는다.
- 안정적인 공개 운영에는 별도 인증/권한 설계가 필요하다. 이번 배포 준비에서는 기존 계약을 보존하기 위해 인증을 새로 추가하지 않았다.

## 4. CORS

허용 메서드는 기존 API가 쓰는 `GET`, `POST`, `PUT`, `OPTIONS`다. 자격증명 쿠키는 허용하지 않으며 허용 헤더는 `Accept`, `Content-Type`으로 제한한다.

프론트 URL 확정 후 예:

```text
SHH_CORS_ALLOWED_ORIGINS=["https://shh-schedule.example.com"]
```

로컬 프론트도 동시에 허용해야 하면:

```text
SHH_CORS_ALLOWED_ORIGINS=["https://shh-schedule.example.com","http://localhost:5173","http://127.0.0.1:5173"]
```

## 5. 런타임 저장과 Render 플랜

추천 생성 시 `runtime/recommendation_snapshots.json`, S7/S8 진행 시 `runtime/resident_notices.json`을 쓴다. 디렉터리는 코드가 자동 생성한다.

Render의 기본 파일시스템과 Free Web Service는 ephemeral이므로 재배포·재시작·idle spin-down 후 이 두 파일이 사라진다. 같은 실행 세션의 시연은 가능하지만 S7/S8 확정 상태를 장기 보존하지 못한다.

지속 저장이 필요하면:

1. 유료 Web Service를 선택한다.
2. Persistent Disk를 `/opt/render/project/src/runtime`에 마운트한다.
3. 위 두 store path 환경변수를 그대로 사용한다.

공식 참고: <https://render.com/docs/disks>, <https://render.com/docs/free>

## 6. 보안 및 외부 API 장애

- Health 응답에는 키가 없고 상태·모델 버전·추출 모드만 포함된다.
- OpenAI는 30초 timeout, JUSO는 기본 5초 timeout이며 무제한 재시도 코드는 없다.
- JUSO 장애는 정규화된 502/503 응답으로 처리된다.
- OpenAI 키와 JUSO 키는 서버 요청에서만 사용한다.
- 공개 `/api/notices/extract`는 인증이나 rate limit이 없어 LLM 모드에서 유료 호출 남용 위험이 있다.

기존 API 계약을 깨는 인증/rate-limit을 이번 변경에 임의로 추가하지 않았다. 공개 전 최소 운영 대책은 다음과 같다.

1. OpenAI에서 전용 Project/API key를 사용하고 프로젝트 예산·사용량 알림을 낮게 설정한다.
2. 촬영 외 시간에는 `SHH_EXTRACTOR_MODE=mock`으로 전환하거나 Render 서비스를 중지한다.
3. Render 로그와 OpenAI usage를 시연 중 모니터링한다.
4. 장기 공개 전에는 API gateway/Cloudflare 또는 애플리케이션 인증·rate-limit을 별도 설계한다.

## 7. 로컬 배포 명령 검증

저장소 루트에서 의존성 설치:

```bash
python3 -m venv /tmp/shh-render-venv
/tmp/shh-render-venv/bin/pip install -r backend/requirements.txt
```

Render와 동일한 시작 형태:

```bash
PORT=10000 SHH_EXTRACTOR_MODE=mock \
  sh -c 'cd backend && uvicorn app.main:app --host 0.0.0.0 --port "$PORT"'
```

확인:

```bash
curl http://127.0.0.1:10000/api/health
```

LLM 모드는 `.env` 또는 Render 환경변수의 기존 설정을 사용한다. 배포 검증 중 실제 유료 호출은 반복하지 않는다.

검증 결과:

- 로컬 Python: `3.14.4`; Render는 재현성을 위해 `3.13.5`로 고정
- 새 임시 가상환경에서 `backend/requirements.txt` 전체 설치 성공
- FastAPI import 및 `/api/health` 200 확인
- Render형 `0.0.0.0:10000` 시작 성공
- `backend/app/data` 시나리오와 루트 `data/processed` 공개자료 HTTP 로딩 성공
- mock 백엔드 테스트 276개 통과
- 9/11 `offset-120`, 180분 → 60분 확인
- 10/7 `offset-0`, 0분 → 0분 확인
- S1~S4 mock 통합 테스트 통과
- 허용 Origin의 S7 PUT preflight 및 미허용 Origin 차단 테스트 통과
- 실제 OpenAI 유료 호출은 수행하지 않음

로컬에는 Python 3.13 실행 파일이 없어 `3.13.5` 자체의 로컬 실행은 생략했다. Render 공식 Python 버전 설정을 고정했으며, 최종 확인은 첫 Render build log의 Python 버전과 wheel 설치 결과를 확인한다.

## 8. GitHub push 후 배포

이 작업에서는 push하지 않는다. 검토 후 사용자가 수행할 절차:

```bash
git push -u origin deploy/render-fastapi-backend
```

Blueprint 방식:

1. Render Dashboard → **New +** → **Blueprint**.
2. GitHub의 `20223096/AI_SOLUTION` 저장소 연결.
3. Blueprint branch로 `deploy/render-fastapi-backend` 선택.
4. `render.yaml`을 확인하고 `sync: false` 변수의 실제 값을 입력.
5. `SHH_CORS_ALLOWED_ORIGINS`에 실제 프론트 Origin을 JSON 배열로 입력.
6. 배포 후 `https://<service>.onrender.com/api/health` 확인.
7. `/api/prd/recommendation-diagnostics?analysis_date=2026-09-11`과 `2026-10-07`을 확인.

Dashboard 직접 생성 방식은 2절의 값을 입력하고 같은 환경변수를 등록한다. Root Directory를 `backend`로 설정하지 않는다.
