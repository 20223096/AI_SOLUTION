# M1 물리 음향 모델

## 1. 모델 경계

M1은 기존 M0와 별개인 선택형 계산기다. 기존 `POST /api/noise/predict`와 모든 기본 결과는 유지하며, M1은 `POST /api/noise/predict-m1`로만 실행한다. 실측 검증이 없으므로 응답의 `validation_status`는 `not_evaluable`이고 정확도 향상을 주장하지 않는다.

코드는 `backend/app/services/m1_acoustics.py`, 입력 모델은 `backend/app/models/domain.py`, API는 `backend/app/api/noise.py`에 있다.

## 2. 음원과 필수 입력

음원 유형은 다음을 구분한다.

- `fixed`: 펌프 등 고정 장비
- `moving_work`: 굴착기·절단기·다짐장비처럼 작업점이 변하는 장비
- `moving_vehicle`: 덤프트럭 등 이동 차량
- `impulsive`: 브레이커·램머 등 충격성 장비

각 음원은 공사구간 ID, 장비 종류/모델, 대수, Lw와 출처, 3차원 작업 위치, 배치시간, 슬롯 실제 가동분 또는 명시적 가동구간, 동시가동 그룹, 측정조건 검증 상태를 받는다. 현재 공간 전파는 **슬롯별 명시적 점 위치**에서 계산한다. 이동·선형 음원은 유형을 보존하지만 경로 geometry와 구간별 체류시간이 없으면 선/이동 음원 적분을 수행하지 않는다.

공식 두 구간은 독립 ID로 유지한다.

- `segment-yeonse-ro-2na-gil`: 328m, D450mm
- `segment-chungjeong-ro`: 155m, D600mm

두 구간 geometry는 여전히 `null`이다. M1 요청에서 실제 또는 명시적 시뮬레이션 좌표를 주지 않으면 `calculation_status=deferred`다. 기존 대표 좌표를 자동 복사하지 않는다.

## 3. 계산식

### 자유음장 점 음원

음원 하나의 전가동 수음점 레벨은 다음과 같다.

`Lp = Lw - 10 log10(4πr²) + ΣCk`

`r`은 음원·수음점의 3차원 거리다. 대수 `N`은 `10 log10(N)`으로 에너지 합산한다. 지면, 대기흡수, 방음벽, 건물, 반사, 기상 보정은 독립 항이다. 값과 근거가 없으면 숫자 0 dB가 아니라 `status=not_modelled`, `value_db=null`을 반환한다.

### 15분 가동률

슬롯 길이 `T=15분`, 장비별 실제 가동시간 `ti`일 때 공사 기여 LAeq는 다음과 같다.

`Lconstruction = 10 log10(Σ 10^(Lpi/10) × ti/T)`

5분 가동은 `ti/T=1/3`이다. 미확인 가동시간은 15분으로 채우지 않고 계산을 보류한다. 100% 가동은 요청자가 `actual_active_minutes=15`와 `activity_provenance=assumed`를 명시한 경우에만 상한 가정으로 사용한다. 운전 부하나 작업모드가 더 시끄러울 가능성이 있으므로 통계적·절대적 최악값으로 표현하지 않는다.

### 배경과 총소음

`Ltotal = 10 log10(10^(Lbackground/10) + 10^(Lconstruction/10))`

`delta_total_db=Ltotal-Lbackground`이며, 기존 `legacy_v1` Impact도 병렬 계산한다. 신규 공사 에너지 노출은 65 dB 기준 선형 에너지-분으로 반환한다.

## 4. 동시 운전

- `exact`: 실제 가동구간으로 최대 동시 레벨을 계산한다.
- `complete_concurrent`: 완전 동시 운전 가정.
- `sequential_possible`: 순차 운전이 가능한 경우의 최대 레벨.
- `overlap_unknown`: 순차 최소와 완전 동시 최대만 반환하고 단일값이나 신뢰구간을 만들지 않는다.

각 장비 가동분이 고정되면 슬롯 LAeq 에너지 총량은 슬롯 안의 순서와 무관하다. 동시성은 순간 최대 합성레벨과 노출의 연속성에 영향을 준다. 예를 들어 같은 69.01 dB 음원 두 대가 각 10분 가동하면 슬롯 LAeq는 두 가정 모두 70.26 dB지만 최대 동시 레벨은 순차 69.01 dB, 완전 동시 72.02 dB다.

M1은 일정 생성기가 아니다. 공정 선후행·자원·작업창 실행 가능성은 기존 optimizer가 검증한 후보에 대해 음향평가를 호출해야 한다. M1 API 자체는 일정을 추천하거나 실행 가능하다고 표시하지 않는다.

## 5. 거리와 CRS

- `EPSG:4326`: 경위도를 구면거리로 m 단위 변환한다.
- `EPSG:5179`, `EPSG:5186`: 같은 투영 CRS의 x/y 차이를 m로 사용한다.
- 서로 다른 CRS의 암묵 변환은 금지한다.
- 높이차를 포함해 `sqrt(horizontal² + Δz²)`로 계산한다.
- 잘못된 CRS, 경위도 범위, 0m 거리는 오류로 처리한다.

실제 좌표가 없는 공식 설계 구간은 거리 계산을 보류한다. M0의 기존 수음점 거리는 `representative_point_assumption` 성격이며 M1의 공식 구간 geometry로 승격되지 않는다.

## 6. 공식 장비자료 매칭

모델명이 있을 때 같은 공식 장비 분류 안에서 정확히 한 건과 일치해야 Lw 참조를 허용한다. 응답에는 승인번호, 모델, URL, 측정조건 문구를 보존한다. 원본 행에 현장 운전조건이 없으므로 `measurement_condition_verified=false`다.

모델이 없으면 `low`, `median`, `high`를 명시해 종류별 공식 분포 레코드를 선택할 수 있다. 이는 `official_reference` 민감도 시나리오이며 현장값이 아니다.

- 절단기: 콘크리트 절단기 31건
- 브레이커: 198건
- 굴삭기: 공식 분류 `굴착기` 405건과 유사 매핑
- 롤러: 롤러/다짐기계 119건
- 램머, 덤프트럭, 디젤펌프: 타 분류 대체 금지, `missing_noise_reference`

## 7. API 상태

계산 성공 시에도 입력에 가정 좌표·가동률이 있으면 `calculation_status=simulated`다. 위치, 가동시간 또는 Lw가 빠지면 `deferred`와 `missing_required_inputs`를 반환한다. `field_verified` 입력만 있다고 해서 전체 모델 검증이 끝난 것은 아니며 실측 비교 전 `validation_status=not_evaluable`을 유지한다.

