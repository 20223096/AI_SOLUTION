# 프론트엔드 API 확장 계약 v3.2

검증일: 2026-10-26. v3.1의 27개 operation과 요청·응답은 그대로 보존하고 S2 주소 대표점 조회 1개를 추가한다. 총 28개 operation이다. 규범 스키마는 `docs/openapi.json`, 생성 타입은 `frontend-contract/types/api.d.ts`다.

## 신규 operation

`POST /api/locations/address-coordinate`

```ts
type Request = components["schemas"]["AddressCoordinateRequest"];
type Response = components["schemas"]["AddressCoordinateResponse"];
```

요청:

```json
{
  "address": "서울특별시 서대문구 연세로2나길 20",
  "selected_address_id": null
}
```

`status=selection_required`이면 `candidates[].address_id`를 사용자가 고른 뒤 같은 주소와 `selected_address_id`로 재요청한다. `resolved`여도 `user_confirmation_required=true`이면 정규화 또는 사용자 선택 결과이므로 화면에서 확인을 받아야 한다.

## 상태와 HTTP 코드

| HTTP | status | 프론트엔드 처리 |
|---|---|---|
| 200 | `resolved` | `map_coordinate`를 주소 핀으로 표시 |
| 200 | `selection_required` | 후보 선택 UI 표시, 좌표로 승격 금지 |
| 200 | `not_found`, `invalid_selection` | 주소 수정 또는 재선택 |
| 422 | FastAPI validation error | 입력 길이·형식 수정 |
| 502 | `provider_error`, `invalid_provider_coordinate` | 공식 서비스 응답 오류 안내 |
| 503 | `configuration_error`, `provider_auth_error`, `provider_rate_limited`, `provider_timeout` | 잠시 후 재시도 또는 운영 설정 점검 |

`source_coordinate`는 공식 API 원좌표 EPSG:5179, `map_coordinate`와 `official_address_coordinate`는 프론트엔드용 EPSG:4326이다. `construction_geometry`, `demo_geometry`, `residential_facade_receptor`는 Sprint 23에서 `null`이다. 공식 주소 핀을 공사 중심·선형 또는 외벽 수음점으로 사용하면 안 된다.

전체 실제 응답은 `frontend-contract/examples/s2-address-coordinate.json`을 사용한다. v3.1 계약은 `FRONTEND_API_CONTRACT_v3_1.md`에 보존한다.
