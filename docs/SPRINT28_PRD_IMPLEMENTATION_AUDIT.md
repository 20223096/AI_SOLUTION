# Sprint 28 PRD 구현 감사

감사일: 2026-10-27 (KST)

대상: `integration/frontend-backend-s1-s8` / `3d6fbb9d7c40ea3e98a09c693fa0090d7c3638b9`

방법: 소스·fixture·API 모델·테스트의 정적 추적과 기존 공개 함수의 읽기 전용 실행. 구현 코드와 데이터는 변경하지 않았다.

## 결론

S1~S8 API 흐름과 일정 제약 검증, 음향 에너지 계산, offset 후보 열거, Pareto 필터, 안내문 확정/공개 수명주기는 실제 코드로 구현되어 있다. 그러나 원 PRD의 넓은 의미에서 보면 핵심 기능 19개 중 **완료 8, 부분 완료 8, 미구현 3**이다. 가장 큰 차이는 다음과 같다.

- 추천기는 OR-Tools가 아니라 0~120분을 15분 간격으로 탐색하는 `exact_enumeration`이다.
- 공식 공사 선형/외벽 수음점이 없어서 최종 시연은 공식 주소 대표점 사이의 수평거리 또는 PoC 거리 가정을 사용한다.
- S-DoT는 품질 감사 자료일 뿐 음향 합성에 쓰이지 않는다. 도로교통소음만 명시적으로 선택할 때 과거 시간대별 대표 배경값으로 계산된다.
- 공공 공사·행사는 날짜 문맥에는 나오지만 일일 작업시간과 음향값이 없어 추천 음향 계산에는 들어가지 않는다. 9월 11일 중첩은 07:00~09:00, 82 dB의 가정 오버레이다.
- 자연어 제약 구조화와 주민 신고 반영은 구현되지 않았다. 기본 추출기는 결정적 키워드 규칙이며 선택적 LLM 경로는 별도 설정이 있을 때만 동작한다.
- 주민 안내문은 생성형 AI가 아니라 서버/클라이언트 템플릿이다.

상태 정의: `완료`는 현재 제한된 PoC 계약 안에서 코드·테스트·실행 근거가 있는 경우, `부분 완료`는 일부 경로만 구현됐거나 가정/수동 입력/제한된 후보 집합에 의존하는 경우, `미구현`은 실행 경로가 없는 경우다. `완료`는 현장 정확도 또는 법적 적합성을 뜻하지 않는다.

## 1. 기획 기능별 구현 상태

| # | 기능 | 상태 | 실제 구현 근거 | 감사 판단 |
|---:|---|---|---|---|
| 1 | 신고서·공사자료 구조화 | 부분 완료 | `backend/app/services/extractor.py:MockExtractor.extract`, `LLMExtractor.extract`; `backend/app/services/prd_v2_1.py:planning_draft_from_notice`; `backend/app/api/notices.py` | 텍스트/TXT/PDF 추출과 확인 초안은 존재. 기본 mock은 정해진 장비명만 인식하고 기간·주소·복합제약을 일반적으로 파싱하지 않는다. 영구 신고서 저장/수정 수명주기도 없다. LLM은 선택 설정이며 이번 감사에서 실제 호출 검증하지 않았다. |
| 2 | 장비 음향파워레벨 조회 | 부분 완료 | `backend/app/services/acoustics.py:source_noise`; `backend/app/services/m1_acoustics.py:resolve_official_lw`; `data/processed/official_equipment_noise.csv` | 공식 753행을 모델 정확 일치 또는 low/median/high 참조로 조회하는 M1 경로가 있다. 최종 시연 M0는 fixture에 선택된 대표값을 직접 보유하며 실제 배치 장비 확인값이 아니다. 덤프트럭은 값이 없어 제외된다. |
| 3 | 거리감쇠 적용 | 완료 | `backend/app/services/acoustics.py:sound_power_to_pressure`; `backend/app/services/m1_acoustics.py:distance_3d_m` | 구면확산 `Lw-10log10(4πr²)+correction`을 적용한다. M1은 3D/CRS 검증을 한다. 다만 최종 시연 거리의 현장 대표성은 검증 불가다. |
| 4 | 다중 장비 에너지 합산 | 완료 | `backend/app/services/acoustics.py:energy_sum`; `prediction.py:predict`; `m1_acoustics.py:_peak_level` | `10log10(Σ10^(L/10))`, 장비 대수 및 시간가동률 경로가 테스트된다. |
| 5 | S-DoT·도로교통소음 배경 결합 | 부분 완료 | `backend/app/services/background_profiles.py:profile_level`; `prediction.py:predict`; `backend/app/data/background_profiles.json` | 도로교통 프로필은 계산 가능하고 배경으로 에너지 합성된다. S-DoT 프로필은 `calculation_eligible=false`로 의도적으로 제외된다. 따라서 두 자료가 함께 결합된 구현은 아니다. |
| 6 | 시간·장소별 민감도 | 부분 완료 | `backend/app/services/sensitivity.py:time_weight,sensitivity`; `prediction.py:predict` | 시간대와 수음점 유형, 시험기간 가중치가 있다. 반경 판정은 실제 공간 연산이 아니라 receptor type 가정이며 주말/공휴일은 기본 예측 경로에서 전달되지 않는다. |
| 7 | Noise Impact Score 산출 | 완료 | `backend/app/services/impact.py:_score,calculate_impact`; `metrics.py:schedule_metrics` | 슬롯별 0~100 실험점수와 일정 합계/증분 비용을 계산한다. 법적 dB와 분리돼 있으나 계수는 검증된 피해함수가 아니다. |
| 8 | Noise Slot 추천 | 부분 완료 | `backend/app/services/optimizer.py:optimize`; `prd_v2_1.py:constraint_filtered_recommendations` | 15분 offset 후보를 생성하고 제약 필터/Pareto 추천한다. 공정별 자유 배치나 전역 최적화는 아니다. |
| 9 | OR-Tools 최적화 | 미구현 | `backend/requirements.txt`에 의존성만 존재; `optimizer.py:optimize`는 `solver="exact_enumeration"` | import·CP-SAT 모델·solver 호출이 없다. |
| 10 | Pareto non-dominated 후보 | 완료 | `backend/app/services/pareto.py:non_dominated,non_dominated_multi`; `optimizer.py:_dominated_reason,optimize` | 표준 최소화 dominance를 실제 후보에 적용한다. 다만 9개 offset 후보 집합 안의 frontier일 뿐 전역 frontier가 아니다. |
| 11 | 연속 고소음시간 | 완료 | `backend/app/services/metrics.py:schedule_metrics`; M1 `m1_acoustics.py:_exact_temporal_metrics` | M0는 수음점별 값 중 슬롯 최대 `total_estimated_db >= 65`의 연속시간, M1은 명시 interval의 연속 공사소음 시간을 계산한다. 두 정의를 혼용하면 안 된다. |
| 12 | Quiet Window | 완료 | `metrics.py:schedule_metrics`; `resident_notices.py:_complement`; 프론트 `src/screens/s8Quiet.ts:summarizeDay` | 내부 지표는 총환경 <65 dB 구간, 주민 공개는 “확정 공사가 없는 구간”이다. 주민용 값은 실제 정숙 보장이 아니며 API에 제한 문구가 있다. |
| 13 | 동시 고소음시간 | 부분 완료 | `m1_acoustics.py:_pair_overlap_bounds,_exact_temporal_metrics,_peak_level`; `metrics.py:schedule_metrics` | M1 명시 interval이면 source pair overlap과 최대 동시 source 수를 계산한다. M0 일정 지표는 기존 이벤트 중첩을 receptor-minutes로만 제공하고 일반적인 “동시 고소음 분” 필드는 없다. |
| 14 | 일정 변경량 | 완료 | `optimizer.py:_candidate`; `metrics.py:compare` | 작업별 시작 이동 절댓값 합, 프로젝트 시작/종료 이동을 계산한다. |
| 15 | 다른 공사·행사·수거 일정 반영 | 부분 완료 | `public_data.py:calendar_overlaps,acoustic_public_events`; `prediction.py:predict`; `backend/app/data/existing_events.json` | 공공 공사·행사는 달력 문맥만 제공한다. 음향 계산에는 검증된 시간+dB가 모두 있어야 하나 현재 0건이다. 수거 자료 0행이며 사용되는 값은 PoC 가정이다. |
| 16 | 주민 안내문 생성 | 완료 | `resident_notices.py:_template,ResidentNoticeService.create/update/confirm`; 프론트 `s7Notice.ts:buildDrafts` | 템플릿 초안, 수정, snapshot 검증, 확정, 공개/무효화가 구현됐다. 생성형 AI 기능은 아니다. |
| 17 | 주민 신고 반영 | 미구현 | 관련 DTO·repository·API·최적화 입력 없음 | 안내문의 문의처 문구만 있으며 주민 민원 수집·분류·가중·재추천 경로가 없다. |
| 18 | 자연어 제약조건 구조화 | 미구현 | `extractor.py:MockExtractor.extract`, `planning_draft_from_notice` | 임의 자연어 제약 파서가 없다. 장비시간·점용·복구·고정작업은 S2 수동 확인 입력으로 구조화된다. |
| 19 | 소음 원인 기여도 분석 | 부분 완료 | `prediction.py:predict`의 장비 source metadata 및 `new_project_contribution_db`; `m1_acoustics.py:predict_m1`의 source별 Lw/Lp/활동 정보 | 신규 공사 전체 기여와 source별 중간값은 제공하지만, 총소음/Impact를 원인별 비율로 분해하는 attribution 결과는 없다. |

집계: 완료 8, 부분 완료 8, 미구현 3, 검증 불가 0. 다만 현장 정확도와 LLM 실운영 품질은 별도의 의미에서 `검증 불가`다.

## 2. 계산식과 단위 감사

### 구현식

- 거리감쇠: `sound_power_to_pressure(Lw, r) = Lw - 10 log10(4πr²) + correction`, 즉 `Lw - 20log10(r) - 10log10(4π)`이다. 상수는 약 `-10.99 dB`다.
- 기획서 간이식 `Lw - 20log10(r) - 8`과는 같은 거리 기울기지만 상수가 약 2.99 dB 다르다. 예를 들어 Lw 100 dB, 10 m에서 기획식은 72.00 dB, 구현식은 69.01 dB다.
- 장비 합산: `energy_sum = 10log10(Σ10^(Li/10))`로 기획과 일치한다.
- 배경+기존 이벤트+신규 공사는 각각 선형 에너지로 합성한다. dB를 산술 덧셈하지 않는다.
- 시간/장소 민감도는 `ImpactRequest.sensitivity_weight`에만 들어가며 `total_estimated_db`, M1 `slot_laeq_dba`를 바꾸지 않는다.
- `Impact score`의 슬롯값은 0~100 clamp다. `total_impact_score`/`absolute_impact_cost`는 receptor-slot 점수의 합이라 100을 넘을 수 있다.

### Impact 정규화

`backend/app/services/impact.py:_score`의 구성요소는 다음과 같다.

- level: `(total_db - threshold_db + 10) / 30`
- duration: `duration_minutes / 480`
- continuous: `continuous_minutes / 180`
- sensitivity: `((weight - 1) / 1.5) * level_component`
- cumulative: `cumulative_exposure / 100`
- 가중치: level 0.45, duration 0.20, continuous 0.15, sensitivity 0.15, cumulative 0.05; 각 구성요소와 최종점수를 `[0,1]` 및 `[0,100]`으로 clamp한다.

이는 영향 우선순위용 실험 지수다. 주민 피해 감소, 건강효과 또는 법적 적합성을 입증하지 않는다.

### 65 dB의 의미

`metrics.py:schedule_metrics`의 기본 65 dB는 PoC 내부 분석 임계값이다. 법정 기준값이 아니며 API도 `legal_assessment=null`을 반환한다. `max_continuous_high_noise_minutes`는 배경을 포함한 총환경이 이 임계값 이상인 시간이라, 배경 프로필이 하루 종일 65 dB 이상이면 공사 이동과 무관하게 660분/quiet 0분이 될 수 있다.

### 원천 장비값 선택

- M1 명시 Lw가 있으면 그것을 우선한다.
- 없으면 동일 category의 정확한 model 1건을 요구한다.
- model이 없으면 사용자가 `low|median|high` reference scenario를 명시해야 한다.
- 덤프트럭·램머·디젤펌프/펌프는 호환 category로 임의 대체하지 않는다.
- 최종 시연의 K6500 113, GB525E(저소음) 122, ZX55USR-5A 100, BW141AD-5 102 dB는 공식 목록의 분포 대표 레코드이지 현장 장비 확인값이 아니다.

### 물리적 단순화

점음원 자유장 구면확산, 수평/3D 직선거리, 고정 Lw, 15분 슬롯을 사용한다. 지면·대기·차폐·건물·반사·기상 보정은 M1에서 명시 입력하지 않으면 `not_modelled`다. 공식 대표 주소점은 실제 공사 선형도 외벽 수음점도 아니다. 현장 실측 교정 전에는 더 정확한 예측이라고 표현할 수 없다.

## 3. 데이터: 저장과 계산 사용의 구분

| 데이터 | 파일/주요 컬럼·기간 | 계산 진입점 | 상태와 fallback/결측 처리 |
|---|---|---|---|
| 국립환경과학원 건설기계 소음도검사 | `data/processed/official_equipment_noise.csv` 753행; category, manufacturer, approval, model, noise_db, unit, condition, source_period | `m1_acoustics.py:_official_rows,resolve_official_lw`; 최종 시연 fixture | 부분 연동. 정확 model 또는 명시 분포 참조만 사용. 미일치/금지 category는 계산 보류 또는 제외. |
| 신촌 S-DoT | `data/processed/sdot_sinchon_clean.csv` 21,654행; 2025-11-12~2026-10-11; noise_avg/max/min, quality | 프로필 생성/품질 감사만 | 저장·감사 완료, 계산 미사용. 지표 정의·교정·설치 위치 호환성 미확인으로 `calculation_eligible=false`; 결측은 held. |
| 도로교통소음 | `data/processed/road_noise_sinchon_clean.csv` 51,075행; 2025-01-01~2026-06-30; date, hour, station, LEQ, quality | `background_profiles.py:profile_level` → `prediction.py:predict` | 명시적으로 `road_traffic_observed_profile`을 선택하면 weekday/weekend 시간별 대표 중앙값 사용. 해당 시간 값이 없으면 `None`과 warning; 수음점·분석일 실측이 아니다. |
| 서울시 건설알림이 | `construction_events.csv` 3행; 사업기간·대표좌표, 일일시간/noise_db 결측 | `public_data.py:calendar_overlaps` | 달력 문맥만 사용. 현재 `acoustic_public_events()` 0건이므로 합성/추천 목적에는 미반영. |
| 서울시 문화행사 | `cultural_events.csv` 55행; 행사기간, 일부 시간, 대표좌표; noise_db 결측 | `calendar_overlaps` | 날짜 문맥만 사용. 시간+dB+verified_public 조건을 만족하지 않아 합성 미반영. |
| 수거 일정 | `waste_collection.csv` 0행 | 공개 catalog; `existing_events.json`의 별도 가정 이벤트 | 공식 처리자료는 계산 미사용. 09:00~09:30/75 dB 등 값은 PoC 가정이며 시나리오 opt-in일 때만 사용. |
| 주거·학교·병원·대학 | `receptors.csv`, `official_facilities.csv`, `receptor_distances.csv`; 학교 452.8/235.3 m, 병원 633.1 m | scenario receptor → `prediction.py:predict`; M1 request | 학교/병원 공식 대표좌표 거리는 사용. 주거 외벽은 확보되지 않았고 25/30/50/100 m 등은 fixture 가정. `land_use.csv`는 0행이라 행정구역/용도지역 판정 없음. |
| 시험기간 | `academic_calendar.csv` 2행; 서강대 2026-10-20~26, 12-15~21 | `public_data.py:is_exam_period` → `prediction.py:predict` | `public_data_calendar_institution`이 설정된 시나리오에만 반영. 9/11·10/7 최종 시연에는 시험기간 아님. 연세/이화로 전용하지 않는다. |
| JUSO 검색·공식 좌표 | 런타임 API; 응답의 road/parcel address, admCd/rnMgtSn/udrtYn/buldMnnm/buldSlno, entX/entY | `coordinate_lookup.py:JusoCoordinateClient.lookup`; `/api/locations/address-coordinate`; S2 | 주소 선택·좌표 확인용. 계산 scenario의 공사 선형/수음점 거리로 자동 주입되지 않는다. 다중 후보는 사용자 선택 요구, 실패는 provider 오류로 반환한다. |

## 4. 민감도와 제약조건 시나리오 추적

| 시나리오 | 실제 판정 | 데이터 성격 |
|---|---|---|
| 일반 평일 vs 시험기간 | 대학 receptor에 legacy `+0.5`; 공식 달력은 지정 institution/date일 때만 | 공식 달력 또는 fixture 가정. 9/11·10/7에는 차이 없음 |
| 학교 수업시간 vs 외 | 일반 day weight와 학교 유형 `+0.5`는 있으나 수업시간표 조건은 없음 | PoC 가정 |
| 병원 반경 안 vs 밖 | 실제 radius 계산 없이 병원/학교 type이면 조정 적용. config의 300 m는 판정에 쓰이지 않음 | PoC 가정; 기능 갭 |
| 주거지역 vs 기타 | residential type만 구분. 토지용도/행정구역 GIS 판정은 없음 | PoC 가정 |
| 평일 vs 공휴일 | 주말용 `weekend_rest` 인자는 있으나 `predict`가 전달하지 않음. 공휴일 달력 없음 | 미구현 |
| 다른 공사 고소음 중첩 | fixture event가 같은 receptor/slot이면 합성 및 receptor-minutes 집계 | 9/11 값은 가정 |
| 행사 충돌 | 날짜 문맥만. 검증된 음향/시간이 없어 hard constraint도 음향 목적도 아님 | 공식 일정, 계산 미반영 |
| 수거 충돌 | assumed event opt-in 시 합성 가능. 공식 처리행 0 | 가정 |
| 특정장비 08~17시 | `validate_prd_schedule`이 명시 `permitted_time_windows` 검사 | 사용자 확인 입력 |
| 작업 선후관계 | validator가 predecessor 종료≤후속 시작 검사; base optimizer는 순차생성으로 보존 | 사용자/fixture 입력 |
| 당일 굴착·복구 | restoration ID 존재와 당일 종료 검사. 누락 duration은 자동 추정하지 않음 | 사용자 확인 입력 |
| 도로점용 허가시간 | `road_excavation=true`이고 permit window가 있을 때 모든 assignment 검사 | 사용자 확인 입력; 공식 허가 API 연동 아님 |

legacy 민감도는 시간대와 유형 adjustment를 더할 수 있다. PRD 실험 정책 `prd_max_v2_1_experimental`은 겹치는 조건 중 단일 최대 multiplier만 사용해 중복 곱셈을 피한다. 기본 S4는 legacy 정책이므로 “동일 수음점 가중치 비중복”을 보장하는 것은 실험 정책뿐이다. 물리 dB에는 어느 정책도 적용되지 않는다.

## 5. 최적화 감사

- 후보: `offset-0`부터 `offset-120`까지 15분 간격 9개.
- solver: `exact_enumeration`; OR-Tools 미호출.
- base hard constraints: 작업시간 존재, 일일 순차시간, 07~18 fixture 창, fixed schedule, forbidden windows.
- PRD 후처리 constraints: 전체/장비/점용 시간, 장비 수·필요시간, 고정 작업, 선후관계, 당일복구, 완료일.
- 목적: 기본은 resident cost와 작업별 시작 이동 합. `multi_axis`는 physical energy, sensitive exposure, continuous burden, change cost의 독립 4축이다.
- Pareto: 구현된 9개 후보에 대해서는 실제 non-dominated 검사를 수행한다.
- 후보 하나: 프론트 S5가 한 개임을 명시하고 수동 선택을 요구한다.
- 후보 없음: backend는 `none_feasible`/사유를 반환하고 프론트는 다음 단계 선택을 막는다.
- 한계: 공정별 독립 시작·병렬 자원할당·다일 분할을 탐색하지 않으므로 전역 최적이라고 부를 수 없다.

## 6. S1~S8 화면 감사

| 화면 | 실제 API/상태 | 감사 결과 |
|---|---|---|
| S1 | `/api/notices/extract`, `/extract-file` | 실제 응답 사용. mock은 “규칙 기반 추출(AI 아님)”으로 표시. 기본 예시 문구는 입력 샘플이지 계산 결과가 아니다. |
| S2 | `/api/prd/planning/from-notice`, `/api/locations/address-coordinate` | 누락값 수동 확인, JUSO 후보/좌표 사용. 지도 시각화는 없으며 공식 좌표가 계산 거리로 자동 연결되지 않는다. |
| S3 | `/api/prd/schedules/validate` | 실제 제약 위반과 일정 timeline 사용. 시간대별 **작업 일정**은 있으나 시간대별 소음 그래프는 없다. |
| S4 | `/api/prd/recommendations/constraint-filtered` | 실제 후보·Impact·중첩·위반·caveat 사용. 추천 사유는 위반/Pareto 상태와 연결되지만 backend `recommendation_reasons`의 상세 evidence를 UI가 모두 표시하지는 않는다. |
| S5 | S4 response | 실제 selectable 후보와 2축 scatter를 사용. 민감도 지도는 없다. |
| S6 | `/api/schedules/compare` | before/after를 서버 재계산해 snapshot 후보와 대조. 지표는 시뮬레이션임을 표시. |
| S7 | resident notice draft/update/confirm API | 서버 snapshot/version 검증 후 공개. 템플릿 초안을 편집한다. `high_noise` 분류는 담당자 checkbox 입력이라 계산된 65 dB 결과가 아니다. |
| S8 | public resident notice API | 확정 publication만 조회하며 S7 일정과 동일 snapshot 기반. 내부 dB/Impact/수음점 수치 미노출. |

### UI 관련 잔여 위험

- 상태는 React 메모리에만 있다. 새로고침 시 S1~S7 진행 상태가 복원되지 않으며, S8도 현재 App 상태가 없으면 직접 진입 경로가 없다. 서버 publication 자체는 유지된다.
- S4/S5의 수치는 실제 API 응답이지만 underlying scenario에는 공식·가정 자료가 혼재한다. caveat는 일부 표시되나 후보 카드마다 provenance를 상세히 분리하지 않는다.
- 원 기획의 민감도 지도는 미구현이다. 일정 timeline과 후보 비교는 구현됐다.
- S7 기본 조정 이유는 실제 compare delta에서 파생되지만 사용자가 편집할 수 있다. 게시 문구는 계산 결과와 자동 재검증되는 자연어가 아니다.
- 일정 변경 시 App이 하위 state를 폐기하고 서버도 publication을 무효화하지만, 브라우저 새로고침 복원 설계가 없어 장기 workflow UX는 미완성이다.

## 7. 회귀 검증

- backend: `pytest -q` → **269 passed in 6.31s**
- frontend: `npm test -- --run` → **2 files, 13 passed**
- production build: `npm run build` → TypeScript 및 Vite 성공, 51 modules transformed
- 이 감사에서는 실제 브라우저 E2E나 외부 API를 재실행하지 않았다. 목적이 계산·PRD 구현 감사이고, 위 수치는 단위/통합 테스트와 직접 서비스 함수 실행 근거다.

## 8. 핵심 누락 및 제출 표현 원칙

필수 누락은 OR-Tools/일반 일정 최적화, 자연어 제약 구조화, 주민 신고 피드백, 공식 공사 선형·외벽 수음점, 현장 장비·가동률·측정 기반 검증이다. 발표에서는 “실제 주민 피해 감소”, “법적 기준 충족”, “AI가 최적해 산출”, “S-DoT 실시간 결합”이라고 표현하면 안 된다. 정확한 표현은 “제한된 offset 후보에 대해 가정과 출처를 표시한 계획지원 시뮬레이션”이다.
