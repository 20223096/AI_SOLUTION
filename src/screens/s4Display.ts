import type { CandidateResult, ScheduleMetrics } from '../api/recommendations'
import type { TaskAssignment } from '../api/schedules'
import { violationMessage } from './s3Schedule'

/** "offset-60" → "+60분 이동" */
export function candidateLabel(id: string): string {
  const advanced = /^cp-sat-(\d+)$/.exec(id)
  if (advanced) return `작업별 배치안 ${Number(advanced[1])}`
  const m = /^offset-(\d+)$/.exec(id)
  if (!m) return id
  return m[1] === '0' ? '원 일정 시각' : `+${m[1]}분 이동`
}

/** "2026-09-11T08:00:00+09:00" → "08:00" */
export const assignmentTime = (iso: string) => iso.slice(11, 16)

export const toTimelineItems = (assignments: TaskAssignment[], names: Map<string, string>, bad?: Set<string>) =>
  assignments.map((a) => ({
    id: a.task_id,
    name: names.get(a.task_id) ?? a.task_id,
    start: assignmentTime(a.start),
    end: assignmentTime(a.end),
    bad: bad?.has(a.task_id),
  }))

export type MetricKey = keyof ScheduleMetrics
type Better = 'lower' | 'higher' | 'neutral'

export interface MetricDef {
  key: MetricKey
  label: string
  unit: string
  better: Better
}

const M = (key: MetricKey, label: string, unit: string, better: Better): MetricDef => ({ key, label, unit, better })

/** 비교 화면 상단 카드(목업 6번 '조정 전후 비교')에 쓰는 핵심 지표 */
export const HEADLINE_METRICS: MetricDef[] = [
  M('incremental_impact_cost', '추가 소음 영향', '', 'lower'),
  M('existing_noise_overlap_receptor_minutes', '기존 소음과 겹침', '수음점·분', 'lower'),
  M('max_total_estimated_db', '최대 추정 소음', 'dB', 'lower'),
  M('saturation_slot_count', '고소음 포화 구간', '개', 'lower'),
  M('longest_quiet_window_minutes', '최장 조용한 시간', '분', 'higher'),
  M('schedule_change_minutes', '일정 변경량', '분', 'neutral'),
]

/** ScheduleMetrics 전체 필드 */
export const ALL_METRICS: MetricDef[] = [
  M('incremental_impact_cost', '추가 소음 영향(증분)', '', 'lower'),
  M('absolute_impact_cost', '절대 영향 비용', '', 'lower'),
  M('total_impact_score', '총 영향 점수', '', 'lower'),
  M('max_impact_score', '최대 영향 점수', '', 'lower'),
  M('max_total_estimated_db', '최대 추정 소음', 'dB', 'lower'),
  M('max_new_project_contribution_db', '신규 공사 최대 기여', 'dB', 'lower'),
  M('cumulative_delta_db_minutes', '누적 dB 증가량', 'dB·분', 'lower'),
  M('saturation_slot_count', '고소음 포화 구간', '개', 'lower'),
  M('existing_noise_overlap_receptor_minutes', '기존 소음과 겹침', '수음점·분', 'lower'),
  M('max_continuous_high_noise_minutes', '최대 연속 고소음 시간', '분', 'lower'),
  M('longest_quiet_window_minutes', '최장 조용한 시간', '분', 'higher'),
  M('sensitive_high_noise_minutes', '민감 시간대 고소음 시간', '분', 'lower'),
  M('new_project_additional_high_noise_minutes', '신규 공사로 늘어난 고소음 시간', '분', 'lower'),
  M('sensitive_new_project_exposure_minutes', '민감 시간대 신규 공사 노출', '분', 'lower'),
  M('sensitive_new_project_receptor_minutes', '민감 수음점 신규 공사 노출', '수음점·분', 'lower'),
  M('sensitivity_weighted_new_project_receptor_minutes', '민감도 가중 신규 공사 노출', '수음점·분', 'lower'),
  M('new_project_receptor_minutes', '신규 공사 노출', '수음점·분', 'lower'),
  M('max_continuous_new_project_minutes', '신규 공사 최대 연속 시간', '분', 'lower'),
  M('new_project_energy_exposure_65db_ref_minutes', '신규 공사 에너지 노출(65dB 기준)', '분', 'lower'),
  M('new_project_inactive_minutes', '신규 공사 비가동 시간', '분', 'neutral'),
  M('schedule_change_minutes', '일정 변경량', '분', 'neutral'),
  M('project_start_change_minutes', '착공 이동', '분', 'neutral'),
  M('project_end_change_minutes', '완료 이동', '분', 'neutral'),
]

export function formatNumber(v: number): string {
  return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

export const formatDelta = (d: number) => (d > 0 ? `+${formatNumber(d)}` : formatNumber(d))

/** 지표 방향에 따라 변화량을 좋음/나쁨/중립으로 분류한다. */
export function deltaTone(def: MetricDef, delta: number): 'good' | 'bad' | 'neutral' {
  if (delta === 0 || def.better === 'neutral') return 'neutral'
  const improved = def.better === 'lower' ? delta < 0 : delta > 0
  return improved ? 'good' : 'bad'
}

const CAVEAT_KO: Record<string, string> = {
  'This is a constraint-filtered result over the explored candidate set, not a global optimum.':
    '탐색한 후보 집합에서 제약으로 거른 결과이며, 전역 최적해가 아닙니다.',
  'This is a constraint-filtered result over the existing offset candidate set, not a global optimum.':
    '기존 이동(offset) 후보 안에서 제약으로 거른 결과이며, 전역 최적해가 아닙니다.',
  'No unspecified time limit or relaxed constraint was introduced.':
    '입력하지 않은 시간 제한을 추가하거나 제약을 완화하지 않았습니다.',
  'S-DoT observations are not added to the acoustic synthesis.': 'S-DoT 관측값은 소음 합성 계산에 포함되지 않습니다.',
  'Official construction geometry and residential facade receptors remain unavailable; field accuracy is not_evaluable.':
    '공식 공사 선형과 주거 외벽 수음점이 없어 현장 정확도는 평가할 수 없습니다(not_evaluable).',
}

export const caveatText = (c: string) => CAVEAT_KO[c] ?? c

/** 후보가 추천되지 않은 이유(위반 안내 문구) */
export function candidateReason(c: CandidateResult, selectable: boolean): string {
  if (c.violations.length > 0) return [...new Set(c.violations.map(violationMessage))].join(' / ')
  if (c.prd_feasible && !selectable) return '제약은 지키지만 다른 후보에 비해 이점이 없어 추천에서 제외'
  return '–'
}
