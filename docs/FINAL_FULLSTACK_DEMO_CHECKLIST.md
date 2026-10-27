# Final Full-stack Demo Checklist

## 실행 전

- [x] 통합 브랜치가 `837864c` 기준인지 확인
- [x] backend `269 passed`
- [x] frontend `13 passed`
- [x] lint 및 Vite production build 성공
- [ ] 유효한 `JUSO_SEARCH_API_KEY`, `JUSO_COORD_API_KEY` 복구
- [ ] 실제 브라우저에서 1440px/모바일 육안 확인

## S1~S8

- [x] S1 텍스트/파일 호출이 실제 API이며 추출 mode 표시
- [x] S2 누락값 보완 전 진행 차단
- [x] S2 주소 다중 후보 자동 선택 금지
- [ ] S2 공식 주소 좌표 실서비스 성공(현재 E0001 인증 실패)
- [x] 주소 대표점과 공사 선형/외벽 수음점 차이 표시
- [x] S3 제약 위반을 서버 응답으로 표시
- [x] S4 `none_feasible`이면 추천 없음 표시
- [x] S5 서버 allow-list 후보만 선택
- [x] S6 동일 기준 전후 비교 API 호출
- [x] S7 snapshot ID/version/revision 검증
- [x] S7 미확정 상태에서 S8 `not_published`
- [x] S7 수정·확정 후 S8 `published`
- [x] S8은 공개 GET만 사용하고 내부 dB/Impact/수음점 미노출
- [x] 일정 변경 시 공개 무효화·재확정 필요

## 데모 문구/수치

- [x] 9월 11일 원 일정 유지
- [x] 10월 7일 Impact `13.72 → 13.20`
- [x] 민감 수음점 노출시간 `1,620 receptor-minutes`
- [x] 실제 피해 감소 입증으로 표현하지 않음
- [x] “조용한 시간”은 실제 정숙 보장이 아닌 일정 기반 표시임을 함께 노출

## 실제 HTTP 재생

```bash
cd frontend-contract/examples
SHH_API_BASE_URL=http://127.0.0.1:5173 \
SHH_WORKFLOW_OUT=/tmp/sprint26-s1-s8-http.json \
python3 verify_s1_s8_workflow.py
```

2026-10-27 실행 결과: 13 steps, selected `offset-60`, snapshot `verified`, 확정 전 `not_published`, 확정 후 `published`. 좌표 단계는 `provider_auth_error`이므로 전체 E2E는 **부분 통과**로 판정한다.
