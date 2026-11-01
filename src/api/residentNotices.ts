import { request } from './client'
import type { components } from './types/api'

type Schemas = components['schemas']
export type ResidentNoticeDraftCreate = Schemas['ResidentNoticeDraftCreateRequest']
export type ResidentNoticeDraftUpdate = Schemas['ResidentNoticeDraftUpdateRequest']
export type ResidentNoticeDraft = Schemas['ResidentNoticeDraftResponse']
export type ResidentPublicResponse = Schemas['ResidentPublicResponse']
export type SelectedNoticeSchedule = Schemas['SelectedNoticeSchedule']

const staffHeaders = (token: string, json = false) => ({
  ...(json ? { 'Content-Type': 'application/json' } : {}),
  ...(token ? { Authorization: `Bearer ${token}` } : {}),
})

export const createResidentNoticeDraft = (body: ResidentNoticeDraftCreate, token: string, signal?: AbortSignal) =>
  request<ResidentNoticeDraft>('/api/staff/resident-notices/drafts', {
    method: 'POST', headers: staffHeaders(token, true), body: JSON.stringify(body), signal,
  })

export const getResidentNoticeDraft = (projectId: string, token: string, signal?: AbortSignal) =>
  request<ResidentNoticeDraft>(`/api/staff/resident-notices/drafts/${encodeURIComponent(projectId)}`, {
    headers: staffHeaders(token), signal,
  })

export const updateResidentNoticeDraft = (projectId: string, body: ResidentNoticeDraftUpdate, token: string, signal?: AbortSignal) =>
  request<ResidentNoticeDraft>(`/api/staff/resident-notices/drafts/${encodeURIComponent(projectId)}`, {
    method: 'PUT',
    headers: staffHeaders(token, true),
    body: JSON.stringify(body),
    signal,
  })

export const confirmResidentNotice = (
  projectId: string,
  expectedRevision: number,
  scheduleVersion: string,
  token: string,
  signal?: AbortSignal,
) => request<ResidentNoticeDraft>(`/api/staff/resident-notices/drafts/${encodeURIComponent(projectId)}/confirm`, {
  method: 'POST',
  headers: staffHeaders(token, true),
  body: JSON.stringify({ expected_revision: expectedRevision, schedule_version: scheduleVersion }),
  signal,
})

export const getPublicResidentNotice = (projectId: string, signal?: AbortSignal) =>
  request<ResidentPublicResponse>(`/api/public/construction/${encodeURIComponent(projectId)}/resident-notice`, { signal })
