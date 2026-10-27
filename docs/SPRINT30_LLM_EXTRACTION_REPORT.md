# Sprint 30 실제 OpenAI LLM 신고서 추출 검증

검증일: 2026-10-27  
기준 커밋: `419aeb77c97b152c68aaddb0b9171c1658ffdeab`

## 결론

`backend/.env`의 LLM 설정은 애플리케이션 설정명 및 허용 provider와 일치했고, API 키 값은 출력하거나 저장소에 기록하지 않았다. 첫 호출은 OpenAI HTTP 요청에는 성공했으나 모델이 요청한 envelope 대신 notice 객체를 직접 반환하여 애플리케이션 파싱이 실패했다. 사용자의 명시적 재호출 요청 뒤 direct notice JSON도 하위 호환으로 수용하도록 최소 수정하고 같은 신고서로 한 번 더 호출했으며, 두 번째 호출은 성공했다.

성공은 OpenAI 연결과 Pydantic 스키마 파싱 성공을 뜻한다. 추출 품질과 S2~S4 입력 완전성까지 모두 충족한다는 뜻은 아니다. 실제 결과에는 장비-작업 연결과 원문 근거 및 출처 상태 오류가 있어 사용자 확인·수정이 필요하다.

## 설정과 호출 방식

| 설정 | 상태 |
|---|---|
| `SHH_EXTRACTOR_MODE=llm` | 설정 및 지원 확인 |
| `SHH_LLM_PROVIDER=openai_compatible` | 설정 및 유일 허용값과 일치 |
| `SHH_LLM_MODEL=gpt-4.1-mini` | 설정 확인 |
| `SHH_LLM_BASE_URL=https://api.openai.com/v1` | 설정 확인 |
| `SHH_LLM_API_KEY` | 값 있음, 값 자체는 미출력·미기록 |

호출은 `POST /v1/chat/completions` 한 건, Bearer 인증, `temperature=0`, JSON mode로 수행한다. 자동 재시도는 없다. 첫 파싱 실패 뒤 사용자가 재호출을 명시적으로 요청하여 두 번째 호출만 추가했다.

공식 OpenAI 문서상 JSON mode는 유효한 JSON만 보장하며 JSON Schema 준수까지 보장하지 않는다. 이번 첫 실패는 이 제약이 실제로 드러난 사례다. 현재 코드는 모델이 wrapper 또는 notice 객체를 직접 반환하는 두 형식을 모두 Pydantic으로 검증한다. 향후 별도 작업에서는 `json_schema` Structured Outputs 전환을 검토할 수 있으나, 이번 Sprint에서는 기존 도메인 스키마와 API 계약을 크게 바꾸지 않았다.

## 실제 호출 결과

- 결과: 두 번째 호출 성공
- 요청 모델 alias: `gpt-4.1-mini`
- 응답 모델: `gpt-4.1-mini-2025-04-14`
- 입력 토큰: 1,168
- 출력 토큰: 884
- 합계: 2,052
- 인증/결제/모델 접근/요청 형식 오류: 없음
- 첫 호출 오류: `structured_response_parsing`
- 두 번째 호출: Pydantic `ConstructionNotice` 검증 통과

공식 공개 단가인 입력 $0.40/백만 토큰, 출력 $1.60/백만 토큰을 단순 적용하면 두 번째 호출의 추정 비용은 약 **$0.00188**이다. 첫 호출의 usage는 파싱 실패 경로에서 보존되지 않아 전체 두 호출 비용은 산정할 수 없다. 실제 청구액은 계정 청구 내역이 기준이다.

## 필드별 정확도

테스트 원문에는 공사명, 위치, 기간, 전체 작업시간, 굴착기 1대 09:00~11:00, 브레이커 2대 13:00~14:00, 굴착 후 포장 복구, 당일 복구 조건이 명시되어 있다.

| 필드 | 실제 LLM 결과 | 판정 |
|---|---|---|
| 공사명 | 원문과 일치 | 정답 추출 |
| 공사 위치 | 원문과 일치 | 정답 추출 |
| 공사기간 | 시작·종료·원문 모두 일치 | 정답 추출 |
| 작업시간 | 08:00~17:00 | 정답 추출 |
| 장비 종류 | constraints에 굴착기·브레이커 기록 | 부분 정답; task `equipment_id` 연결 누락 |
| 장비 수량 | 굴착기 1, 브레이커 2 | 정답 추출 |
| 특정장비 사용시간 | 두 장비 모두 원문과 일치 | 정답 추출 |
| 작업 순서 | 굴착 → 포장 복구 | 정답 추출 |
| 조정 불가 조건 | 포장 복구 당일 완료 | 정답 추출 |
| 원문에 없는 값 | notice `id`를 공사명으로 생성 | 모델 생성값 |
| 원문 근거 | `field_evidence={}` | 누락 |
| 출처 상태 | 각 필드를 `verified_public`으로 표시 | 잘못 추출; 실제로는 사용자 제공 원문 |

`duration_minutes`는 원문에 작업별 작업시간이 직접 명시되지 않아 null인 것이 안전하다. 반면 굴착기·브레이커가 작업의 `equipment_id`에 연결되지 않은 결과는 S3~S4 계산 진입 전에 S2에서 보완해야 한다.

## Mock 비교

동일 원문에 대한 Mock은 프로젝트명과 위치를 시연용 고정값으로 바꾸고, 기간 및 08:00~17:00 작업시간을 놓쳤다. 장비 종류 일부는 키워드로 찾았으나 수량·장비별 사용시간·당일 복구를 놓쳤고, 120/300분의 고정 duration과 원문과 반대인 브레이커→굴착 순서를 만들었다. 실제 LLM은 명시 필드 정확도가 크게 높았지만, 장비-작업 연결·evidence·provenance는 불완전했다.

## 프론트엔드와 후속 단계 영향

- S1은 `mode=llm`일 때 `AI 추출 · provider / model`을 표시하므로 성공 결과에 “AI 아님”이 노출되지 않는다.
- S1 결과는 표에 표시되며 S2 폼에서 이름·주소·기간·시간·작업·장비를 수정할 수 있다.
- 분류된 API 오류의 `category`와 안전한 message를 프론트가 표시한다. provider 응답 본문이나 키는 표시하지 않는다.
- LLM 응답 자체는 S2 planning-draft 요청 스키마를 통과하지만, 실제 결과의 task `equipment_id`와 duration이 비어 있으므로 **사용자 보완 없이 S3~S4 소음 계산에 사용할 수 있는 완전한 계획은 아니다**.
- S5~S8 계약과 추천 엔진에는 변경이 없다. Chromium 회귀 E2E는 비용·재호출 방지를 위해 mock 추출 모드로 수행했다.

## 변경 범위

- `backend/app/services/extractor.py`: 단일 요청 payload, 안전한 오류 분류, wrapper/direct JSON 호환 파싱, evidence·usage 보존
- `backend/app/api/notices.py`: 분류된 LLM 오류를 안전한 HTTP detail로 변환
- `backend/app/models/responses.py`: LLM evidence·usage 응답 필드 추가
- `backend/tests/test_llm_extractor.py`: 요청, 성공, 오류, 스키마, direct JSON 회귀 테스트
- `src/api/client.ts`, `src/api/api.test.ts`, `src/api/notices.ts`: 오류 표시와 계약 처리
- OpenAPI 및 TypeScript 생성 타입 갱신

CP-SAT, `offset_v1`, 소음 계산, 데이터셋 및 JUSO 설정은 변경하지 않았다.

## 회귀 검증

- 백엔드: 282 passed (기존 목표 274 포함, Sprint 30 신규 테스트 포함)
- 프론트엔드: 15 passed (기존 목표 14 포함, Sprint 30 신규 테스트 포함)
- TypeScript/Vite production build: 성공
- lint: 성공
- Chromium S1~S8 E2E: 1 passed
- E2E 확인: 실제 API 통신, JUSO 주소·좌표, 비공개/공개 gate, 새로고침, 모바일 overflow, 콘솔 오류 없음
- 비밀키: `.env`는 Git ignore 상태이며 tracked 파일에 키를 추가하지 않음

## 남은 한계

1. JSON mode는 스키마 준수를 보장하지 않으므로 strict Structured Outputs 전환 검토가 필요하다.
2. 모델의 `source_provenance=verified_public` 오표기를 서버가 교정하지 않는다.
3. 실제 응답에서 `field_evidence`가 비어도 현재는 성공으로 처리한다.
4. 장비명과 내부 장비 ID, task 연결은 S2 사용자 보완이 필요하다.
5. LLM 성공을 포함한 브라우저 E2E는 호출 횟수 제한 때문에 수행하지 않았고, mock 기반 S1~S8 회귀만 수행했다.
