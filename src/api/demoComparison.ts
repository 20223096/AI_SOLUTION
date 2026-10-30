import { request } from './client'
import type { components } from './types/api'

export type RecommendationDiagnostics = components['schemas']['RecommendationDiagnosticsResponse']

export function getRecommendationDiagnostics(analysisDate: '2026-09-11' | '2026-10-07', signal?: AbortSignal) {
  const query = new URLSearchParams({ analysis_date: analysisDate, background_profile: 'road_traffic_observed_profile' })
  return request<RecommendationDiagnostics>(`/api/prd/recommendation-diagnostics?${query}`, { signal })
}
