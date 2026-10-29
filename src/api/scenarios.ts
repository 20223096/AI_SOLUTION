import { request } from './client'
import type { components } from './types/api'

type Schemas = components['schemas']
export type ScenarioDetail = Schemas['ScenarioDetailResponse']
export type Receptor = Schemas['Receptor']

/** S4 민감도 지도: GET /api/poc/scenarios/{scenario_id} (수음점과 공사장까지 거리) */
export function getScenario(scenarioId: string, signal?: AbortSignal) {
  return request<ScenarioDetail>(`/api/poc/scenarios/${encodeURIComponent(scenarioId)}`, { signal })
}
