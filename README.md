# 쉿간표 (Shh Schedule) PoC

구청 담당자가 신규 공사 작업을 15분 슬롯으로 검토하고, 예상 소음·민감도·일정 변경비용을 함께 비교하는 **행정 참고용** FastAPI PoC입니다. 법적 허가, 소음 준수 인증 또는 실제 피해 감소의 증명이 아닙니다.

## 백엔드 실행

Python 3.11 이상에서:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Swagger: `http://127.0.0.1:8000/docs`, 상태 확인: `GET /api/health`.

```bash
cd backend
pytest -q
```

기본 `SHH_EXTRACTOR_MODE=mock`입니다. `backend/.env.example`을 `backend/.env`로 복사해 서버 전용 키와 설정을 넣습니다. `llm` 모드는 제공업체별 전송 구현과 키를 요구하며 설정 불완전 시 명시적으로 실패합니다.

## 설계 요약

- `app/models`: Pydantic v2 입력·출력 도메인
- `app/services`: 음향, 민감도, 점수, 최적화, Pareto, 비교, 추출
- `app/api`: FastAPI 라우터
- `app/data`: 출처 상태가 포함된 JSON 설정·시나리오
- `tests`: 손계산, 물리식, 제약, API 회귀 테스트

개발용 후보 진단은 `GET /api/schedules/optimize/{scenario_id}/diagnostics`에서 확인합니다. 기본 CASE A와 별도로 소음 집중, 시험기간, 제약 강화 실험 시나리오가 제공됩니다.

## 배경소음 ETL

원본 경로를 유지한 기본 실행:

```bash
python scripts/noise_etl.py
```

다른 경로는 `--raw-root`, `--processed-root`, `--backend-catalog`으로 지정합니다. 원본 CSV는 CP949 스트리밍 방식이며 ZIP에서는 신촌 시트만 읽습니다. 생성 CSV는 Git에서 제외됩니다. `GET /api/noise/background-profiles`로 프로파일을 조회하고 predict/optimize 요청의 `background_profile`로 명시 선택합니다. 기본값은 기존 `assumed_demo`입니다.

작은 시나리오에는 모든 15분 시작 오프셋을 정확 평가합니다. `requirements.txt`에 OR-Tools가 포함되어 있으나 현재 PoC 실행 경로는 재현성과 설명 가능성을 위해 정확 열거를 사용합니다.

## 프론트엔드 실행

```bash
npm install
npm run dev      # http://localhost:5173 (/api 요청은 백엔드로 프록시)
npm run build
```

백엔드는 별도로 `cd backend && python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000`으로 실행합니다.

## 환경변수

`frontend/.env.local`

```env
VITE_SHH_API_BASE_URL=http://127.0.0.1:8000
```

- **개발(`npm run dev`)**: 브라우저는 `/api/...`(같은 origin)로 요청하고, `vite.config.ts` 프록시가 위 주소로 전달합니다. CORS 설정이 필요 없습니다.
- **빌드(`npm run build`)**: 결과물이 위 주소로 직접 요청하므로 백엔드 `SHH_CORS_ALLOWED_ORIGINS`에 배포 origin을 추가해야 합니다.
- 주소를 바꾼 뒤에는 개발 서버를 재시작하세요.

## 구조

```text
src/
  api/
    client.ts          # base URL, fetch 래퍼, ApiError(404/415/422 안내 문구)
    notices.ts         # S1: /api/notices/extract, /api/notices/extract-file
    planning.ts        # S2: /api/prd/planning/from-notice, ConfirmedPlan 타입
    schedules.ts       # S3: /api/prd/schedules/validate, ANALYSIS_DATE
    recommendations.ts # S4~S6: 제약 필터 추천, /api/schedules/compare, 선택 가능 판정
    types/api.d.ts     # 계약 패키지의 openapi-typescript 생성 타입(수정 금지)
  components/          # AppHeader, ProvenanceBadge, Missing, CandidateBadge, ScheduleTimeline(목업 타임라인)
  utils/               # time(시각 변환), async(요청 상태·오류 문구)
  screens/
    S1NoticeInput.tsx       # S1 공고문 올리기
    S2ExtractionReview.tsx  # S2 추출 확인 (초안 → 사용자 확인 폼)
    s2Form.ts               # 초안↔폼 변환, 필수값 검사, 확정 계획(ConfirmedPlan) 생성
    S3ConstraintCheck.tsx   # S3 제약 확인 (원 일정 편집·검증·위반 사유)
    s3Schedule.ts           # 원 일정 생성, 위반 코드 안내 문구
    S4Recommendation.tsx    # S4 후보 추천 (후보별 판정 표)
    s4Display.ts            # 후보 라벨, 지표 정의(좋아지는 방향), 유의사항 번역
    S5CandidatePicker.tsx   # S5 조정안 고르기 (변경량×추가 소음 영향 산점도, 추천 후보 카드)
    S6Comparison.tsx        # S6 조정 전후 비교 (타임라인, 핵심 지표, 전체 지표)
    S7NoticeDraft.tsx       # S7 일정 확정 + 주민 안내문 초안(홈페이지/문자/게시판)
    s7Notice.ts             # 안내문 템플릿: 확정 정보만 사용
    S8ResidentView.tsx      # S8 주민 화면 (공사 일정, 가장 긴 조용한 시간)
    s8Quiet.ts              # 작업 허용시간 안의 빈 구간 계산
  index.css            # 목업의 디자인 토큰(라이트/다크)
```

## 진행 상황

| 화면 | API | 상태 |
|---|---|---|
| S1 공고문 올리기 | `POST /api/notices/extract`, `POST /api/notices/extract-file` | 완료 |
| S2 추출 확인·주소 좌표 | `POST /api/prd/planning/from-notice`, `POST /api/locations/address-coordinate` | 완료 |
| S3 제약 확인 | `POST /api/prd/schedules/validate` (분석일 2026-09-11 고정) | 완료 |
| S4 후보 추천 | `POST /api/prd/recommendations/constraint-filtered` | 완료 |
| S5 조정안 고르기 | (S4 응답 사용) | 완료 |
| S6 조정 전후 비교 | `POST /api/schedules/compare` | 완료 |
| S7 확정·주민 안내 | staff draft POST/PUT/confirm | 완료 |
| S8 주민 화면 | `GET /api/public/construction/{project_id}/resident-notice` | 완료 |

S7은 추천 snapshot ID·schedule version·revision을 서버에서 검증하고 명시적으로 확정합니다. S8은 staff 초안이나 브라우저 상태를 재사용하지 않고 공개 API를 다시 조회합니다. 다만 staff API의 loopback/host 제한은 운영 인증을 대체하지 않으므로 인터넷에 직접 공개하면 안 됩니다.

## 환경변수 분리

- 백엔드 비밀값: `backend/.env` (Git 제외)
- 프론트 공개 설정: `frontend/.env.local` (Git 제외, `VITE_SHH_API_BASE_URL`만 허용)
- 기존 루트 `.env`는 Sprint 27 마이그레이션 호환용 fallback이며 새 설정에는 사용하지 않습니다.
- 실제 API 키를 `VITE_` 변수에 넣으면 브라우저 번들에 노출되므로 금지합니다.
