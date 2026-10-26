# 쉿간표 PRD v2.1 백엔드 갭 보고서

기준 커밋: `8fd07f1`  
감사일: 2026-10-24  
대상: FastAPI 21개 API, 요청/응답 모델, 계산·최적화 서비스, 데이터 파일, 212개 자동화 테스트

## 1. 감사 범위와 출처 제한

저장소와 현재 대화에 연결된 첨부를 검색했으나 F1~F12 및 S1~S8의 원문 제목·수용 기준이 포함된 PRD v2.1 파일은 제공되지 않았다. 따라서 이 보고서는 이번 18차 요청에 명시된 기능 항목을 순서대로 F1~F12의 감사 축으로 매핑한다. 이는 원문 기능명을 복원하거나 추측한 것이 아니다. 기획팀이 원문을 제공하면 식별자/명칭을 재대조해야 하며, 아래 구현 판정은 코드 사실에 대해서는 확정적이다.

판정 기준:

- `implemented`: 현재 공개 API와 테스트로 핵심 흐름을 완료할 수 있음.
- `partially_implemented`: 일부 데이터/분기/API는 있으나 PRD에 언급된 입력 또는 사용자 흐름 전체를 충족하지 못함.
- `not_implemented`: 해당 출력이나 사용자 동작을 제공하는 공개 API/서비스가 없음.

## 2. F1~F12 대조 결과

| ID | 18차 요청 기반 기능축 | 판정 | 실제 구현 근거 | 부족한 부분 |
|---|---|---|---|---|
| F1 | 신고자료 등록·텍스트/PDF 추출 | `partially_implemented` | `POST /api/notices/extract`, `/extract-file`; `api/notices.py`; `services/extractor.py`; `test_api.py` | 영구 저장/수정 없음. mock은 정해진 4개 작업만 탐지. PDF는 텍스트 추출형만 지원. LLM은 외부 설정 필요 |
| F2 | 장비·규격·대수·공사시간·특정장비시간·도로점용·조정불가 조건 구조화 | `partially_implemented` | `ConstructionNotice`, `ConstructionTask`, `Equipment`; 시나리오의 `count`, `duration_minutes`, `permitted_time_windows`, `constraints`; `domain.py`, `poc_scenario.json` | ExtractRequest는 자유 텍스트뿐이며 mock 추출은 규격/최대대수/특정장비 시간/도로점용시간/조정불가 조건을 만들지 않음. `fixed_schedule`은 최적화가 읽지만 추출 API가 생성하지 않음 |
| F3 | M0/M1 소음 예측 | `implemented` | `/api/noise/predict`, `/predict-m1`, `/compare-m0-m1`; `prediction.py`, `m1_acoustics.py`; M1 물리·시간 테스트 | 공식 현장 M1은 geometry/활동/측정조건 결손 시 deferred. 이는 의도된 계약 |
| F4 | 민감도 및 주거·학교·병원·대학 수음점 | `partially_implemented` | `Receptor.type` enum; `sensitivity.py`; scenario/public receptor 데이터; `test_core.py`, `test_public_data.py` | 타입은 모두 지원하지만 case-a에는 병원 없음. 일부 실제 시설은 다른 시나리오/카탈로그에 존재. 주거 외벽 실측점은 미검증. 가중치는 가정값 |
| F5 | 기존 공사·행사·수거 일정 결합/노출 | `partially_implemented` | M0 `calendar_overlaps`, `existing_event_ids`, `source_metadata.existing_events`; `/api/public-data/catalog`; `prediction.py` | 전용 통합 캘린더 API/CRUD 없음. 소음값 없는 일정은 음향 합산에서 제외. 현재 이벤트 일부는 assumed |
| F6 | Noise Impact Score | `implemented` | `/api/impact/calculate`; `impact.py`; M0 슬롯·일정 metrics에 사용; `test_incremental.py`, `test_scoring_validation.py` | 실험 지수이며 법정 기준/피해 확률이 아님 |
| F7 | 작업시간 제약 및 일정 최적화 | `partially_implemented` | `/api/schedules/optimize`; `optimizer.py`; 순차, 일일 제한, 허용창, fixed schedule, forbidden windows, 선후행/공유자원 확인 | 15분 offset 0~120의 정확 열거만 수행. 장비별 08~17 규칙과 도로점용시간을 일반 정책으로 자동 적용하지 않음. 다일 계획 없음 |
| F8 | Pareto 후보와 추천안 | `implemented` | optimize의 `pareto_candidates`, `recommended_options`, 진단; `pareto.py`; `test_noise_objectives.py` | 항상 3개를 보장하지 않음. 동일 후보 label은 합쳐지며 실제 비지배 후보만 반환 |
| F9 | 원본/추천 일정 비교 | `implemented` | `/api/schedules/compare`; `metrics.py`; `CompareResponse`; 실제 17번 예시 | 비교는 호출자가 제공한 before/after에 대해 수행하며 저장된 승인 이력은 없음 |
| F10 | 주민 안내문 생성 | `not_implemented` | 해당 route/model/service 없음 | 문안 템플릿, 입력 provenance, 승인/배포 상태 정의 필요 |
| F11 | 주민용 화면 조회 | `not_implemented` | 주민 전용 공개 route/auth/view model 없음 | 공개 범위, 개인정보·위치 정밀도, 설명문구, 캐시/배포 정책 필요 |
| F12 | 자연어 조건 수정 | `not_implemented` | notice 추출은 신규 문서 구조화일 뿐 기존 시나리오 제약 patch가 아님 | 대상 시나리오, 허용 명령, diff/확인/감사로그, 재최적화 트랜잭션 필요 |

집계: `implemented` 4개(F3, F6, F8, F9), `partially_implemented` 5개(F1, F2, F4, F5, F7), `not_implemented` 3개(F10~F12).

법적 규제기준 자동 판정은 별도 요구축으로 감사했으며 `not_implemented`다. M0 응답의 `legal_assessment`는 항상 null이고 disclaimer가 법적 측정·평가/적합 판정이 아님을 명시한다. `noise_limit_profile`은 도메인 필드일 뿐 법적 판정 엔진이 아니다.

## 3. S1~S8 화면 연결성

PRD 원문 화면명이 없으므로 아래는 현재 API로 검증 가능한 화면 능력의 S1~S8 운영 매핑이다. 기획 원문의 식별자와 동일하다고 주장하지 않는다.

| 화면 능력 | 가능성 | API/필드 | 제한 |
|---|---|---|---|
| S1 공사·시나리오 목록 | 바로 개발 가능 | `GET /api/poc/scenarios`: `id`, `title`, `expected_feasibility` | PoC 시나리오 목록이며 공식 공사 DB 목록이 아님 |
| S2 신고자료 업로드/추출 | 제한적 개발 가능 | `POST /api/notices/extract`, `/extract-file`: `notice`, `field_evidence`, `warnings` | 저장/편집/규격·복합제약 추출 없음; mock 라벨 필수 |
| S3 공사 상세 | 바로 개발 가능 | `GET /api/poc/scenarios/{id}`: `notice`, `equipment`, `receptors`, provenance | PoC scenario와 공식 설계자료를 동일 엔터티로 합치면 안 됨 |
| S4 소음 그래프·영향 | 바로 개발 가능 | M0 `predictions[]`, background, total, contribution, impact, source metadata | null은 0이 아님; 법적 판정 금지 |
| S5 작업시간 추천 | 바로 개발 가능 | optimize의 candidates, Pareto, recommended options, reasons | 추천 3개 고정 UI 금지 |
| S6 전후 비교 | 바로 개발 가능 | compare의 `before`, `after`, `delta`, schedule change details | 지표마다 개선 방향이 다름 |
| S7 공식자료·설계/M1 분석 | 바로 개발 가능(상태 표시 필수) | public-data, construction-design, design simulation, M1 APIs | 공식 prediction은 deferred; simulation은 가정값 |
| S8 주민 안내/주민 공개/자연어 수정 | 개발 불가 | 대응 API 없음 | 신규 계약과 기획 결정 필요 |

## 4. 계산 로직 정합성 감사

### 4.1 장비 Lw 선택

M0 `source_noise()`의 우선순위는 검증된 동일 모델 → 검증된 동일 category → 시나리오 명시값 → missing이다(`services/acoustics.py:26-38`). 중앙값 또는 상위 10%를 계산하지 않는다.

M1 `resolve_official_lw()`는 동일 모델 정확 일치 또는 사용자가 `low|median|high` reference scenario를 명시한 경우 정렬된 공식 category 분포의 최저/중앙 인덱스/최고값을 사용한다(`m1_acoustics.py:55-92`). `high`는 최댓값이며 상위 10% 분위수가 아니다. 장비 class 대체 금지 목록도 있다.

판정: PRD의 “중앙값/상위 10%”와 현재 M1의 `median/high(max)`는 동일하지 않다. 승인 없이 변경하면 기존 결과와 계약이 깨진다.

### 4.2 거리감쇠와 에너지 합산

M0/M1 공통 point-source 식은 다음이다.

```text
Lp = Lw - 10 log10(4πr²) + C
```

구현: `services/acoustics.py:5-9`. M1은 같은 식을 사용하되 3D 거리, CRS 검증, explicit propagation correction을 추가한다. `EPSG:4326`은 구면 거리 후 높이를 합성하고, `EPSG:5179/5186`은 평면거리와 높이를 합성한다(`m1_acoustics.py:37-52`). 보정은 제공되지 않으면 0으로 몰래 간주하는 대신 `not_modelled/value_db:null`로 반환한다.

장비, 배경, 기존 이벤트는 dB 산술합이 아니라 `10 log10(Σ10^(L/10))` 에너지 합산이다(`acoustics.py:12-16`, `prediction.py:93-97`). PRD 거리식이 단순 `Lw - 20log10(r) - 8` 등 다른 형태라면 상수·방사조건이 달라 동일 모델로 취급할 수 없다.

### 4.3 Noise Impact Score

현재 `legacy_v1`은 0~1로 clipping한 다섯 component의 가중합 ×100이다.

| component | 정규화 | weight |
|---|---|---:|
| level | `(total-threshold+10)/30`, [0,1] clipping | 0.45 |
| duration | `minutes/480`, [0,1] | 0.20 |
| continuous | `minutes/180`, [0,1] | 0.15 |
| sensitivity | `((weight-1)/1.5) × level_component`, [0,1] | 0.15 |
| cumulative | `burden/100`, [0,1] | 0.05 |

구현: `services/impact.py:4-27`. threshold 기본은 65 dB다. 물리 에너지, 법정 초과 확률 또는 피해율이 아니며 포화로 인해 물리 증가가 있어도 incremental score가 0일 수 있다.

### 4.4 민감도 수치와 중복 규칙

- 22:00~05:00: 2.0
- 05:00~07:00 및 18:00~22:00: 1.5
- 07:00~18:00: 1.0
- 대학 시험기간: +0.5
- 주거 주말휴식: +0.3
- 병원/학교: +0.5

구현은 `base + sum(adjustments)`다(`sensitivity.py:4-23`). 즉 PRD가 “중복 시 최댓값 하나”를 요구한다면 현재 구현과 다르다. 단, 여러 수음점을 하나의 슬롯 metrics로 축약할 때는 수음점별 weight 중 최댓값을 취한다(`metrics.py:11-18`). “상황 adjustment 중복”의 합산과 “수음점 집계”의 최댓값을 혼동하면 안 된다.

모든 가중치는 `assumed`이며 법정/연구 검증값이 아니다(`data/sensitivity_config.json`).

### 4.5 시간·제약·solver

- 기본 case-a는 07:00~18:00, 알려진 작업 540분, 순차 시연 가정이다.
- optimizer는 0~120분을 15분 간격으로 열거하여 9개 후보를 만든다(`optimizer.py:114-124`).
- 허용창 이탈, 일일 순차 제한, fixed schedule, forbidden window, 선후행·공유자원 충돌을 검사한다.
- 특정장비 08:00~17:00은 공통 정책으로 하드코딩되어 있지 않다. task의 permitted windows도 현재 optimizer가 개별적으로 검사하지 않고 전체 notice window와 forbidden windows를 사용한다.
- `road_open_after_work` 데이터는 존재하지만 해당 boolean 자체에 대한 별도 계산은 없고, 누락 duration/전체창/순차 조건으로만 실행가능성을 판단한다.
- OR-Tools가 requirements에 있으나 현재 실행 solver는 `exact_enumeration`이며 CP-SAT을 호출하지 않는다.

### 4.6 Pareto와 지표

단일 목적 모드는 `[resident_cost, change_cost]`, multi-axis는 physical energy, sensitive exposure, continuous burden, change cost의 비지배 frontier다. 추천 label은 construction convenience, resident protection, legacy balanced 또는 multi-axis reference이며 같은 candidate면 합쳐진다. 따라서 “항상 3개 추천”이 아니다.

실제 지표는 `ScheduleMetrics`에 다음을 포함한다: 연속 고소음, longest quiet window, 민감시간 고소음, 신규 공사 추가 고소음, 민감 수음점·가중 수음점 minutes, 신규 공사 연속시간, 65 dB-reference energy-minutes, 누적 delta dB-minutes, 기존 이벤트 overlap receptor-minutes, 최대 총소음/신규기여, 일정 변경량. M1/design simulation에는 동시성의 exact/bound와 maximum concurrent combined level이 별도로 있다.

## 5. PoC 시나리오와 공식 데이터 구분

- `/api/poc/scenarios`는 PoC 실행 시나리오다. case-a의 07~18, 장비시간, 거리와 Lw는 공식 현장 일정/측정이 아니다.
- `/api/public-data/construction-design`은 공식 설계 문서에서 보존된 두 구간·물량·출처다.
- 공식 구간 geometry/representative point는 null이며 실제 현장 acoustic prediction/distance calculation은 deferred다.
- `/api/noise/design-simulation/reschedule`는 요청 distance와 가정 geometry를 사용하는 simulated 결과이며 공식 예측이 아니다.
- M1은 입력 provenance를 표시하고 결손 시 deferred, 실측 정렬자료가 없으면 validation_status가 not_evaluable이다.

## 6. 미구현 기능 계획

| 기능 | 필요한 입력 | 출력 | 기존 데이터 재사용 | 신규 API | 난이도/예상 | 기존 API 영향 | 기획 결정 |
|---|---|---|---|---|---|---|---|
| 주민 안내문 | 승인된 공사/추천안, 기간·위치, 공개 가능한 소음/주의사항, 담당부서 | draft 문안, 근거, disclaimer, 승인 상태 | scenario, compare, provenance | 권장: `POST /api/notices/resident-draft` | 중 / 3~5일 | additive | 문체, 필수 고지, 승인주체, 공개 가능한 수치 |
| 주민 화면 조회 | 공개 project ID, 공개 기간/구간 정밀도, 승인 문안/일정 | 개인정보 제거 public DTO | 승인된 notice/추천안 | 권장: `GET /api/public/projects/{id}` | 중~상 / 5~8일 | additive | 공개범위, 인증, 위치 마스킹, 갱신주기 |
| 자연어 조건 수정 | scenario/version, 명령 text, 사용자, 현재 constraints | proposed diff, validation, confirmation token, 재최적화 결과 | extractor schema, OptimizeRequest | 별도 propose/confirm 2단계 권장 | 상 / 7~12일 | 기존 API 변경 없이 additive | 허용 명령, 충돌 우선순위, 승인/감사로그, rollback |
| 법적 판정 | 적용 법령·지역·기간·측정방법·기기/보정·실측값·수음점 | 판정과 근거조항 | 현재 예측값은 판정에 사용 불가 | 승인 전 만들지 않음 | 매우 높음 | 별도 bounded context | 관할 법령, 책임주체, 측정 적격성, 법무 검토 |
| 신고 고급필드 | 장비 규격/최대대수, 장비별 시간, 점용시간, 불변조건과 원문 evidence | 확장 notice DTO | ConstructionTask/constraints 일부 | 기존 extract request 유지, response model 확장 또는 v2 endpoint | 중 / 4~7일 | response additive 가능하나 프론트 재생성 필요 | 필드 정의, 단위, 필수성, 충돌 규칙 |

일정은 1명의 기존 코드 숙련 백엔드 개발자 기준의 구현·테스트 추정치이며 승인된 계획이 아니다.

## 7. 우선순위 제안

1. P0: PRD v2.1 원문 F/S 정의 확보, 신고 고급필드 데이터 사전 확정.
2. P0: 법적 판정 제외 범위와 화면 disclaimer 확정.
3. P1: 주민 안내문 draft 계약과 승인 workflow.
4. P1: 자연어 수정의 propose/confirm 및 감사로그 설계.
5. P2: 주민 공개 API의 인증/비식별/캐시 정책.

## 8. 기획팀 결정 필요 사항

- F1~F12/S1~S8의 원문 이름과 acceptance criteria.
- “상위 10%”의 통계 정의와 표본 부족 처리, median/high 선택 UI.
- PRD 민감도 중복 규칙을 합산에서 최댓값으로 바꿀지 여부와 버전 전략.
- 장비별 시간창, 도로점용, 당일 복구를 hard constraint로 볼지 경고로 볼지.
- 추천안이 3개 미만일 때 중복 복제 금지 여부와 empty/infeasible UX.
- 주민에게 공개할 예측 수치, 위치 정밀도, 데이터 품질 문구.
- 법적 기준 기능의 명시적 제외 또는 별도 검증 프로젝트 승인.

## 9. 검증 근거

- 현재 OpenAPI operations: 21, 모두 명시적 200 response schema.
- 자동화 테스트: 212개(응답 회귀, null/status, CORS 포함).
- 실제 HTTP 예시: `frontend-contract/examples/01-*.json`~`21-*.json`, 오류 4종.
- 타입: `frontend-contract/types/api.d.ts`, `openapi-typescript@7.10.1` 생성.
- 기존 계산/API/시나리오는 이번 감사에서 변경하지 않음.
