import { postJson, request } from './client'
import type { components } from './types/api'

type Schemas = components['schemas']
export type ResidentNoticeDraftCreate = Schemas['ResidentNoticeDraftCreateRequest']
export type ResidentNoticeDraftUpdate = Schemas['ResidentNoticeDraftUpdateRequest']
export type ResidentNoticeDraft = Schemas['ResidentNoticeDraftResponse']
export type ResidentPublicResponse = Schemas['ResidentPublicResponse']
export type SelectedNoticeSchedule = Schemas['SelectedNoticeSchedule']

export const createResidentNoticeDraft = (body: ResidentNoticeDraftCreate, signal?: AbortSignal) =>
  postJson<ResidentNoticeDraft>('/api/staff/resident-notices/drafts', body, signal)

export const getResidentNoticeDraft = (projectId: string, signal?: AbortSignal) =>
  request<ResidentNoticeDraft>(`/api/staff/resident-notices/drafts/${encodeURIComponent(projectId)}`, { signal })

export const updateResidentNoticeDraft = (projectId: string, body: ResidentNoticeDraftUpdate, signal?: AbortSignal) =>
  request<ResidentNoticeDraft>(`/api/staff/resident-notices/drafts/${encodeURIComponent(projectId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })

export const confirmResidentNotice = (
  projectId: string,
  expectedRevision: number,
  scheduleVersion: string,
  signal?: AbortSignal,
) => postJson<ResidentNoticeDraft>(
  `/api/staff/resident-notices/drafts/${encodeURIComponent(projectId)}/confirm`,
  { expected_revision: expectedRevision, schedule_version: scheduleVersion },
  signal,
)

export const getPublicResidentNotice = (projectId: string, signal?: AbortSignal) =>
  request<ResidentPublicResponse>(`/api/public/construction/${encodeURIComponent(projectId)}/resident-notice`, { signal })
