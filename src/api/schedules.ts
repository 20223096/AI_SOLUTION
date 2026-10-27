import { postJson } from './client'
import type { ConfirmedPlan } from './planning'
import type { components } from './types/api'

type Schemas = components['schemas']

export type ScheduleValidationRequest = Schemas['PRDScheduleValidationRequest']
export type ScheduleValidationResponse = Schemas['PRDScheduleValidationResponse']
export type ConstraintViolation = Schemas['ConstraintViolation']
export type TaskAssignment = Schemas['TaskAssignment']

/** 시연 분석 날짜. 추천 API가 지원하는 날짜(2026-09-11, 2026-10-07) 중 9/11로 고정한다. */
export const ANALYSIS_DATE = '2026-09-11'
/** assignment datetime은 timezone offset이 필수다(KST). */
const TZ_OFFSET = '+09:00'

/** "08:00" → "2026-09-11T08:00:00+09:00" */
export const toAssignmentDateTime = (hhmm: string) => `${ANALYSIS_DATE}T${hhmm}:00${TZ_OFFSET}`

/** S3 일정 검증: POST /api/prd/schedules/validate */
export function validateSchedule(plan: ConfirmedPlan, assignments: TaskAssignment[], signal?: AbortSignal) {
  const body: ScheduleValidationRequest = {
    analysis_date: ANALYSIS_DATE,
    planning: plan.planning,
    assignments,
    predecessors: plan.predecessors,
    equipment_by_task: plan.equipment_by_task,
    equipment_count_by_task: plan.equipment_count_by_task,
    task_duration_by_task: plan.task_duration_by_task,
    restoration_task_ids: plan.restoration_task_ids,
  }
  return postJson<ScheduleValidationResponse>('/api/prd/schedules/validate', body, signal)
}
