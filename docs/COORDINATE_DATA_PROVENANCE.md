# 좌표 데이터 출처와 승격 규칙

검증일: 2026-10-26

## 데이터 계층

| 데이터 | 출처 | 좌표계 | Sprint 23 상태 | 허용 용도 |
|---|---|---|---|---|
| 공식 주소 좌표 | 행정안전부 주소기반산업지원서비스 좌표제공 검색 API | 원본 EPSG:5179, 변환 EPSG:4326 | 실제 조회 | S2 주소 핀·주소 확인 |
| 실제 공사 구간 geometry | 현장/설계 검증 자료 필요 | 미정 | `null` | 사용 금지 |
| 실험용 시연 geometry | 별도 실험 자산 | 자산별 명시 | API 응답에서는 `null` | 실제 위치로 표시 금지 |
| 실제 주거 외벽 수음점 | 현장조사·건물 검증 필요 | 미정 | `null` | 소음 현장 예측에 사용 금지 |

공식 좌표의 `entX`, `entY`는 도로명주소 건물 출입구 대표점이다. 공사 중심점, 굴착 선형, 장비 위치, 수음점이 아니다. 따라서 주소 좌표 확보는 M0/M1의 `validation_status`, 현장 정확도 또는 법적 판단을 개선하지 않는다. API는 이를 `site_accuracy_status=not_validated`와 고정 limitation으로 표현한다.

## 변환과 추적성

1. 주소검색 API `addrLinkApi.do`로 공식 주소와 5개 코드(`admCd`, `rnMgtSn`, `udrtYn`, `buldMnnm`, `buldSlno`)를 얻는다.
2. 별도 승인을 받은 좌표제공 API `addrCoordApi.do`에 5개 코드를 전달한다.
3. 반환된 UTM-K(GRS80) 좌표를 EPSG:5179로 기록한다.
4. 백엔드의 역 Transverse Mercator 변환으로 EPSG:4326 경위도를 생성한다.
5. 원좌표와 변환좌표를 모두 응답해 변환 이력을 보존한다.

주소 문자열만으로 좌표 API를 직접 호출하거나, 검색 후보가 여러 개인데 첫 후보를 자동 채택하지 않는다. 다중 후보는 `selection_required`; 결과 없음은 `not_found`; 공급자 좌표가 숫자가 아니거나 유효한 경위도로 변환되지 않으면 `invalid_provider_coordinate`다.

## 비밀·운영 정책

- `.env`는 Git ignore 및 비추적 상태이며 키 값은 로그·문서·예시에 기록하지 않는다.
- 검색 키와 좌표 키는 `SecretStr`로 로드하고 공급자 POST body에만 전달한다.
- 주소기반산업지원서비스 공식 안내상 고정 호출 횟수 제한은 없지만 과도한 호출은 IP 차단 대상이 될 수 있다. 클라이언트는 429를 `provider_rate_limited`로 처리한다.
- 네트워크 타임아웃 기본값은 5초이고 `SHH_JUSO_TIMEOUT_SECONDS`로 0초 초과 30초 이하에서 조정한다.

공식 참고: [주소기반산업지원서비스](https://business.juso.go.kr/), [좌표 API와 검색 API 분리 안내](https://www.juso.go.kr/addrlink/qna/qnaDetail.do?bulletinRefSn=134424), [UTM-K(GRS80) 좌표계 안내](https://business.juso.go.kr/addrlink/qna/qnaDetail.do?bulletinRefSn=128137).
