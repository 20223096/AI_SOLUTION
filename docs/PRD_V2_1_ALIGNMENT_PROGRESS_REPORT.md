# 쉿간표 19차 PRD v2.1 정합성 진행 보고서

작성 기준: 2026-10-24 저장소 구현과 이번 요청에 제공된 공식 F/S 명칭. 이 문서는 내부 개발 진행 보고서이며 프론트엔드 확정 계약서가 아니다. 기존 `FRONTEND_API_CONTRACT_v2_1.md`는 변경하지 않았다.

## 1. PRD 원문 기준 F1~F12 재매핑

판정은 공개 FastAPI 계약에서 바로 사용할 수 있는지를 기준으로 한다. 이번에 추가한 `models/prd_v2_1.py`와 `services/prd_v2_1.py`는 검증용 내부 코드이며 아직 공개 API 구현으로 세지 않는다.

| ID | 공식 기능명 | 상태 | 실제 근거 | 남은 차이 |
|---|---|---|---|---|
| F1 | 신고서 등록 | `partially_implemented` | `api/notices.py`, `models/domain.py:ExtractRequest`, `/api/notices/extract`, `/extract-file` | 추출만 하며 저장·수정·신고 ID 수명주기가 없다. 신규 계획 필드는 공개 요청에 없다. |
| F2 | AI 신고서 정리 | `partially_implemented` | `services/extractor.py`, notice API 테스트 | mock/선택적 LLM 추출이며 장비 규격·대수·허가시간·근거를 신뢰 가능한 원문 필드로 확정하지 않는다. |
| F3 | 소음 예측 | `implemented` | `api/noise.py`, `services/prediction.py`, `services/m1_acoustics.py`, M0/M1 테스트 | M0/M1의 적용 조건과 provenance를 화면에 유지해야 한다. |
| F4 | 민감도 반영 점수 | `partially_implemented` | `services/sensitivity.py`, `services/impact.py`, `test_noise_objectives.py` | 공개 기본은 가산식. PRD 최댓값 정책은 이번 차수 내부 실험만 있고 API 계약이 아니다. |
| F5 | 기존 소음 일정 표시 | `partially_implemented` | public-data catalog, `existing_events.json`, prediction의 기존 이벤트 중첩 지표 | 공식 행에는 일일 공사시간·음향값이 없다. 일부 음향 오버레이는 명시적 시연 가정이다. |
| F6 | Noise Slot 추천 | `partially_implemented` | `api/schedules.py`, `services/optimizer.py` | 15분 단위 정확 열거 추천은 있으나 신고서별 장비 허용시간·도로점용·고정 작업·복구 제약이 공개 optimizer 입력에 연결되지 않았다. |
| F7 | 조정안 비교 | `implemented` | optimize의 가변 Pareto 후보·추천 이유·진단, optimizer/scoring 테스트 | 비지배 후보가 3개 미만이어도 허위 카드를 만들지 않는다. 3개 고정 UI 정책은 기획 결정 필요. |
| F8 | 조정 전후 비교 | `implemented` | `/api/schedules/compare`, `services/metrics.py` | 현재 확정된 지표 범위에서 사용 가능하다. |
| F9 | 주민 안내문 생성 | `not_implemented` | route/model/service 없음 | 초안 입력, 승인·확정 상태, 템플릿과 책임 주체 필요. |
| F10 | 주민 화면 | `not_implemented` | 주민 전용 공개 view/API 없음 | 공개 범위, 위치 정밀도, 개인정보, 캐시 정책 필요. |
| F11 | 조건 직접 입력(자연어) | `not_implemented` | 기존 notice 추출은 조건 변경 API가 아님 | 해석 결과 diff와 사용자 승인 후 적용하는 2단계 계약 필요. |
| F12 | 법 기준 확인 | `not_implemented` | 계산 응답의 `legal_assessment`는 결론을 제공하지 않음 | 검증된 기준표 출처·적용 조건이 필요. 현장 측정 없이 적합/위반 자동 판정 금지. |

집계: `implemented` 3개(F3, F7, F8), `partially_implemented` 5개(F1, F2, F4, F5, F6), `not_implemented` 4개(F9~F12).

## 2. S1~S8 화면 연결성

| 화면 | 상태 | 현재 사용 가능한 API/필드 | 부족 항목 |
|---|---|---|---|
| S1 신고서 등록 | 부분 가능 | notice extract 결과 | 저장/수정, 고급 제약 필드, 원문 단위 근거 확정 |
| S2 소음 민감도 지도 | 부분 가능 | scenario의 수음점 좌표·유형·거리, prediction 민감도 | 모든 수음점의 검증 좌표와 PRD 정책 확정 |
| S3 시간대별 소음 일정 | 부분 가능 | M0 prediction 슬롯, public-data catalog | 공식 기존 공사의 일일 운전시간·소음 부재를 `null`로 표시해야 함 |
| S4 Noise Slot 추천 | 부분 가능 | schedule optimize 후보·지표 | 신규 신고서 제약을 optimizer에 연결할 공개 계약 |
| S5 조정안 고르기 | 바로 가능 | Pareto 후보, 추천 이유, infeasible 사유 | UI가 후보 3개 고정을 요구하지 않아야 함 |
| S6 조정 전후 비교 | 바로 가능 | schedule compare | 확정된 지표만 표시 |
| S7 확정 및 안내문 | 불가 | 확정/안내문 API 없음 | F9와 승인 수명주기 |
| S8 주민 화면 | 불가 | 주민 전용 API 없음 | F10 공개 projection |

## 3. 신고서 모델 및 작업시간 제약

이번 차수에는 공개 계약과 분리한 `PRDNoticePlanningInput`을 추가했다. 전체 공사창, 장비 종류·규격·선택 모델명·하루 최대 대수·필요 사용시간·장비별 허용창, 도로굴착/점용 허가창, 고정 작업, 당일 복구, 완료일, 조정 불가 조건, 원문 근거와 provenance를 표현한다. 값은 `field_measured`, `official_document`, `user_provided`, `assumed` 중 하나로 명시하며 LLM 결과를 공식값으로 승격하지 않는다.

`validate_prd_schedule`은 **명시적으로 입력된 경우에만** 전체 공사창, 장비창, 점용 허가창, 변경 불가 작업, 선후행, 당일 복구, 완료일을 검사한다. 위반 시 `feasible=false`와 위반 코드를 반환한다. 07~18시 또는 08~17시를 보편 법 규칙으로 만들지 않았다. 현재 공개 optimizer는 기존 시나리오의 원 작업창, 고정 일정, 금지창, 순차 작업, 일일 최대시간만 강제하며 OR-Tools가 아닌 0~120분 범위의 15분 정확 열거를 사용한다. 내부 validator를 공개 optimizer에 연결하려면 요청/응답 모델과 오류 계약 승인 후 별도 API 또는 버전 필드가 필요하다.

## 4. 계산 정책 차이

- M0는 기존 단순 거리감쇠/합성 경로, M1은 좌표·활동시간·보정 상태를 받는 선택형 물리 모델이다. PRD 식과 동일하다고 간주하지 않는다.
- 장비 에너지 합산과 배경소음 합성은 데시벨 에너지 합산이다. M1 `high`는 현재 자료의 최댓값이다. PRD의 상위 10%와 다르며 표본 포함/제외 및 분위수 보간 정의 전에는 추가 계산하지 않는다.
- 공개 민감도 `legacy_v1`은 시간 기본 가중치에 상황 adjustment를 더한다. 학교·병원 및 대학 시험기간 adjustment는 검증된 피해계수가 아니라 가정이다.
- 내부 실험 `prd_max_v2_1_experimental`은 겹치는 맥락에서 하나의 최댓값만 사용한다. 1.1/1.3/1.5를 실행했으며 기본 API 파라미터나 OpenAPI에는 노출하지 않았다.
- 9/11 `final-demo-congestion` 실험에서 세 배수 모두 추천 `offset-0`, Pareto `offset-0`, 전체 후보 순위가 유지됐다. 추천안의 민감 수음점 노출은 1,620 receptor-minutes, 일정 변경량은 0분으로 동일했다. 가중 노출은 각각 1,782/2,106/2,430으로 변했다. 이는 피해 검증값이 아닌 정책 민감도 결과다.
- 65 dB는 PoC 분석 임계값이며 법정 규제기준이 아니다. 현장 측정 및 법 적용 조건 없이 위반/적합 결론을 내리지 않는다.

## 5. 기존 소음과 동시 고소음

9/11 fixture는 신규 시연 공사(가정), 기존 공사 사업기간(공식), 문화행사 시간(공식), 폐기물 수거(가정)를 분리한다. 공식 공사의 일일 가동시간과 음향값은 없으므로 08~17시 실제 운전 또는 공식 동시 소음을 주장할 수 없다. `final-demo-congestion`의 07~09시 82 `Lp_dBA`는 별도 가정 오버레이이며, 모델 지표 `existing_noise_overlap_receptor_minutes`는 이 가정 안에서만 해석한다.

## 6. F9~F12 설계 및 우선순위

| 우선순위 | 기능 | 제안 계약 | 기존 데이터 재사용 | 난이도/영향 | 선결 결정 |
|---|---|---|---|---|---|
| P0 | F9 안내문 초안 | 확정 후보 ID + 공개 가능한 일정/주의사항 → `draft`, 근거, 승인상태. 승인 전 `final` 금지 | scenario, candidate, provenance | 중/새 API, 핵심 계산 무변경 | 승인 주체·문구·배포 채널 |
| P0 | F12 법 기준 참고 | 버전된 기준표와 출처/적용조건만 조회. 분석결과와 별도 표시 | 없음 또는 검증 기준표 | 중/새 읽기 API | 관할·공종·시간별 공인 원문, 법무 검토 |
| P1 | F10 주민 조회 | 승인된 notice/candidate의 최소 공개 projection | F9 승인 결과 | 중상/새 공개 API·보안 검토 | 위치 정밀도·개인정보·공개기간 |
| P2 | F11 자연어 조건 | 자연어 → 구조화 diff(`proposed`) → 사용자 승인 → 적용/재최적화 | PRD planning model | 상/새 2단계 API·감사로그 | 허용 명령, 충돌 정책, 승인 권한 |

## 7. 기획팀 결정 필요 항목

1. 시연 필수 화면과 F9~F12 제외/포함 범위.
2. PRD 최댓값 정책의 적용 대상과 1.1/1.3/1.5 중 확정값 또는 수음점별 값.
3. 상위 10%의 모집단, 최소 표본수, 분위수 계산법.
4. Pareto 카드가 3개 미만일 때 UI 처리. 백엔드는 후보를 복제하지 않는다.
5. 신고서 저장 수명주기와 사용자 제공/LLM 추출/공식 문서 값의 승인 규칙.
6. 법 기준표의 공인 출처·관할·적용조건과 법무 검토 책임.
7. 9/11 공사 일일시간·장비·음향값을 실제값으로 표시하려면 필요한 추가 원자료.

## 8. 최종 계약 발행 판정

**발행 불가.** F/S 재매핑과 내부 모델·실험·fixture 검증은 완료했지만, 시연 포함 범위에 대한 기획 결정, 공개 API 구현, Pydantic 응답 확정, OpenAPI/TypeScript 재생성 및 신규 API HTTP 검증 조건이 충족되지 않았다. 따라서 새 최종 계약서를 만들지 않았고 기존 v2.1 정본을 그대로 유지한다.

검증 근거: `backend/tests/test_prd_v2_1_alignment.py`, 기존 전체 회귀 테스트, `docs/DEMO_2026_09_11_DATA_VALIDATION.md`.
