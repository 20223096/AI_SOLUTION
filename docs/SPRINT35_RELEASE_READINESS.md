# Sprint 35 최종 대조 및 배포 준비

검증 기준 커밋: `7fa4c34f294a1dcac2149e5594bdd8a10098c98c`

## 기획서 기능 대조

| 기능 | 판정 | 실제 경로 | 검증 |
|---|---|---|---|
| 신고서 AI 추출·사용자 확인 | 완료 | `POST /api/notices/extract`, `/extract-file`; `extractor.py`, S1/S2 | Structured Outputs/원문 evidence 및 담당자 확인 테스트 |
| 장비 음향파워·거리감쇠·배경소음 | 부분 완료 | `/api/noise/predict`; `acoustics.py`, `background.py` | 공식 참조·대표 거리·관측 대표 배경 혼재. 현장 geometry/장비 미확보 |
| 민감도 가중치·지도 | 부분 완료 | `/api/public-data/catalog`; `sensitivity.py`, `SensitivityMap.tsx` | 실제 좌표와 가정 수음점 분리. 수업시간·공휴일 전용 규칙 없음 |
| Noise Impact Score | 완료(PoC) | `/api/impact/calculate`; `impact.py` | 계산 점수이며 실측·피해 감소 수치 아님 |
| CP-SAT Noise Slot 추천 | 완료(PoC) | `/api/prd/recommendations/constraint-filtered`; `advanced_optimizer.py` | `cp_sat_v2`, 15분 슬롯, 탐색 후보 집합 기준 |
| Pareto 후보 | 완료 | 동일 추천 API; `pareto.py` | 다축 비지배 후보 테스트 및 정량 재현 |
| 전후 비교 | 완료 | `POST /api/schedules/compare`; S6 | 동일 수음점·규칙, 변화 없음도 표시 |
| 주민 안내문·확정·공개 | 완료(PoC) | staff draft POST/PUT/confirm, public GET; S7/S8 | snapshot/version/revision 및 공개 gate 검증 |
| 공공데이터·가정 구분 | 부분 완료 | `/api/public-data/catalog`, provenance badge | 확인된 출처는 표시. 일부 거리·민감도·이벤트는 가정 |

## 고정 baseline 재현

명령: `PYTHONPATH=backend python3 scripts/run_sprint29_experiments.py`

| 날짜 | 원안 | offset_v1 | cp_sat_v2 | CP-SAT 후보/Pareto |
|---|---:|---:|---:|---:|
| 2026-09-11 | 7.36 | 7.36 (개선 없음) | 7.36 (개선 없음) | 495 / 35 |
| 2026-10-07 | 13.72 | 13.20 | 13.12 | 495 / 18 |

위 값은 `road_traffic_observed_profile`, 동일 fixture, 15분 grid의 모델 점수다. 실제 주민 피해 감소를 나타내지 않는다. 현재 S1~S8 UI의 분석일은 2026-09-11 고정이므로 화면의 7.36과 개선 없음은 baseline과 일치한다. 2026-10-07 값은 비교실험 API/스크립트 결과이며 일반 입력 UI에서 날짜를 바꿔 표시하는 기능은 없다.

## 데모와 배포

- mock: `./scripts/run_mock_demo.sh`로 매 실행 독립 저장소를 사용한다. 키 불필요.
- LLM: backend 전용 provider/model/key 필요. mock과 별도 프로세스로 실행한다.
- 개발 CORS: Vite proxy로 same-origin. 정적 배포는 정확한 frontend origin을 `SHH_CORS_ALLOWED_ORIGINS`에 등록한다.
- staff API: 현재 host allow-list만 있으며 사용자 인증·권한·감사 주체가 없다. 인터넷 공개 배포의 차단요인이다.
- 비밀값: `.env`, `*.local`은 Git 제외. 브라우저에는 `VITE_SHH_API_BASE_URL` 외 비밀값을 넣지 않는다.
- 실제 배포 필요 항목: backend compute/HTTPS, frontend hosting, 영속 저장소, 도메인·CORS, staff 인증/RBAC, secrets manager, 로그·모니터링, 백업, JUSO/LLM/공공데이터 API 권한과 사용료·쿼터 검토.
- 새 clone 검증에서 FastAPI 0.162.0의 router introspection과 Pydantic 2.14.1의 OpenAPI schema 변경을 확인해, 계약 테스트가 검증된 FastAPI 0.135.3/Pydantic 2.12.5로 버전을 고정했다.

## 알려진 제한과 우선순위

1. staff API 인증/RBAC과 운영용 영속 DB를 먼저 구현한다.
2. 배포 origin/CORS 및 secrets manager를 구성한다.
3. 실제 공사 geometry·외벽 수음점·현장 장비/배경소음 검증 데이터를 확보한다.
4. 발표 UI에서 10/7 고정 비교실험을 별도 읽기 전용 화면으로 제공할지 결정한다.
5. 학교 수업시간·공휴일 정책은 근거와 승인 후에만 계산 엔진에 추가한다.
