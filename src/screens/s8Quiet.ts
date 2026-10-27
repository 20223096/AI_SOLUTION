import type { TaskAssignment } from '../api/schedules'
import { fromMinutes, hhmm, toMinutes } from '../utils/time'
import { assignmentTime } from './s4Display'

export type DayItem =
  | { kind: 'work'; start: string; end: string; name: string }
  | { kind: 'quiet'; start: string; end: string | null }

export interface QuietSummary {
  /** 작업 허용시간 안에서 이 공사 작업이 없는 가장 긴 구간. 없으면 null */
  longest: { start: string; end: string; minutes: number } | null
  items: DayItem[]
}

const t = (m: number) => fromMinutes(m) ?? '24:00'

/**
 * 확정 일정에서 주민용 하루 일정을 만든다.
 * '조용한 시간' = 작업 허용시간 안에서 이 공사의 작업이 없는 구간(교통 등 다른 소음은 포함하지 않음).
 */
export function summarizeDay(
  assignments: TaskAssignment[],
  names: Map<string, string>,
  window: { start: string; end: string },
): QuietSummary {
  const ws = toMinutes(hhmm(window.start))
  const we = toMinutes(hhmm(window.end))
  const tasks = assignments
    .map((a) => ({
      name: names.get(a.task_id) ?? a.task_id,
      s: toMinutes(assignmentTime(a.start)),
      e: toMinutes(assignmentTime(a.end)),
    }))
    .sort((a, b) => a.s - b.s)

  // 겹치는 작업은 하나의 '공사 중' 구간으로 합쳐 빈 시간을 찾는다.
  const busy: { s: number; e: number }[] = []
  for (const k of tasks) {
    const last = busy[busy.length - 1]
    if (last && k.s <= last.e) last.e = Math.max(last.e, k.e)
    else busy.push({ s: k.s, e: k.e })
  }

  const gaps: { s: number; e: number }[] = []
  let cursor = ws
  for (const b of busy) {
    if (b.s > cursor) gaps.push({ s: cursor, e: Math.min(b.s, we) })
    cursor = Math.max(cursor, b.e)
  }
  if (cursor < we) gaps.push({ s: cursor, e: we })
  const inWindow = gaps.filter((g) => g.e > g.s)

  const best = inWindow.reduce<{ s: number; e: number } | null>(
    (acc, g) => (!acc || g.e - g.s > acc.e - acc.s ? g : acc),
    null,
  )

  const items: DayItem[] = [
    ...tasks.map((k) => ({ kind: 'work' as const, start: t(k.s), end: t(k.e), name: k.name })),
    ...inWindow.map((g) => ({ kind: 'quiet' as const, start: t(g.s), end: t(g.e) })),
  ].sort((a, b) => a.start.localeCompare(b.start))
  // 작업 허용시간이 끝난 뒤에는 이 공사가 없다.
  const lastEnd = Math.max(we, ...tasks.map((k) => k.e))
  items.push({ kind: 'quiet', start: t(lastEnd), end: null })

  return {
    longest: best ? { start: t(best.s), end: t(best.e), minutes: best.e - best.s } : null,
    items,
  }
}
