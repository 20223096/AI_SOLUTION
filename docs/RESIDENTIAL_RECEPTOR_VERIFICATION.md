# 주거 수음점 공식 용도 교차검증 (15차)

## 결론

2026-10-24 기준 충정로 35-17의 **주소와 건물 신원**은 건축HUB 표제부에서 확인했지만, 주소기반산업지원서비스 좌표제공 API의 별도 승인키(`confmKey`)가 없어 공식 좌표는 확보하지 못했다. 따라서 공식 공사구간 `geometry=null`, 충정로 거리대별 집계, 외벽 수음점, M1 현장 예측은 계속 `deferred`이다. 좌표를 임의 생성하거나 OSM 좌표를 공식 좌표로 승격하지 않았다.

건축HUB의 정확 일치 결과는 충정로3가 120-1, 도로명주소 충정로 35-17, 충정로 제2빌딩, 건물관리번호 `101411159`, 주용도 `제2종근린생활시설`이다. 이 건물은 공식 주거 건물로 분류하지 않았다.

## 공식 주소 API 경로와 좌표계

구현 위치는 `backend/app/services/official_address.py`이다.

1. 도로명주소 검색 API `addrLinkApi.do`에서 정확한 도로명주소 1건을 고른다.
2. `admCd`, `rnMgtSn`, `udrtYn`, `buldMnnm`, `buldSlno`를 좌표제공 API `addrCoordApi.do`에 전달한다.
3. `entX`, `entY`는 주소정보 누리집이 안내하는 UTM-K(GRS80), 즉 EPSG:5179로 취급하고 EPSG:4326으로 역변환한다.
4. 정확 일치가 0건 또는 복수이면 좌표를 채우지 않는다.

주소 검색과 좌표 제공은 서로 다른 API이며 좌표 API도 별도 신청이 필요하다. 공식 안내: [주소정보 누리집 좌표 API 답변](https://business.juso.go.kr/addrlink/qna/qnaDetail.do?bulletinRefSn=128137), [검색 후 코드 기반 좌표 조회 절차](https://www.juso.go.kr/addrlink/qna/qnaDetail.do?bulletinRefSn=134424). 현재 `.env`에는 JUSO 승인키가 없다. 키 원문이나 요청 URL은 산출물에 기록하지 않는다.

## 건축HUB 403 재현 및 원인

프로젝트의 정상 수집 코드는 포털의 인코딩된 serviceKey를 `unquote`한 뒤 HTTP 클라이언트의 쿼리 파라미터 인코딩을 한 번만 적용한다. 14차 일회성 `curl --data-urlencode` 진단은 이미 인코딩된 키에 다시 인코딩을 적용해 `%`가 `%25`로 바뀌었다. 이 차이가 403의 원인이다.

현재 정상 경로로 재검증한 결과는 HTTP 200, 응답코드 `00`, `NORMAL SERVICE`이다. API 경로와 필수 파라미터도 동일했으며 승인 중단이나 호출량 초과 증거는 없다. 비밀키는 길이와 존재 여부만 진단하며 원문은 출력하지 않는다.

## 서울시 건축물대장 대체자료

- 총괄표제부 OA-23051은 한 대지에 둘 이상의 건물이 있는 경우의 총괄 정보로, 전체 건물별 검증 자료가 아니다. 실제 API `aiVBigDjrRecapTitle`에서 두 대상 주소의 정확 일치는 없었다.
- 건물별 표제부 OA-22424(`vBigDjrTitle`)는 주용도·동명·건물 식별자를 제공하지만 좌표 필드가 없고, 현재 583,877건 규모다. [서울시 표제부 데이터셋 공지](https://data.seoul.go.kr/together/notice/datasetNoticeView.do?bbsCd=10008&ditcCd=&pageIndex=1&seq=98f410ec29343dfa9ee4b419eb05d36e)
- 필지 하나에 여러 동이 있을 수 있으므로 주소 문자열 유사도만으로 OSM 폴리곤과 자동 결합하지 않았다. 공식 식별자 또는 필지의 정확 일치 후에도 일대다이면 보류한다.

## OSM 1,559개 재분류

| 구간/검색영역 | 원본 폴리곤 | 공식 주거 확인 | OSM 주거 후보 | 용도 미확정 | 비주거 태그 |
|---|---:|---:|---:|---:|---:|
| A 연세로2나길 | 748 | 0 | 10 | 447 | 291 |
| B 충정로 검색영역 | 811 | 0 | 94 | 690 | 27 |
| 합계 | 1,559 | 0 | 104 | 1,137 | 318 |

`apartments`, `residential`, `house`, `detached`, `terrace`, `semidetached_house`, `dormitory`만 OSM 주거 후보로 인정했다. `building=yes`는 모두 `unknown_building_use`로 남겼다. 명백한 상업·학교·종교·업무 등의 OSM 태그는 `verified_non_residential`로 분류했지만, 여기서 “verified”는 해당 OSM 태그가 명시적이라는 뜻이며 공식 대장 교차검증을 뜻하지 않는다. 공식 검증 여부는 별도 match 필드로 구분한다.

기존 A의 10개 후보는 유지했다. B의 94개는 500m 탐색영역 안의 주거 태그 후보일 뿐, 공식 주소 기준점이 없어 100/200/300m 수음점 후보로 승격하지 않았다. 1,559개 OSM ID 중 중복은 0개였다.

## 거리와 수음점

A의 OSM 주소 건물 기준 폴리곤 경계 거리는 100m 2개, 200m 4개, 300m 10개다. 이는 실제 공사선형 거리와 다르다. B의 공식 좌표가 없으므로 거리 분포는 계산하지 않았다.

건물 폴리곤·중심점은 실제 외벽 측정점이 아니다. 작업 방향과 공사선형이 없기 때문에 외벽점 좌표는 비워 두고 `candidate_deferred_no_construction_alignment`로 표시했다. 수음점 높이도 `unknown`이다.

## 산출물과 출처

- `official_address_anchors.json`: 공식 신원, 좌표 확보 상태, OSM 탐색 기준점의 구분
- `building_use_match_audit.csv`: 1,559개 OSM 레코드와 충정로 공식 표제부 1건의 분류 근거
- `residential_buildings.csv`, `.geojson`: 104개 OSM 주거 후보
- `receptor_candidates.csv`: 기존 A 거리 조건을 만족한 10개 후보
- `receptor_coverage_report.json`: 집계·진단·deferred 상태
- `data/processed/archive/v14/`: 갱신 전 14차 산출물 사본

원본 OSM 추출 시점과 해시는 14차 자료에 보존되어 있다. 건축HUB 결과는 공공데이터포털 `BldRgstHubService/getBrTitleInfo`, 서울 자료는 OA-23051/OA-22424, 주소 좌표계는 주소정보 누리집 공식 안내를 근거로 했다.

## 남은 사용자 조치

1. 주소기반산업지원서비스에서 **도로명주소 검색 API와 좌표제공 API** 승인키를 신청하고 `JUSO_API_KEY`로 로컬 환경에 설정한다.
2. 키 확보 후 두 주소를 다시 조회하고 EPSG:5179 원좌표와 EPSG:4326 변환값을 함께 보존한다.
3. 실제 공사선형 또는 작업점, 구간별 현장 수음점과 높이를 확보한다.
4. OSM 후보를 공식 건물 폴리곤/필지·건물 식별자와 일대일로 결합할 수 있는 원자료를 확보한다.

이 조치 전에는 공식 주거 확인 수 0, 외벽 수음점 확인 수 0, 실제 정확도 `not_evaluable`이다.

## 검증 결과

- 기존 172개와 신규 8개를 합친 **pytest 180개 통과**
- Python `compileall` 통과
- API 스모크: `/api/health`, `/api/public-data/catalog`, 기존 M0 `/api/noise/predict` 모두 HTTP 200
- 공식 공사 2개 구간의 `geometry`와 대표점은 계속 `null`
- 로컬 커밋 대상으로 검토했으며 원격 push는 수행하지 않는다.
