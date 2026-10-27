import type { ConstructionNotice } from '../api/notices'
import type { ConfirmedPlan } from '../api/planning'
import { toAssignmentDateTime, type ConstraintViolation, type TaskAssignment } from '../api/schedules'
import { fromMinutes, hhmm, toMinutes } from '../utils/time'

export interface ScheduleRow {
  task_id: string
  name: string
  start: string // "HH:MM", '' = 미입력
  end: string
}

/** 선행 관계를 지키는 작업 순서(Kahn). 순환이 있으면 남은 작업은 원래 순서대로 붙인다. */
function orderTasks(ids: string[], predecessors: Record<string, string[]>): string[] {
  const done = new Set<string>()
  const ordered: string[] = []
  let progressed = true
  while (progressed) {
    progressed = false
    for (const id of ids) {
      if (done.has(id)) continue
      const preds = (predecessors[id] ?? []).filter((p) => ids.includes(p))
      if (preds.every((p) => done.has(p))) {
        done.add(id)
        ordered.push(id)
        progressed = true
      }
    }
  }
  return [...ordered, ...ids.filter((id) => !done.has(id))]
}

/**
 * 신고서 원 일정: 공고문 작업 시작시각부터 선행 순서대로 작업을 이어 붙인다.
 * (백엔드 추천 API의 original_schedule = offset-0 과 같은 규칙)
 * 소요시간은 공고문 작업 시간 → 확정한 장비 필요 사용시간 순으로 쓰고, 둘 다 없으면 비워 둔다.
 */
export function buildOriginalSchedule(notice: ConstructionNotice, plan: ConfirmedPlan): ScheduleRow[] {
  const tasks = new Map(notice.tasks.map((t) => [t.id, t]))
  const usage = new Map(plan.planning.equipment_constraints?.map((e) => [e.equipment_id, e.required_usage_minutes]))
  const startOfDay = notice.original_work_window?.start ?? plan.planning.total_work_window.start

  let cursor: number | null = toMinutes(hhmm(startOfDay))
  return orderTasks([...tasks.keys()], plan.predecessors).map((id) => {
    const task = tasks.get(id)!
    const equipment = plan.equipment_by_task[id]
    const duration = task.duration_minutes ?? (equipment ? usage.get(equipment) : undefined) ?? null

    const start = cursor != null ? fromMinutes(cursor) : null
    const endMin = cursor != null && duration != null ? cursor + duration : null
    const end = endMin != null ? fromMinutes(endMin) : null
    cursor = end != null ? endMin : null // 소요시간을 모르면 이후 작업 시각도 비운다.
    return { task_id: id, name: task.name, start: start ?? '', end: end ?? '' }
  })
}

export function scheduleIssues(rows: ScheduleRow[]): string[] {
  const issues: string[] = []
  for (const r of rows) {
    if (!r.start || !r.end) issues.push(`${r.name}: 시작·종료 시각을 입력해 주세요.`)
    else if (r.start >= r.end) issues.push(`${r.name}: 종료 시각이 시작 시각보다 늦어야 합니다.`)
  }
  return issues
}

export const toAssignments = (rows: ScheduleRow[]): TaskAssignment[] =>
  rows.map((r) => ({ task_id: r.task_id, start: toAssignmentDateTime(r.start), end: toAssignmentDateTime(r.end) }))

// PRD 연동 가이드 5절 권장 문구. 법적 판정이 아니라 입력 계획과 명시 제약의 불일치 안내다.
const VIOLATION_MESSAGE: Record<string, string> = {
  construction_period_missing: '공사 시작일과 종료일을 확인해 주세요.',
  outside_construction_period: '선택 날짜가 공사기간 밖입니다.',
  outside_total_work_window: '작업이 전체 공사 허용시간을 벗어납니다.',
  outside_equipment_time_window: '장비 작업이 장비별 허용시간을 벗어납니다.',
  equipment_count_missing: '작업별 투입 장비 대수를 입력해 주세요.',
  equipment_daily_count_exceeded: '입력한 장비 대수가 일 최대 대수를 초과합니다.',
  equipment_concurrent_count_exceeded: '동시에 사용하는 장비 대수가 한도를 초과합니다.',
  equipment_required_usage_mismatch: '배정된 장비 사용시간이 필요한 사용시간과 다릅니다.',
  outside_road_occupancy_permit: '작업이 도로점용 허가시간을 벗어납니다.',
  fixed_task_missing: '필수 고정 작업이 일정에 없습니다.',
  fixed_task_start_changed: '고정 작업 시작시각을 변경할 수 없습니다.',
  fixed_task_end_changed: '고정 작업 종료시각을 변경할 수 없습니다.',
  predecessor_violation: '선행 작업 완료 전에 후속 작업이 시작됩니다.',
  same_day_restoration_missing: '당일 복구 작업이 일정에 없습니다.',
  same_day_restoration_violation: '복구 작업이 당일 완료되지 않습니다.',
  project_completion_date_exceeded: '계획 완료일을 초과합니다.',
}

export const violationMessage = (v: ConstraintViolation) => VIOLATION_MESSAGE[v.code] ?? v.code

/** 위반에 딸린 대상·수치를 "작업 · 장비 · 수치" 형태로 정리한다. */
export function violationDetails(v: ConstraintViolation, taskNames: Map<string, string>): string[] {
  const name = (id: string) => taskNames.get(id) ?? id
  const parts: string[] = []
  if (v.task_id) parts.push(`작업 ${name(v.task_id)}`)
  if (v.predecessor_id) parts.push(`선행 작업 ${name(v.predecessor_id)}`)
  if (v.equipment_id) parts.push(`장비 ${v.equipment_id}`)
  if (v.count != null) parts.push(v.maximum != null ? `${v.count}대 / 최대 ${v.maximum}대` : `${v.count}대`)
  else if (v.maximum != null) parts.push(`최대 ${v.maximum}대`)
  if (v.scheduled_minutes != null || v.required_minutes != null) {
    parts.push(`배정 ${v.scheduled_minutes ?? '?'}분 / 필요 ${v.required_minutes ?? '?'}분`)
  }
  if (v.detail) parts.push(v.detail)
  return parts
}
