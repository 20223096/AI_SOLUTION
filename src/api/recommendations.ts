import { postJson } from './client'
import type { ConfirmedPlan } from './planning'
import { ANALYSIS_DATE, type TaskAssignment } from './schedules'
import type { components } from './types/api'

type Schemas = components['schemas']

export type RecommendationRequest = Schemas['PRDConstraintRecommendationRequest']
export type RecommendationResponse = Schemas['PRDConstraintRecommendationResponse']
export type CandidateResult = Schemas['ConstraintCandidateResult']
export type ScheduleMetrics = Schemas['ScheduleMetrics']
export type CompareRequest = Schemas['CompareRequest']
export type CompareResponse = Schemas['CompareResponse']

/** 추천과 비교가 같은 배경소음 기준을 쓰도록 공유한다(서버 기본값). */
export const BACKGROUND_PROFILE = 'road_traffic_observed_profile'
const OBJECTIVE_MODE: RecommendationRequest['objective_mode'] = 'incremental_impact'

/** S4 후보 생성 + 제약 필터: POST /api/prd/recommendations/constraint-filtered */
export function requestRecommendations(plan: ConfirmedPlan, signal?: AbortSignal) {
  const body: RecommendationRequest = {
    analysis_date: ANALYSIS_DATE,
    planning: plan.planning,
    predecessors: plan.predecessors,
    equipment_by_task: plan.equipment_by_task,
    equipment_count_by_task: plan.equipment_count_by_task,
    task_duration_by_task: plan.task_duration_by_task,
    restoration_task_ids: plan.restoration_task_ids,
    background_profile: BACKGROUND_PROFILE,
    objective_mode: OBJECTIVE_MODE,
    recommendation_engine: 'cp_sat_v2',
  }
  return postJson<RecommendationResponse>('/api/prd/recommendations/constraint-filtered', body, signal)
}

/** S4 전후 비교: POST /api/schedules/compare (before = 원 일정, after = 선택 후보) */
export function compareSchedules(
  scenarioId: string,
  before: TaskAssignment[],
  after: TaskAssignment[],
  signal?: AbortSignal,
) {
  const body: CompareRequest = {
    scenario_id: scenarioId,
    analysis_date: ANALYSIS_DATE,
    before,
    after,
    background_profile: BACKGROUND_PROFILE,
  }
  return postJson<CompareResponse>('/api/schedules/compare', body, signal)
}

/** 가이드 6절: id 목록에 있고 recommendable·prd_feasible이 모두 true인 후보만 선택 가능하다. */
export const isSelectable = (c: CandidateResult, res: RecommendationResponse) =>
  res.recommendable_candidate_ids.includes(c.candidate_id) && c.recommendable && c.prd_feasible
