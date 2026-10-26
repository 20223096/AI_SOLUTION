# Sprint 21 백엔드 진행 보고

## 구현

- 신고서 추출 결과를 nullable PRD 확인 초안으로 변환하는 `POST /api/prd/planning/from-notice` 추가.
- 기존 optimizer 후보를 PRD validator로 검증하고 통과 후보만 조건부 Pareto/추천으로 반환하는 `POST /api/prd/recommendations/constraint-filtered` 추가.
- 요청·응답 Pydantic 모델, 위반 코드, 출처, 정책 버전, 원 일정/후보 적합성, 일정 변경량, Noise Impact, 결측, 추천 없음 사유, 시뮬레이션 상태를 명시.
- 기본 M0/M1 계산, 기존 optimizer, 9/11·10/7 fixture, 기존 25개 API는 수정하지 않음.

## 데이터 경계

- 미확인 신고서 값은 null/결측으로 유지한다.
- 공식 geometry와 공식 주거 외벽 수음점은 계속 null/미확보다.
- 현장 음향 예측은 deferred, 실측 정확도는 not_evaluable이다.
- S-DoT 관측은 맥락 자료이며 음향 합성 입력이 아니다.
- S7/S8 공개 기능은 기획 결정 전까지 비활성이다.

## 프론트엔드 후속 연결

추출 초안 확인 폼, 결측값 입력 UI, 위반 코드별 메시지, 추천 없음 상태, 원 일정/조건부 Pareto 비교, 출처·가정 배지를 연결해야 한다. `recommendable=false` 후보를 추천 카드로 표시하면 안 된다.

## 남은 기획 결정

S7 승인 주체와 공개 가능 상태 전이, S8 공개 범위·위치 정밀도·변경/철회 정책, 공정 분할·병렬화 탐색 허용 여부, 현장별 장비 대수 의미(보유/투입/동시)의 행정 정의가 필요하다.
