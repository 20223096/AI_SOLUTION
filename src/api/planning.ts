import { postJson } from './client'
import { getFieldEvidence, type ExtractResponse } from './notices'
import type { components } from './types/api'

type Schemas = components['schemas']

export type PlanningDraftRequest = Schemas['PRDPlanningDraftRequest']
export type PlanningDraftResponse = Schemas['PRDPlanningDraftResponse']
export type PlanningDraft = Schemas['PRDPlanningDraft']
export type DraftEquipmentConstraint = Schemas['DraftEquipmentConstraint']
export type PlanningInput = Schemas['PRDNoticePlanningInput-Input']
export type EquipmentConstraintInput = Schemas['EquipmentPlanningConstraint-Input']
export type TimeWindow = Schemas['TimeWindow']

/**
 * S2에서 사용자가 확정한 계획. S3 검증·S4 추천 요청에 그대로 넣는다.
 * (PRDScheduleValidationRequest / PRDConstraintRecommendationRequest의 공통 부분)
 */
export interface ConfirmedPlan {
  planning: PlanningInput
  predecessors: Record<string, string[]>
  equipment_by_task: Record<string, string | null>
  equipment_count_by_task: Record<string, number>
  restoration_task_ids: string[]
}

/** S2 PRD 초안 변환: POST /api/prd/planning/from-notice */
export function createPlanningDraft(extraction: ExtractResponse, signal?: AbortSignal) {
  const body: PlanningDraftRequest = {
    // 추출 응답의 notice(Output)와 요청 notice(Input)는 같은 구조다.
    notice: extraction.notice,
    extractor_mode: extraction.mode,
    is_actual_ai: extraction.is_actual_ai,
    field_evidence: getFieldEvidence(extraction),
  }
  return postJson<PlanningDraftResponse>('/api/prd/planning/from-notice', body, signal)
}
