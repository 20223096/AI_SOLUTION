# 공공데이터 수집·통합 보고서

## 범위와 실행 결과

조회 시점은 2026-10-23(Asia/Seoul)이다. `python3 -m scripts.collect_public_data`로 재실행하며, 원본은 `data/raw/<source>/`, 정규화 결과는 `data/processed/`, 실행 매니페스트와 SHA-256은 `data/reports/public_data_manifest.json`에 남긴다. 기존 S-DoT 및 도로교통소음 원본/ETL은 재수집·재가공하지 않았다.

| 데이터 | 공식 출처 | 상태 | 정규화 행 | 확보 필드 / 결손 | ETL·통합 여부 |
|---|---|---:|---:|---|---|
| 건설장비 소음 | [공공데이터포털 검색](https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%EA%B1%B4%EC%84%A4%EA%B8%B0%EA%B3%84%20%EC%86%8C%EC%9D%8C) | `insufficient_fields` | 0 | 모델별 값, Lw/Lp, 측정조건을 함께 충족하는 행 미확보 | 빈 스키마 생성, 기존 PoC 가정값 유지 |
| 신촌 공사 | [서울 One-PMIS 안전점검 일정](https://data.seoul.go.kr/dataList/OA-15589/A/1/datasetView.do) | `blocked_auth` + 과거 서비스 종료 표시 | 0 | 서울 API 키와 현행 서비스명 필요 | 미통합 |
| 문화행사 | [서울시 문화행사 정보](https://data.seoul.go.kr/dataList/OA-23040/S/1/datasetView.do) | `blocked_auth` | 0 | 서울 API 키 필요 | 미통합 |
| 연세대 신촌 | [연세대 공식 오시는 길](https://mirae.yonsei.ac.kr/sc/502/subview.do) | `processed` | 1 | 공식 주소 확보, 공식 좌표/CRS 없음 | 카탈로그만 통합 |
| 세브란스병원 | [세브란스 공식 오시는 길](https://sev.severance.healthcare/sev/about/location/map.do) | `processed` | 1 | 공식 주소 확보, 공식 좌표/CRS 없음 | 카탈로그만 통합 |
| 창서초·창천중·이화대 | 기관별 공식 좌표 자료 추가 필요 | `pending_verification` | 3 | 이름 외 주소·좌표 미검증 | 계산 미통합 |
| 주거 수음점 | PoC 설정 | `assumed` | 1 | 실제 위치 없음 | 기존 가정 유지 |
| 연세대 학사일정 | [연세대 공식 학사일정](https://yonshin.yonsei.ac.kr/theology/department/schedule.do) | `collected`, 추출 0 | 0 | 응답에서 안정적인 기계 판독 범위 미확보 | 미통합 |
| 이화대 학사일정 | [이화대 공식 학사일정](https://cmsguide.ewha.ac.kr/cc/bachelor/academic-schedule.do?date=2026-10&mode=calendar) | `pending_verification` | 0 | 시험 명칭 확인, 날짜 자동추출 보류 | 미통합 |
| 서강대 학사일정 | [서강대 공식 학사일정](https://me.sogang.ac.kr/ko/undergraduate/calendar) | `processed` | 2 | 2026-10-20~26 중간시험, 2026-12-15~21 기말시험 | 시험기간 민감도에 통합 |
| 서대문구 폐기물 | [서대문구 배출 안내](https://www.sdm.go.kr/waste/contents/wasteGuide.do) | `insufficient_fields` | 0 | 주민 배출시간은 차량 수거시간이 아님 | 소음 이벤트 미생성 |
| 용도지역·경계 | [토지이음](https://www.eum.go.kr/web/am/amMain.jsp) | `blocked_access` | 0 | 대상 필지·재사용 가능한 경계/CRS 없음 | 미통합 |

상태별 상세 URL, UTC 조회시각, 원본 경로, 체크섬은 매니페스트가 정본이다. 서울 API 키는 `.env.example`의 `SEOUL_OPEN_DATA_API_KEY`로만 주입하며 저장소에는 저장하지 않는다.

## 정규화 및 안전 규칙

- `Lw_dBA`와 `Lp_dBA`를 명시하지 않은 장비값은 계산에 넣지 않는다. 현재 장비값은 계속 `user_provided` 가정이다.
- 사업기간과 실제 일일 작업시간은 별도 열이며 전자로 후자를 추론하지 않는다.
- 행사 일자와 시각을 분리한다. dB와 실제 시각이 없는 공사·행사는 일정 맥락일 뿐 에너지 합산 대상이 아니다.
- WGS84 좌표와 CRS가 확인된 지점만 지오데식 거리 계산에 쓴다. 주소만 확인된 시설에는 좌표나 거리를 만들지 않았다.
- 주민 배출 가능 시간은 차량 운행·수거 시간으로 변환하지 않는다.
- 행사 중복 키는 `(명칭, 시작일, 종료일, 장소)`이다.

## PoC 통합과 데모 날짜

추가 시나리오 `sinchon-public-2026-10`은 CASE A의 물리 조건을 유지하면서 서강대 공식 일정에서 파생한 대학 수음점 민감도만 적용한다. 권장 검증일은 **2026-10-20~2026-10-26**, 기본 데모일은 **2026-10-20**이다. 이를 연세대·이화대 시험기간으로 표현해서는 안 된다.

2026-10-20 실제 실행 결과는 후보 9개, 실행 가능 9개, Pareto 1개, 추천 `offset-0`이다. 증분 영향비용 1515.85, 절대 영향비용 1523.35, 변경량 0분, 최대 연속 고소음 180분, Quiet Window 480분이다. 비교일 2026-11-02에는 영향비용이 각각 1464.90, 1472.40으로 낮아졌지만 추천은 바뀌지 않았다. 시험기간 민감도가 비용을 바꿨으나 원 일정이 계속 비지배 후보였다.

배경 프로파일은 역사적 대표 프로파일이다. 시연일이 관측일이라는 의미가 아니며 S-DoT는 분석 전용, 도로교통 프로파일만 기존 정책에 따라 물리 합성 가능하다.

## 실제값·가정값과 한계

공식 페이지로 검증된 것은 서강대 시험일 범위와 연세대·세브란스 주소다. 시험기간 여부는 공식 일정에서 `derived`되지만 민감도 가중치 자체는 PoC 정책 가정이다. 장비 소음, 공사원 위치, 수음점 거리, 주거 수음점, 기존 혼잡 이벤트 소음은 기존 가정이다. 주소 검증은 좌표 정확도 검증이 아니며, 현재 공사·행사·폐기물·용도지역 자료는 계산에 반영되지 않았다.

## 추가로 필요한 사용자 작업

1. 서울 열린데이터광장 키를 `SEOUL_OPEN_DATA_API_KEY`로 주입한 뒤 재실행한다.
2. 현행 건설알림이/One-PMIS 서비스명과 주간 공정의 실제 작업시간 필드를 확인한다.
3. 장비 모델, Lw/Lp, 측정거리·운전조건이 함께 있는 국립환경과학원 원문 표를 제공한다.
4. 공사원 WGS84 좌표와 기관 공식 좌표/CRS를 제공한다.
5. 차량 운행 시각이 포함된 서대문구 수거 원자료를 확보한다.
6. 대상 필지 또는 사업구간과 공식 용도지역 경계 파일을 제공한다.

각 원천의 이용약관과 호출 제한을 재확인해야 한다. 원본 디렉터리는 개인정보·대용량 유입을 막기 위해 Git에서 제외하고 정규화 CSV와 매니페스트만 버전 관리한다.
