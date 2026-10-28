export type Metrics = {
  constraint_violation_count: number | null
  noise_impact: number | null
  quiet_window_minutes: number | null
  continuous_high_noise_minutes: number | null
  schedule_change_minutes: number | null
}

export type DayResult = {
  analysis_date: string
  scenario_id: string
  input_data: Record<string, string>
  A_original_vs_offset: { candidate_count: number; pareto_count: number; original: Metrics; offset_recommendation: Metrics }
  B_original_vs_advanced: { candidate_count: number; pareto_count: number; advanced_recommendation: Metrics }
}

export type Variant = { label: string; metrics: Metrics; candidateCount: number; paretoCount: number }

export function rowsForDay(day: DayResult): Variant[] {
  return [
    { label: '원안', metrics: day.A_original_vs_offset.original, candidateCount: day.A_original_vs_offset.candidate_count, paretoCount: day.A_original_vs_offset.pareto_count },
    { label: 'offset_v1', metrics: day.A_original_vs_offset.offset_recommendation, candidateCount: day.A_original_vs_offset.candidate_count, paretoCount: day.A_original_vs_offset.pareto_count },
    { label: 'cp_sat_v2', metrics: day.B_original_vs_advanced.advanced_recommendation, candidateCount: day.B_original_vs_advanced.candidate_count, paretoCount: day.B_original_vs_advanced.pareto_count },
  ]
}
