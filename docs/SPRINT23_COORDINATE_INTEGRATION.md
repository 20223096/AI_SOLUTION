# Sprint 23 주소 좌표 통합 결과

검증일: 2026-10-26
기준 커밋: `5d535e1`

## 구현 결과

- 프로젝트 루트 `.env`를 실행 디렉터리와 무관하게 읽도록 고정했다. `JUSO_SEARCH_API_KEY`, `JUSO_COORD_API_KEY`는 Pydantic `SecretStr`이며 실제 값은 출력하지 않았다.
- `.env`는 `.gitignore`에 포함되고 Git index에는 없다.
- 기존 주소검색과 별도인 승인 좌표 API를 서버 측 2단계로 연결했다.
- `POST /api/locations/address-coordinate` 1개를 v3.2로 추가했다. 기존 27개 operation은 유지한다.
- 신고서 `notice.location` 또는 사용자 입력 주소를 요청의 `address`로 그대로 전달할 수 있다. S1 응답 스키마는 변경하지 않았다.
- 실제 공사 geometry, 시연 geometry, 주거 외벽 수음점은 주소 대표점과 분리해 `null`로 유지한다.

## 공식 API 계약 확인

| 구분 | 확인값 |
|---|---|
| 주소검색 | `POST https://business.juso.go.kr/addrlink/addrLinkApi.do` |
| 좌표제공 | `POST https://business.juso.go.kr/addrlink/addrCoordApi.do` |
| 검색 필수값 | `confmKey`, `currentPage`, `countPerPage`, `keyword`, `resultType=json` |
| 좌표 필수값 | `confmKey`, `admCd`, `rnMgtSn`, `udrtYn`, `buldMnnm`, `buldSlno`, `resultType=json` |
| 공통 응답 | `results.common.errorCode`, `errorMessage`, `totalCount` |
| 좌표 응답 | `results.juso[].entX`, `entY` 및 주소 코드 |
| 원좌표계 | UTM-K(GRS80), EPSG:5179 |
| 지도 좌표계 | WGS 84, EPSG:4326 |
| 사용량 | 고정 횟수 제한 없음; 과도 호출 시 IP 차단 가능 |

## 실제 호출 결과

승인 키로 공식 API를 실제 호출했다. 키와 HTTP body는 기록하지 않았다.

| 사례 | 입력(공개 주소/비민감 테스트 문자열) | 실제 결과 |
|---|---|---|
| 정상 | 서울특별시 서대문구 연세로2나길 20 | `resolved`, exact, EPSG:5179 → EPSG:4326 |
| 결과 없음 | 서울특별시 없는구 없는로 999999 | `not_found` |
| 다중 후보 | 서울특별시 서대문구 연세로 | `selection_required`, 10 candidates |
| 잘못된 주소 | `@@@` | 공급자 오류를 `provider_error`로 격리 |
| 인증 오류 | 의도적으로 잘못된 좌표 키 | `provider_auth_error` |
| 타임아웃 | 1ms 제한으로 강제 | `provider_timeout` |
| 요청 제한 | 실제 차단은 유발하지 않음 | Mock HTTP 429 → `provider_rate_limited` |
| 표준화 | 정상 주소 | 공식 괄호 동명이 포함된 도로명주소 반환 |

정상 실제 결과의 전체 공개 좌표 응답은 `frontend-contract/examples/s2-address-coordinate.json`에 있다. 주소 핀은 공식 출입구 대표점일 뿐 현장 geometry가 아니다.

## 회귀 결과

- 신규 단위·HTTP 계약 테스트: 정상, 없음, 다중 후보/선택, 인증, 시스템 오류, 타임아웃, 429, 잘못된 좌표, 키 로그 비노출, CORS, OpenAPI, 28-operation 호환성.
- 기존 9/11·10/7 및 M0/M1 고정값 테스트를 포함해 `255 passed`를 확인했다(기존 247 + 신규 8).
- OpenAPI 3.1 및 `openapi-typescript@7.10.1` 타입을 재생성한다.
- 공식 주소 좌표만으로 `validated`를 설정하는 경로는 없다.

최종 커밋 해시는 완료 보고에 기록한다.
