import { describe, expect, it } from 'vitest'
import { isSelectable } from '../api/recommendations'
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

  it('does not expose internal metrics in resident timeline summaries', () => {
    const result = summarizeDay([], new Map(), { start: '08:00', end: '18:00' })
    expect(JSON.stringify(result)).not.toMatch(/impact|receptor|decibel|dB/i)
  })
})
