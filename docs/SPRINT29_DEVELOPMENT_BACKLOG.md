# Sprint 29 개발 백로그

근거: Sprint 28 PRD 감사 및 정량 검증

목표: 해커톤 제출 전에 “API가 연결됨”을 “기획 기능이 구현됨”으로 과장하지 않으면서, 핵심 결손을 가장 작은 검증 가능한 단위로 해소한다.

## 우선순위 원칙

1. 계산 결과의 의미가 잘못 전달될 위험을 먼저 제거한다.
2. 추천이 실제 제약·데이터를 사용한다는 증거를 만든다.
3. 전역 최적화나 AI라는 명칭은 실제 구현과 대조 실험이 생긴 뒤에만 사용한다.
4. 기존 9월 11일 원 일정, 10월 7일 13.72→13.20, 1,620 receptor-minutes를 회귀 기준으로 고정한다.
5. 모든 신규 데이터는 `official / observed / user_confirmed / assumed / missing` provenance와 계산 사용 여부를 분리한다.

## P0 — 해커톤 제출 전 필수

### P0-1. 제품 문구와 지표 정의 정합화

작업:

- UI와 발표자료에서 solver를 `15분 offset 전수열거`로 표기하고 OR-Tools/전역 최적 표현을 제거한다.
- S4/S6의 65 dB를 “PoC 분석 임계값”으로 고정 표기한다.
- 내부 Quiet Window와 주민용 “공사 없는 시간”의 서로 다른 정의를 라벨에 반영한다.
- S7 `high_noise` checkbox가 담당자 분류임을 표시하거나 계산 결과와 연결한다.
- S-DoT 미합성, 대표점 거리, 9/11 가정 overlay를 후보 화면에서도 확인 가능하게 한다.

완료 기준:

- 화면별 provenance/caveat 스냅샷 테스트.
- “실제 피해 감소”, “법적 충족”, “S-DoT 실시간 결합”, “AI 최적해” 금지 문구 검토.

### P0-2. 추천 목적과 기존소음 중첩의 정책 결정

문제: 9/11에는 중첩이 360→0으로 줄어도 현 목적함수가 이를 사용하지 않아 offset-0이 유일한 Pareto다.

작업:

- `existing_noise_overlap_receptor_minutes`를 독립 Pareto 축으로 넣을지, 단지 설명 지표로 유지할지 제품 정책을 명시한다.
- 포함할 경우 검증된 이벤트와 assumed 이벤트를 별도 축/실험으로 분리한다.
- 동일 scenario에서 event overlay on/off가 가능한 실험 입력을 추가한다.

완료 기준:

- 9/11 통제 실험에서 목적축, 후보 frontier, 추천 이유가 수치와 일치.
- assumed event가 공식 관측처럼 표시되지 않음.

### P0-3. 정량 baseline 구현

문제: “단순 빈 시간 추천 vs Noise Slot” 비교가 현재 불가능하다.

작업:

- deterministic baseline을 `earliest feasible`, `minimum schedule change`, `minimum calendar overlap` 중 명시적으로 정의한다.
- 동일 후보 집합·동일 hard constraints·동일 배경에서 Noise Slot과 비교한다.
- A~F 공통 결과 schema: continuous high, quiet, Impact, overlap, change, violations, candidate/Pareto counts.

완료 기준:

- 날짜 9/11과 10/7의 재현 가능한 비교 테스트와 보고서 fixture.
- 결과가 같거나 악화돼도 그대로 노출.

### P0-4. 지리·수음점 정확성 경계 강화

작업:

- JUSO 대표 좌표를 공사 선형이나 외벽 수음점으로 사용하지 못하도록 타입/validation 경계를 유지한다.
- 실제 공사 geometry와 주거 외벽 receptor가 없으면 M1 현장 계산을 `deferred/not_evaluable`로 반환한다.
- 학교/병원 “300 m 이내”는 실제 좌표거리로 판정하고, 좌표가 없으면 적용하지 않는다.
- 토지용도 0행 상태에서 주거지역 판정을 생성하지 않는다.

완료 기준:

- 안/밖 경계, CRS 불일치, 대표점 오용, 좌표 결측 테스트.
- 기존 공식 대표점 결과는 별도 reference simulation으로만 유지.

### P0-5. 회귀 및 재현성 gate

작업:

- 기존 backend 269, frontend 13, production build를 CI 최소 gate로 설정한다.
- 9/11 offset-0, 10/7 13.72→13.20, 1,620 receptor-minutes golden assertion 유지.
- 생성 보고서의 실행 커밋·profile·policy·scenario ID를 기록한다.

완료 기준:

- clean clone에서 테스트/빌드/정량 스크립트 1회 실행 성공.
- 보고서 수치가 fixture와 자동 대조됨.

## P1 — 핵심 기능 보강

### P1-1. 일반 일정 최적화 및 OR-Tools 도입 여부 결정

현재 offset 열거를 기준선으로 보존한 뒤 다음을 별도 solver로 구현한다.

- 공정별 시작변수, 선후관계, 자원용량, 장비 허용시간, 도로점용, 당일복구, 다일 분할.
- CP-SAT을 실제 호출하고 solver status, bound, timeout을 응답한다.
- 동일 입력에서 enumeration과 CP-SAT 결과/시간을 비교한다.
- multi-objective는 가중합을 숨기지 말고 epsilon-constraint 또는 반복 solve로 Pareto를 생성한다.

완료 기준: OR-Tools import 존재가 아니라 solver log/status와 비자명한 공정 재배치 테스트가 있어야 한다.

### P1-2. 자연어 제약 구조화

- schema-first extraction: 원문 span, 값, 단위, confidence가 아니라 `confirmation_required` 상태를 저장.
- 장비 규격/대수/허용시간, 점용시간, 고정작업, 선후관계, 당일복구를 지원.
- mock/LLM/user-confirmed를 분리하고 사용자가 승인하기 전 optimizer에 넣지 않는다.
- prompt injection, 모순 제약, 누락값, PDF OCR 실패 테스트.

완료 기준: “14시 이전 시작 불가” 같은 표현이 evidence와 함께 구조화되고 승인 후에만 제약으로 작동.

### P1-3. 공공 일정의 실제 반영 가능성 확보

- 건설알림이 사업기간과 실제 일일 작업시간을 구분.
- 문화행사 시간 문자열 정규화와 음향정보 부재를 분리.
- 수거 일정은 공식 시간 자료가 없으면 assumed fixture로만 유지.
- 검증된 time+dB가 없는 일정은 hard conflict 또는 acoustic synthesis로 승격하지 않는다.

완료 기준: calendar-only, constraint-eligible, acoustic-eligible의 세 상태 테스트.

### P1-4. 주민 신고 피드백 최소 기능

- 개인정보를 분리한 complaint 입력, 위치/시간/유형, moderation/status schema.
- 원시 민원 수를 곧바로 물리 dB로 바꾸지 않고 별도 planning signal로 사용.
- 추천 재실행 시 사용된 신고 snapshot/version과 공개 제외 정책 기록.

완료 기준: 접수→승인→별도 목적축/제약 반영→감사로그; 공개 API에 개인정보 미노출.

### P1-5. 원인 기여도

- receptor-slot별 source energy contribution과 총합 검산.
- background, verified event, assumed event, 각 장비를 구분.
- Impact attribution은 비선형/clamp 때문에 단순 점수 비율로 나누지 말고 방법을 명시.

완료 기준: source 에너지 합이 construction contribution과 수치 허용오차 내 일치하고 missing source는 0으로 대체하지 않음.

## P2 — 시간이 남으면 개발할 확장 항목

- 실제 공사 선형/GIS와 건물 외벽 receptor 자동 생성 및 현장 확인 workflow.
- 현장 LAeq, 장비 가동로그, 기상/차폐 입력을 통한 calibration과 holdout validation.
- S-DoT metric·교정·설치 위치가 확인된 뒤 analysis-only에서 적합한 사용 범위로 승격.
- 확률분포 기반 불확실성/Monte Carlo 및 confidence interval. 현재 deterministic range와 혼동 금지.
- 민감도 지도: 실제 좌표, provenance, 계산 불가 영역을 함께 표시.
- 휴일·학교 수업시간·기관별 학사일정의 검증된 calendar adapter.
- 브라우저 새로고침 후 서버 workflow 복원과 S8 직접 URL routing.
- 안내문 생성형 AI는 사실 whitelist와 publication validation을 먼저 구현한 뒤 선택적으로 추가.

## 권장 Sprint 29 순서

1. P0-1 지표/표현 정합화
2. P0-2 중첩 목적 정책 및 on/off 실험
3. P0-3 단순 baseline과 자동 정량 리포트
4. P0-4 실제 공간 판정 경계
5. P0-5 CI/golden gate
6. P1-1 OR-Tools solver spike와 go/no-go 결정
7. P1-2 자연어 제약 승인 workflow
8. P1-3 공공 일정 eligibility
9. P1-5 원인 기여도
10. P1-4 주민 신고 피드백

## DoD 공통 체크리스트

- 기능에 대응하는 API, 구현 함수, 단위 테스트, 실패 테스트가 모두 존재한다.
- official/observed/assumed/missing과 실제 계산 사용 여부가 응답에 포함된다.
- 법적 dB, 내부 65 dB threshold, Impact score를 서로 다른 필드와 라벨로 유지한다.
- 후보 0개/1개/다수, 모두 위반, 결측 source, stale snapshot을 검증한다.
- 기존 세 golden 수치와 backend/frontend 회귀가 유지된다.
- 현장 검증 전 정확도·피해감소를 주장하지 않는다.
