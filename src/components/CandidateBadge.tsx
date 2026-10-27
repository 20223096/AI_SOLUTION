import type { CandidateResult } from '../api/recommendations'

/** 후보 판정 배지: 추천 / 제약 충족(비추천) / 위반 */
export function CandidateBadge({ candidate: c, selectable }: { candidate: CandidateResult; selectable: boolean }) {
  if (selectable) return <span className="s4-badge rec">추천</span>
  if (c.prd_feasible) return <span className="s4-badge ok">제약 충족</span>
  return <span className="s4-badge bad">위반 {c.violations.length}건</span>
}
