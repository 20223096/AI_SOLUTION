import { describe, expect, it } from 'vitest'
import report from '../../public/sprint36-comparison.json'
import { rowsForDay } from './scenarioComparisonModel'

describe('presentation scenario comparison', () => {
  it('uses the reproducible experiment artifact for both dates', () => {
    expect(report.generator).toBe('scripts/run_sprint29_experiments.py')
    expect(report.results.map((day) => day.analysis_date)).toEqual(['2026-09-11', '2026-10-07'])

    const september = rowsForDay(report.results[0])
    expect(september.map((row) => row.metrics.noise_impact)).toEqual([7.36, 7.36, 7.36])
    expect(september[2]).toMatchObject({ candidateCount: 495, paretoCount: 35, metrics: { schedule_change_minutes: 0 } })

    const october = rowsForDay(report.results[1])
    expect(october.map((row) => row.metrics.noise_impact)).toEqual([13.72, 13.2, 13.12])
    expect(october[2]).toMatchObject({ candidateCount: 495, paretoCount: 18, metrics: { schedule_change_minutes: 420 } })
  })

  it('keeps uncomputed simultaneous wall-clock noise as null', () => {
    for (const day of report.results) {
      expect(day.A_original_vs_offset.original.simultaneous_high_noise_minutes).toBeNull()
      expect(day.B_original_vs_advanced.advanced_recommendation.simultaneous_high_noise_minutes).toBeNull()
    }
  })
})
