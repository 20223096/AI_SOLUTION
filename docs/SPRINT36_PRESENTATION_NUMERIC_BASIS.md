# Sprint 36 발표 수치 근거

## 화면 데이터 계보

발표 비교 화면은 `public/sprint36-comparison.json`을 읽는다. 이 파일은 다음 명령으로 생성했으며 UI 소스에 결과 수치를 하드코딩하지 않는다.

```bash
PYTHONPATH=backend python3 scripts/run_sprint29_experiments.py --output public/sprint36-comparison.json
```

생성기는 `sprint29_cp_sat_v2`, `road_traffic_observed_profile`, 15분 grid를 사용한다. 시나리오 fixture, Python/OR-Tools 버전, 실행 시각, 입력 설명과 모델 가정은 JSON 최상위 및 날짜별 레코드에 함께 기록한다. 생성 과정은 fixture나 기존 추천 snapshot을 수정하지 않는다.

## 발표 수치

| 날짜 | 안 | Noise Impact | 제약 위반 | 탐색/Pareto | 변경량 | Quiet Window | 연속 고소음 |
|---|---|---:|---:|---:|---:|---:|---:|
| 2026-09-11 | 원안 | 7.36 | 0 | 9/1 | 0분 | 0분 | 660분 |
| 2026-09-11 | offset_v1 | 7.36 | 0 | 9/1 | 0분 | 0분 | 660분 |
| 2026-09-11 | cp_sat_v2 | 7.36 | 0 | 495/35 | 0분 | 0분 | 660분 |
| 2026-10-07 | 원안 | 13.72 | 0 | 9/9 | 0분 | 0분 | 660분 |
| 2026-10-07 | offset_v1 | 13.20 | 0 | 9/9 | 480분 | 0분 | 660분 |
| 2026-10-07 | cp_sat_v2 | 13.12 | 0 | 495/18 | 420분 | 0분 | 660분 |

9월 11일은 기존 일정 유지가 정상 결과다. 10월 7일의 `13.72 → 13.12`는 Noise Impact 모델 점수 변화이고, `420분`은 별도 일정 변경량이다. 두 값을 같은 의미로 해석하지 않는다.

Noise Impact는 `incremental_impact_cost` 시뮬레이션 점수다. 실측 소음, 주민 노출, 민원 건수 또는 실제 피해 감소를 나타내지 않는다. Quiet Window와 연속 고소음시간은 PoC의 총환경 65 dB threshold에 따른다. 실험에서 계산하지 않은 값은 JSON의 `null`을 유지하고 화면에서는 `N/A`로 표시한다.

## 화면 캡처

- [데스크톱](assets/sprint36/comparison-desktop.png)
- [모바일](assets/sprint36/comparison-mobile.png)

Chromium E2E가 동일 화면의 핵심 문구, 두 날짜, 생성기 출처와 가로 overflow 부재를 확인하면서 위 파일을 생성한다.
