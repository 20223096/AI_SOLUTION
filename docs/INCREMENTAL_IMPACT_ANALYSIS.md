# 신규 공사 증분 Noise Impact 분석

## 정의

동일 수음점·동일 15분 슬롯·동일 민감도에서 다음을 계산합니다.

- `background_only_db`: 선택한 배경 프로파일 값
- `existing_environment_db`: 배경과 기존 공사·행사·수거 소음의 dB 에너지 합성
- `new_project_contribution_db`: 신규 공사 장비가 해당 수음점에 기여하는 추정 Lp. 전체값의 산술 차이가 아님
- `with_new_project_db`: 기존 환경과 신규 공사 기여 레벨의 dB 에너지 합성
- `delta_total_db = with_new_project_db - existing_environment_db`: 신규 공사 추가 후 총소음의 물리적 증가량
- `baseline_impact = Impact(existing_environment_db)`
- `total_impact = Impact(with_new_project_db)`
- `incremental_impact = max(0, total_impact - baseline_impact)`

신규 공사가 없는 슬롯은 `new_project_contribution_db=null`, `delta_total_db=0`, `incremental_impact=0`입니다. 음원을 산술 dB 차감해 신규 공사 레벨을 역산하지 않습니다. Impact는 같은 시간·수음점·민감도·65dB 분석 임계값·`poc-0.1.0` 점수식을 사용합니다.

## 최적화 목적

응답은 항상 `absolute_impact_cost`, `incremental_impact_cost`, `schedule_change_cost`(`change_cost` 호환 필드)를 보존합니다. `objective_mode` 기본값은 `incremental_impact`; `absolute_impact`를 선택하면 기존 총 절대 Impact 축으로 평가합니다. `resident_cost`는 선택된 모드의 비용을 가리켜 기존 Pareto 코드와 API 계약을 유지합니다.

실험 B의 기존소음 중첩 정책비용은 `policy_overlap_cost`로만 보고하며 두 목적 모두에 더하지 않습니다. 증분 Impact가 이미 기존 환경과 신규 공사의 결합효과를 반영하므로, 검증되지 않은 중첩계수를 추가하면 이중 계산 및 결과 유도 위험이 있기 때문입니다.

## CASE A/B/C/D 재실행

검증일 2026-10-26, 민감도 활성, 주민 보호 선택 기준입니다. 절대/증분 모드의 Pareto와 추천은 각 조합에서 동일했습니다. 기준환경의 분석구간 합계가 후보에 공통인 상수이므로 `incremental = absolute - baseline`은 후보 간 순서를 바꾸지 않습니다.

| 시나리오·배경 | 생성/가능/Pareto | 원 시작 | 주민 보호 시작 | 절대 비용 | 증분 비용 | 변경량 | 연속 고소음 | Quiet | 신규 공사 추가 고소음 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A assumed | 9/9/1 | 07:00 | 07:00 | 1472.40 | 1464.90 | 0 | 180 | 480 | 180 |
| A road | 9/9/9 | 07:00 | 09:00 | 3900.88 | 291.08 | 480 | 660 | 0 | 0 |
| B assumed | 9/9/1 | 07:00 | 07:00 | 1885.58 | 760.84 | 0 | 180 | 480 | 30 |
| B road | 9/9/1 | 07:00 | 07:00 | 4195.96 | 154.20 | 0 | 660 | 0 | 0 |
| C assumed | 9/9/9 | 07:00 | 09:00 | 1481.30 | 1473.80 | 480 | 180 | 360 | 180 |
| C road | 9/9/9 | 07:00 | 09:00 | 3923.80 | 292.20 | 480 | 660 | 0 | 0 |
| D assumed/road | 9/0/0 | 07:00 | 없음 | — | — | — | — | — | — |

CASE D는 모든 조합에서 복구 공정시간 누락과 12:00~14:00 금지시간 충돌로 불가능합니다.

### 수음점별 주민 보호안 점수: 절대 / 증분

| 시나리오·배경 | 주거 | 대학 | 학교 |
|---|---:|---:|---:|
| A assumed | 666.30 / 658.80 | 482.18 / 482.18 | 323.92 / 323.92 |
| A road | 1320.20 / 156.96 | 1256.28 / 93.04 | 1324.40 / 41.08 |
| B assumed | 748.14 / 337.64 | 602.80 / 263.68 | 534.64 / 159.52 |
| B road | 1391.88 / 79.00 | 1349.44 / 52.48 | 1454.64 / 22.72 |
| C assumed | 666.30 / 658.80 | 491.08 / 491.08 | 323.92 / 323.92 |
| C road | 1320.20 / 156.96 | 1279.20 / 94.16 | 1324.40 / 41.08 |

도로 프로파일에서는 절대 비용 대부분이 기존 배경에서 발생하므로 증분 비용이 크게 작습니다. 이는 영향이 없다는 뜻이 아니라 현재 점수식에서 신규 공사의 추가분만 분리한 결과입니다.

## 포화 검증

동일 신규 공사 수음점 기여 레벨 85dB, 주간 민감도 1.0, 15분 슬롯으로 계산했습니다.

| 배경 dB | 합성 총소음 dB | delta_total_db | 전체 Impact | 증분 Impact | 포화 |
|---:|---:|---:|---:|---:|---|
| 50 | 85.00 | 35.00 | 46.88 | 46.88 | level 성분 상한 |
| 60 | 85.01 | 25.01 | 46.88 | 39.38 | level 성분 상한 |
| 70 | 85.14 | 15.14 | 46.88 | 22.50 | level 성분 상한 |
| 75 | 85.41 | 10.41 | 46.88 | 15.01 | level 성분 상한 |

총점 100에는 도달하지 않지만 level 성분이 1.0으로 절단되어 총소음 차이를 더 이상 구분하지 못합니다. 배경 85dB와 총소음 90dB처럼 baseline과 total의 level·시간 성분이 모두 같은 상한에 있으면 물리 증가가 있어도 증분 Impact가 0이 될 수 있습니다. 이 경우 응답의 `impact_saturation.incremental_zero_despite_physical_increase=true`가 경고합니다. 0점은 무영향을 뜻하지 않습니다.

점수식을 임의 변경하지 않았습니다. 대안은 (1) 절단 전 연속 level 성분 병렬 표시, (2) 음향 에너지 또는 `delta_total_db` 기반 증분량, (3) 완만한 비포화 로그/로지스틱 함수, (4) 절대 노출과 프로젝트 귀속 증분의 이중 목적입니다. 기준점·상한·정책 가중치는 담당기관과 음향 전문가가 결정해야 합니다.

## Quiet Window 보조지표

- `new_project_additional_high_noise_minutes`: baseline은 65dB 미만이나 신규 공사 포함 시 65dB 이상이 된 슬롯을 시간축에서 한 번씩 센 분. 단위 분, 법정 기준 아님
- `sensitive_new_project_exposure_minutes`: 신규 공사가 활성이고 민감도 가중치가 1보다 큰 슬롯의 시간. 단위 분
- `incremental_impact_cost`: 모든 수음점·슬롯 증분 Impact 합계

기존 `longest_quiet_window_minutes`와 `max_continuous_high_noise_minutes`는 전체 환경 기준으로 유지됩니다.

## 실제 데이터와 남은 가정

도로 배경은 2025-01~2026-06 신촌 LEQ 시간대 중앙값(`derived`)이며 세 가상 수음점 적용은 `assumed`입니다. 장비 Lw, 거리, 민감도, 임계값, B의 이벤트와 중첩계수는 여전히 가정입니다. 수음점 좌표·측정지점 좌표·교정정보·실제 공사 장비 측정값이 없어 법적 또는 역학적 영향으로 해석할 수 없습니다.
