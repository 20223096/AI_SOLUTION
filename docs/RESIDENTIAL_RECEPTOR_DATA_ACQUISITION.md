# 두 공사구간 주변 주거 수음점 공간정보 수집

## 1. 결론

2026-10-24 실제 다운로드를 수행했다. OSM 건물 폴리곤은 총 1,559개(연세로 검색 748, 충정로 탐색검색 811)를 확보했다. 그러나 공식 GIS건물통합정보 SHP는 VWorld의 대화형 다운로드 제약으로 확보하지 못했고, 승인된 프로젝트의 `DATA_GO_KR_API_KEY`로 건축HUB를 호출했으나 HTTP 403을 받았다. 키 값은 로그·파일·Git에 기록하지 않았다.

연세로2나길 20은 OSM 주소 태그가 정확히 일치하는 건물 객체를 찾았다. 이 주소점에서 폴리곤 외벽까지 300m 이내이며 `building=apartments`가 명시된 10개를 탐색 후보로 저장했다. 건축물대장 교차검증은 실패했으므로 `classification_status=osm_residential_tag_only`, 신뢰도는 `low_not_building_register_verified`다.

충정로 35-17은 주소 존재와 지번 `충정로3가 120-1`은 공개 검색으로 교차확인했으나, Nominatim이 정확 번지를 반환하지 않았다. 도로 중심 검색으로 받은 811개 폴리곤은 주소 기준점이 아니므로 후보로 승격하지 않았다. 좌표를 추측하지 않았다.

## 2. 공개 공간정보 조사

| 우선 | 자료 | 제공형식/조건 | 결과 |
|---:|---|---|---|
| 1 | [국토교통부 GIS건물통합정보](https://www.data.go.kr/data/15083092/fileData.do) | SHP, 6,656,497행, VWorld 기관 다운로드, 공공누리 1유형 | VWorld 대화형 접근/로그인 경로만 확인; 서울·서대문구 원본 미확보 |
| 2 | [건축HUB 건축물대장정보](https://www.data.go.kr/data/15134735/openapi.do) | JSON/XML, 월간, 개발키 자동승인 서비스 | 현재 프로젝트 키 호출 HTTP 403; 속성 미확보 |
| 3 | [연속수치지형도 건물](https://www.data.go.kr/data/15125047/fileData.do) | 전국 SHP 19,402,663행, VWorld 기관 다운로드 | 지역 단위 자동 다운로드 경로 미확보; 전국 파일 미다운로드 |
| 대체 | OSM Nominatim/Overpass | WGS84 JSON, ODbL | 부분 성공 |

원본 응답은 `data/raw/building_footprints/`에 로컬 보존했다. 약 940KB인 OSM 원본은 재현 가능하고 Git에 부적합하므로 `.gitignore` 상태로 유지하며 출처 메타데이터만 커밋한다.

## 3. API 호출 방식

- Nominatim: 전체 도로명주소, `format=jsonv2`, `addressdetails=1`, `countrycodes=kr`, 사용자 에이전트 명시
- Overpass: 검증 주소점 주변 `way[building](around:300, lat, lon)`, `out tags center geom`
- 건축HUB: `BldRgstHubService/getBrTitleInfo`, 서비스키는 `.env`에서 런타임에만 읽고 출력하지 않음
- VWorld: 공공데이터포털이 연결한 `dsId=18`, `dsId=30162` 다운로드 페이지 확인

재현 전처리는 `python3 scripts/process_residential_receptors.py`로 수행한다. 원본 OSM JSON이 있을 때 CSV, GeoJSON, coverage report를 결정론적으로 다시 생성한다.

## 4. 주소 지오코딩

| 구간 | 요청 주소 | 결과 | 좌표 | 품질/출처 |
|---|---|---|---|---|
| A | 서울 서대문구 연세로2나길 20 | 도로명·번호·구 정확 일치 | 37.5569953, 126.9384393 | OSM way/1499237143, EPSG:4326, 공식 주소좌표 아님 |
| B | 서울 서대문구 충정로 35-17 | 정확 번지 미해결 | `null`, `null` | Nominatim이 충정로 도로만 반환; 기준점 보류 |

A 좌표는 주소 건물의 OSM 대표점이며 공사 위치가 아니다. 과거 공사 대표좌표를 두 구간에 공유하지 않았다. B에는 A 좌표나 충정로 도로 중심을 대입하지 않았다.

## 5. 구간별 수집 결과

| 구간 | 다운로드 폴리곤 | 주거태그 후보 | 공식 주거확인 | 100m | 200m | 300m |
|---|---:|---:|---:|---:|---:|---:|
| A 연세로 | 748 | 10 | 0 | 2 | 4 | 10 |
| B 충정로 | 탐색용 811 | 0 | 0 | 0 | 0 | 0 |

반경은 주소 기준점에서 건물 폴리곤 경계까지의 근사 최단거리다. 공사 영향권 또는 공사장-수음점 거리로 해석하지 않는다. B의 0은 주변에 건물이 없다는 뜻이 아니라 기준점 미확정으로 후보 계산을 보류했다는 뜻이다.

주소만 확인됐으나 좌표를 확정하지 못한 건물은 충정로 제2빌딩 1개다. 공식 데이터에서 확보한 폴리곤은 0개다.

## 6. 실제 파일의 예시 5개

다음은 생성된 CSV의 실제 행이며 모두 OSM `building=apartments` 태그다. 건축물대장 용도 확인값은 아니다.

| OSM 건물 ID | 도로명주소 | 중심 위도 | 중심 경도 |
|---|---|---:|---:|
| way/1141324829 | 서울 서대문구 연세로2나길 16 | 37.5568011 | 126.9383423 |
| way/1442814956 | 서울 서대문구 신촌로 119 | 37.5561564 | 126.9389954 |
| way/1442814969 | 서울 서대문구 신촌로 127 | 37.5564618 | 126.9399658 |
| way/1467799367 | 서울 마포구 신촌로 142 | 37.5561324 | 126.9413323 |
| way/1467800863 | 서울 마포구 백범로1길 83 | 37.5560612 | 126.9409824 |

행정경계 필터는 서울 범위 검사만 적용했다. 300m 원 안에 마포구 건물도 실제로 포함되므로 제거하지 않고 주소 속성을 보존했다.

## 7. 주거용도 판정

포함 태그는 `apartments`, `residential`, `house`, `detached`, `terrace`, `semidetached_house`, `dormitory`다. `building=yes`, 상업, 학교, 교회, 호텔 등은 주거로 승격하지 않았다. 이번 10개는 모두 `apartments`였다.

건축HUB 교차검증이 되지 않았기 때문에 “공식 주거용 건물”로 표시하지 않는다. 오피스텔·주상복합은 OSM 태그만으로 확인되지 않아 포함하지 않았다. 개인 이름·연락처·호실 데이터는 수집하지 않았다.

## 8. 공간 계산과 수음점 상태

- 원본 OSM CRS: EPSG:4326
- 거리 계산: 주소점 위도에서의 로컬 등거리 근사 투영, 단위 m, 최대 300m 범위
- `address_anchor_distance_m`: 주소점→폴리곤 경계 최단거리
- `building_centroid_distance_m`: 주소점→건물 중심점 거리
- 폴리곤: 폐합 및 서울 좌표범위 검사
- 원본 ID: OSM way ID로 중복 제거

공사 선형이 없으므로 도로를 향한 외벽을 선택할 수 없다. `receptor_lat`, `receptor_lon`, `receptor_height_m`은 모두 비워 두었고 `receptor_point_status=deferred_no_construction_alignment`다. 확정 외벽 수음점과 실제 측정 수음점은 모두 0개다.

## 9. M1 연계 가능 범위

건물 폴리곤과 중심점은 탐색·현장조사 계획에는 사용할 수 있다. 다음 용도로는 사용할 수 없다.

- 건물 중심점을 실제 측정 수음점으로 사용
- 주소점 거리를 공사장-수음점 거리로 사용
- 공식 geometry 또는 대표점 생성
- 공식 현장소음 예측

따라서 공식 두 공사구간의 `geometry=null`, M1 공식 계산 `deferred`, 실측 검증 `not_evaluable`을 유지한다. 별도 시뮬레이션에서도 사용자가 명시적으로 가정 외벽점과 높이를 선택해야 한다.

## 10. 출력 파일

- `data/raw/building_footprints/`: 로컬 원본 4개 및 출처 메타데이터
- `data/processed/residential_buildings.geojson`: OSM 주거태그 폴리곤 10개
- `data/processed/residential_buildings.csv`: 건물 속성 10행
- `data/processed/receptor_candidates.csv`: A 구간 후보 관계 10행
- `data/processed/receptor_coverage_report.json`: 성공·실패·반경별 집계

## 11. 추가로 필요한 자료

1. VWorld GIS건물통합정보의 서울 또는 서대문구 SHP와 원본 CRS 설명
2. 건축HUB 서비스 활용승인 또는 올바른 서비스키 권한
3. 충정로 35-17의 공식 주소 좌표 또는 건물 PK
4. 두 공사구간의 실제 관로 선형 및 일별 작업 위치
5. 건물별 도로면, 층별 주거용도, 수음점 높이
6. 현장 확인 및 동기화 소음측정

현재 결과는 실제 OSM 건물 형상을 이용한 후보 데이터 수집 성과지만, 공식 주거용도와 수음점 검증을 완료한 데이터셋은 아니다.

## 12. 검증 및 Git

기존 162개를 포함한 전체 **172개 pytest**가 통과했다. Python 컴파일과 기존 `/api/health`, M0 `/api/noise/predict` 스모크도 통과했다. 원본별 바이트 수와 SHA-256은 coverage report에 기록한다. 최종 로컬 커밋 해시는 완료 보고에 기록하며 원격 저장소가 없으면 push하지 않는다.
