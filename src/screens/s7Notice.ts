import type { ConfirmedPlan } from '../api/planning'
import type { CandidateResult, CompareResponse, RecommendationResponse } from '../api/recommendations'
import { ANALYSIS_DATE } from '../api/schedules'
import { hhmm } from '../utils/time'
import { assignmentTime, SCENARIO_TASKS } from './s4Display'

/**
 * 주민 안내문 초안 생성. 계약상 안내문 생성 API가 없으므로 클라이언트 템플릿으로 만든다.
 * 원칙(주민_안내문_예시.html): 확정된 정보만 사용하고, 정보에 없는 날짜·번호·내용은 쓰지 않는다.
 */

export type Channel = 'web' | 'sms' | 'board'
export const CHANNEL_LABEL: Record<Channel, string> = { web: '구청 홈페이지 공지', sms: '주민 문자', board: '현장 게시판' }

export interface NoticeFacts {
  projectName: string
  location: string
  period: string
  periodShort: string
  dateLabel: string
  workStart: string
  workEnd: string
  equipment: string[]
}

export interface NoticeInputs {
  department: string
  phone: string
  reason: string
}

const WEEKDAY = ['일', '월', '화', '수', '목', '금', '토']

/** "2026-09-11" → "9월 11일(금)" */
export function formatKoreanDate(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  const day = new Date(y, m - 1, d).getDay()
  return `${m}월 ${d}일(${WEEKDAY[day]})`
}

const shortDate = (iso: string) => {
  const [, m, d] = iso.split('-').map(Number)
  return `${m}/${d}`
}

/** 받침 유무에 따라 조사 선택: josa('공사', '이', '가') → '공사가' */
export function josa(word: string, withFinal: string, withoutFinal: string): string {
  const code = word.charCodeAt(word.length - 1) - 0xac00
  if (code < 0 || code > 11171) return `${word}${withoutFinal}`
  return `${word}${code % 28 ? withFinal : withoutFinal}`
}

export function buildFacts(plan: ConfirmedPlan, candidate: CandidateResult): NoticeFacts {
  const p = plan.planning
  const { start, end } = p.construction_period
  const starts = candidate.assignments.map((a) => a.start).sort()
  const ends = candidate.assignments.map((a) => a.end).sort()
  return {
    projectName: p.project_name,
    location: p.location,
    period: start && end ? (start === end ? formatKoreanDate(start) : `${formatKoreanDate(start)} ~ ${formatKoreanDate(end)}`) : '',
    periodShort: start && end ? (start === end ? shortDate(start) : `${shortDate(start)}~${shortDate(end)}`) : '',
    dateLabel: formatKoreanDate(ANALYSIS_DATE),
    workStart: starts[0] ? assignmentTime(starts[0]) : '',
    workEnd: ends.length ? assignmentTime(ends[ends.length - 1]) : '',
    equipment: [...new Set((p.equipment_constraints ?? []).map((e) => e.category))],
  }
}

/** 조정 이유 기본 문구: 원 일정의 위반과 비교 결과에서 확인되는 사실만 쓴다. */
export function defaultReason(
  plan: ConfirmedPlan,
  res: RecommendationResponse,
  candidate: CandidateResult,
  compare: CompareResponse,
): string {
  const sentences: string[] = []
  const w = plan.planning.total_work_window
  const original = res.original_schedule
  const shift = candidate.project_start_change_minutes

  if (original && !original.prd_feasible) {
    sentences.push(`처음 제출된 일정은 확정된 작업 허용시간(${hhmm(w.start)}~${hhmm(w.end)})을 벗어나 조정이 필요했습니다.`)
  }
  if (shift > 0) sentences.push(`작업 시작을 ${shift}분 늦춰 허용시간 안에서 진행하도록 정했습니다.`)
  else if (shift < 0) sentences.push(`작업 시작을 ${-shift}분 앞당겨 허용시간 안에서 진행하도록 정했습니다.`)

  const overlap = compare.delta.existing_noise_overlap_receptor_minutes ?? 0
  if (overlap < 0) sentences.push('이렇게 조정하면 주변의 다른 소음과 겹치는 시간도 줄어듭니다.')
  return sentences.join(' ')
}

/** 빈 값(false)은 빼고 줄을 잇는다. 연속 빈 줄은 하나로 줄인다. */
const joinLines = (lines: (string | false)[]) =>
  lines
    .filter((l): l is string => l !== false)
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()

export function buildDrafts(f: NoticeFacts, input: NoticeInputs): Record<Channel, string> {
  const department = input.department.trim()
  const phone = input.phone.trim()
  const contact = [department, phone].filter(Boolean).join(' ')
  const reason = input.reason.trim()

  const web = joinLines([
    `${f.projectName} 작업 시간 안내`,
    '',
    '주민 여러분, 안녕하십니까.',
    `${f.location}에서 ${josa(f.projectName, '이', '가')} 진행될 예정이라 안내드립니다.`,
    '',
    !!f.period && `■ 공사 기간: ${f.period}`,
    `■ 작업 시간(${f.dateLabel} 기준): ${f.workStart} ~ ${f.workEnd}`,
    `■ 장소: ${f.location}`,
    f.equipment.length > 0 && `■ 사용 장비: ${f.equipment.join(', ')}`,
    '',
    !!reason && reason,
    !!reason && '',
    '공사 기간 동안 불편을 드려 죄송합니다. 안내된 시간 외에 소음이 발생하거나 불편 사항이 있으시면 아래로 연락해 주십시오.',
    !!contact && `문의: ${contact}`,
  ])

  const sms = [
    department && `[${department}]`,
    f.periodShort,
    `${f.location} ${f.projectName}.`,
    `${f.dateLabel} 작업은 ${f.workStart}~${f.workEnd}에 진행합니다.`,
    phone && `문의 ${phone}`,
  ]
    .filter(Boolean)
    .join(' ')

  const board = joinLines([
    '공사 작업 시간 안내',
    '',
    `${f.workStart} – ${f.workEnd}`,
    `(${f.dateLabel} 기준)`,
    '',
    [f.projectName, f.period].filter(Boolean).join(' · '),
    f.location,
    '',
    !!contact && `문의 ${contact}`,
  ])

  return { web, sms, board }
}

/** 기본으로 '시끄러운 작업'에 체크할 장비. 담당자가 화면에서 바꿀 수 있다. */
const DEFAULT_HIGH_NOISE_EQUIPMENT = [
  { id: 'cutter', name: '절단기' },
  { id: 'breaker', name: '브레이커' },
]

/**
 * 절단기·브레이커를 쓰는 작업을 기본으로 체크한다. 장비 ID나 S2에서 확정한 장비 분류명으로 판단한다.
 * S2 계획에 없는 작업(공고문에서 추출되지 않은 시나리오 작업)은 시나리오 장비로 판단한다.
 */
export function defaultHighNoise(plan: ConfirmedPlan, taskIds: string[]): Record<string, boolean> {
  const categories = new Map((plan.planning.equipment_constraints ?? []).map((e) => [e.equipment_id, e.category]))
  const isLoud = (equipmentId: string) =>
    DEFAULT_HIGH_NOISE_EQUIPMENT.some(
      (d) => equipmentId === d.id || (categories.get(equipmentId) ?? '').includes(d.name),
    )
  const equipmentOf = (taskId: string) =>
    taskId in plan.equipment_by_task ? plan.equipment_by_task[taskId] : (SCENARIO_TASKS[taskId]?.equipment_id ?? null)
  return Object.fromEntries(
    taskIds.filter((taskId) => {
      const equipmentId = equipmentOf(taskId)
      return equipmentId != null && isLoud(equipmentId)
    }).map((taskId) => [taskId, true]),
  )
}

/** 작업을 시작 시각순(같으면 종료 시각순)으로 정렬한 사본 */
export const byStartTime = <T extends { start: string; end: string }>(items: T[]): T[] =>
  [...items].sort((a, b) => a.start.localeCompare(b.start) || a.end.localeCompare(b.end))
