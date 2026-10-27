import { afterEach, describe, expect, it, vi } from 'vitest'
import { lookupAddressCoordinate } from './coordinates'
import { extractNoticeFromText } from './notices'
import {
  confirmResidentNotice,
  createResidentNoticeDraft,
  getPublicResidentNotice,
  updateResidentNoticeDraft,
} from './residentNotices'
import { request } from './client'
import { requestRecommendations } from './recommendations'

const ok = (payload: unknown) => vi.spyOn(globalThis, 'fetch').mockResolvedValue(
  new Response(JSON.stringify(payload), { status: 200, headers: { 'Content-Type': 'application/json' } }),
)

afterEach(() => vi.restoreAllMocks())

describe('API v3.4 client', () => {
  it('S1 posts notice text', async () => {
    const fetch = ok({ mode: 'mock' })
    await extractNoticeFromText('신고서')
    expect(fetch).toHaveBeenCalledWith('/api/notices/extract', expect.objectContaining({ method: 'POST' }))
  })

  it('S2 sends the selected JUSO candidate explicitly', async () => {
    const fetch = ok({ status: 'resolved' })
    await lookupAddressCoordinate('서울 주소', 'candidate-2')
    expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toEqual({ address: '서울 주소', selected_address_id: 'candidate-2' })
  })

  it('does not turn a coordinate not_found response into data', async () => {
    ok({ status: 'not_found', candidates: [], user_confirmation_required: true })
    expect((await lookupAddressCoordinate('없는 주소')).status).toBe('not_found')
  })

  it('creates a private S7 draft through the staff endpoint', async () => {
    const fetch = ok({ status: 'draft' })
    await createResidentNoticeDraft({} as never)
    expect(fetch).toHaveBeenCalledWith('/api/staff/resident-notices/drafts', expect.objectContaining({ method: 'POST' }))
  })

  it('updates a draft with PUT', async () => {
    const fetch = ok({ revision: 2 })
    await updateResidentNoticeDraft('project/a', {} as never)
    expect(fetch).toHaveBeenCalledWith('/api/staff/resident-notices/drafts/project%2Fa', expect.objectContaining({ method: 'PUT' }))
  })

  it('confirms with revision and schedule version', async () => {
    const fetch = ok({ status: 'confirmed' })
    await confirmResidentNotice('project', 2, 'schedule-v2')
    expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toEqual({ expected_revision: 2, schedule_version: 'schedule-v2' })
  })

  it('S8 reads only the public endpoint', async () => {
    const fetch = ok({ status: 'not_published' })
    expect((await getPublicResidentNotice('project')).status).toBe('not_published')
    expect(fetch).toHaveBeenCalledWith('/api/public/construction/project/resident-notice', expect.any(Object))
  })

  it('preserves server errors for UI handling', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ detail: 'snapshot mismatch' }), { status: 422 }))
    await expect(request('/api/test')).rejects.toMatchObject({ status: 422, detail: 'snapshot mismatch' })
  })

  it('reports network failures distinctly', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('offline'))
    await expect(request('/api/test')).rejects.toMatchObject({ status: null })
  })

  it('S4 explicitly requests the CP-SAT v2 engine while the API default remains compatible', async () => {
    const fetch = ok({ candidates: [] })
    await requestRecommendations({
      planning: {}, predecessors: {}, equipment_by_task: {}, equipment_count_by_task: {}, restoration_task_ids: [],
    } as never)
    expect(JSON.parse(String(fetch.mock.calls[0][1]?.body)).recommendation_engine).toBe('cp_sat_v2')
  })
})
