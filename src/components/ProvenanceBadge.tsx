import type { ProvenanceStatus } from '../api/notices'

// PRD 연동 가이드 7절: 출처 배지. missing은 값처럼 보이지 않게 구분한다.
const LABEL: Record<ProvenanceStatus, string> = {
  verified_public: '검증된 공개자료',
  user_provided: '사용자 입력',
  assumed: '가정값',
  derived: '계산값',
  missing: '미확인',
}

export function ProvenanceBadge({ status }: { status: ProvenanceStatus }) {
  return <span className={`badge prov-${status}`}>{LABEL[status] ?? status}</span>
}
