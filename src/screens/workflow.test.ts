import { describe, expect, it } from 'vitest'
import { isSelectable, representativeId } from '../api/recommendations'
import { validateForm, type PlanningForm } from './s2Form'
import { summarizeDay } from './s8Quiet'

describe('workflow guards', () => {
  it('blocks a notice with missing required fields', () => {
    const form = {
      project_name: '', location: '', period_start: '', period_end: '', period_raw: null,
      work_start: '', work_end: '', road_excavation: '', has_permit_window: false,
      permit_start: '', permit_end: '', same_day_restoration: false, completion_date: '',
      non_adjustable: '', equipment: [], tasks: [],
    } satisfies PlanningForm
    expect(validateForm(form).map((issue) => issue.key)).toEqual(expect.arrayContaining(['project_name', 'location', 'construction_period']))
  })

  it('allows one valid recommendation candidate', () => {
    const candidate = { candidate_id: 'only', recommendable: true, prd_feasible: true }
    expect(isSelectable(candidate as never, { recommendable_candidate_ids: ['only'] } as never)).toBe(true)
  })

  it('rejects candidates omitted from the server allow-list', () => {
    const candidate = { candidate_id: 'stale', recommendable: true, prd_feasible: true }
    expect(isSelectable(candidate as never, { recommendable_candidate_ids: [] } as never)).toBe(false)
  })

  // API 실제 응답의 incremental_impact_cost 값(2026-09-11, 2026-10-07)
  const rec = (impacts: Record<string, number>, allowed = Object.keys(impacts)) =>
    ({
      recommendable_candidate_ids: allowed,
      candidates: Object.entries(impacts).map(([id, cost]) => ({
        candidate_id: id,
        recommendable: true,
        prd_feasible: true,
        schedule_change_minutes: Number(id.split('-')[1]) * 4,
        noise_impact: { incremental_impact_cost: cost },
      })),
    }) as never

  it('picks offset-0 as the representative recommendation on 9/11', () => {
    expect(representativeId(rec({ 'offset-0': 7.36, 'offset-120': 13.2 }, ['offset-0']))).toBe('offset-0')
  })

  it('picks offset-120 as the representative recommendation on 10/7', () => {
    expect(representativeId(rec({ 'offset-0': 13.72, 'offset-60': 13.64, 'offset-120': 13.2 }))).toBe('offset-120')
  })

  it('does not expose internal metrics in resident timeline summaries', () => {
    const result = summarizeDay([], new Map(), { start: '08:00', end: '18:00' })
    expect(JSON.stringify(result)).not.toMatch(/impact|receptor|decibel|dB/i)
  })
})
