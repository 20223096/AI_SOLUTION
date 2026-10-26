# 쉿간표 프론트엔드

Vite + React + TypeScript. 화면 디자인은 `전체서비스화면.html` 목업, API는 `shh-frontend-api-contract-v3_1` 계약 기준.

## 실행

```bash
npm install
npm run dev      # http://localhost:5173 (/api 요청은 백엔드로 프록시)
npm run build
```

백엔드는 별도로 `python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.

## 환경변수

`.env`

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
| S2 추출 확인 | `POST /api/prd/planning/from-notice` | 완료 |
| S3 제약 확인 | `POST /api/prd/schedules/validate` (분석일 2026-09-11 고정) | 완료 |
| S4 후보 추천 | `POST /api/prd/recommendations/constraint-filtered` | 완료 |
| S5 조정안 고르기 | (S4 응답 사용) | 완료 |
| S6 조정 전후 비교 | `POST /api/schedules/compare` | 완료 |
| S7 확정·주민 안내 | 없음 — 계약에 안내문 API 없음, 클라이언트 템플릿 | 초안 생성까지 |
| S8 주민 화면 | 없음 — 계약에 주민 조회 API 없음, 확정 일정으로 계산 | 미리보기 |

S7 확정 상태와 안내문은 브라우저 메모리에만 있으며 새로고침하면 사라집니다. 승인·게시·주민 공개 기능은 없습니다.
