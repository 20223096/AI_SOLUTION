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
    restoration_task_ids: plan.restoration_task_ids,
    background_profile: BACKGROUND_PROFILE,
    objective_mode: OBJECTIVE_MODE,
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

/**
 * 대표 추천: 선택 가능한 추천 후보 중 추가 소음 영향(incremental_impact_cost)이 가장 낮은 후보.
 * 같으면 일정 변경이 적은 후보. 날짜별 결과는 API가 정한다(예: 9/11은 offset-0, 10/7은 offset-120).
 */
export function representativeId(res: RecommendationResponse): string | null {
  const best = res.candidates
    .filter((c) => isSelectable(c, res))
    .reduce<CandidateResult | null>((a, c) => {
      if (!a) return c
      const d = c.noise_impact.incremental_impact_cost - a.noise_impact.incremental_impact_cost
      return d < 0 || (d === 0 && c.schedule_change_minutes < a.schedule_change_minutes) ? c : a
    }, null)
  return best?.candidate_id ?? null
}
