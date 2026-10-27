import { describe, expect, it } from 'vitest'
import { isSelectable } from '../api/recommendations'
import { formFromDraft, validateForm, type PlanningForm } from './s2Form'
import { summarizeDay } from './s8Quiet'

describe('workflow guards', () => {
  it('blocks a notice with missing required fields', () => {
    const form = {
      project_name: '', location: '', period_start: '', period_end: '', period_raw: null,
      work_start: '', work_end: '', road_excavation: '', has_permit_window: false,
      permit_start: '', permit_end: '', same_day_restoration: false, completion_date: '',
      non_adjustable: '', equipment: [], tasks: [],
    } satisfies PlanningForm
    expect(validateForm(form).map((issue) => issue.key)).toEqual(expect.arrayContaining(['project_name', 'location', 'construction_period', 'equipment_constraints']))
  })

  it('carries normalized equipment quantity into S2 and blocks an unlinked task', () => {
    const draft = {
      notice_id: 'llm', project_name: '공사', location: '연세로',
      construction_period: { start: '2026-09-11', end: '2026-09-11', raw_text: null },
      total_work_window: { start: '08:00:00', end: '17:00:00' }, road_excavation: true,
      road_occupancy_permit_window: null,
      equipment_constraints: [{ equipment_id: 'excavator', category: '굴착기', specification: null, model_name: null,
        required_usage_minutes: 120, max_daily_count: 1, permitted_time_windows: [{ start: '09:00:00', end: '11:00:00' }],
        source_metadata: { status: 'user_provided', source: 'request text', note: null, unit: null } }],
      fixed_tasks: [], predecessors: {}, same_day_restoration_required: true, source_evidence: {}, field_provenance: {},
    }
    const tasks = [
      { id: 'dig', name: '굴착', equipment_id: 'excavator', duration_minutes: 120, permitted_time_windows: [], predecessors: [], is_movable: true, required_resources: [] },
      { id: 'restore', name: '복구', equipment_id: null, duration_minutes: null, permitted_time_windows: [], predecessors: ['dig'], is_movable: true, required_resources: [] },
    ]
    const form = formFromDraft(draft as never, tasks as never)
    expect(form.tasks[0].count).toBe('1')
    expect(validateForm(form).map((issue) => issue.key)).toContain('tasks.1.equipment_id')
    form.tasks[1].restoration = true
    expect(validateForm(form).map((issue) => issue.key)).not.toContain('tasks.1.equipment_id')
  })

  it('blocks equipment usage outside the confirmed total work window and quantity overflow', () => {
    const form = {
      project_name: '공사', location: '연세로', period_start: '2026-09-11', period_end: '2026-09-11', period_raw: null,
      work_start: '08:00', work_end: '17:00', road_excavation: 'no', has_permit_window: false,
      permit_start: '', permit_end: '', same_day_restoration: false, completion_date: '', non_adjustable: '',
      equipment: [{ equipment_id: 'excavator', category: '굴착기', specification: '', model_name: '', required_usage_minutes: '120', max_daily_count: '1', window_start: '07:00', window_end: '09:00' }],
      tasks: [{ id: 'excavate', name: '굴착', equipment_id: 'excavator', count: '2', duration_minutes: '120', restoration: false }],
    } satisfies PlanningForm
    const messages = validateForm(form).map((issue) => issue.message)
    expect(messages).toEqual(expect.arrayContaining([
      expect.stringContaining('전체 작업 허용시간'), expect.stringContaining('장비 수량을 초과'),
    ]))
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
