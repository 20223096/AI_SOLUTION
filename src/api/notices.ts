import { postJson, request } from './client'
import type { components } from './types/api'

type Schemas = components['schemas']

export type ExtractRequest = Schemas['ExtractRequest']
export type MockExtractResponse = Schemas['MockNoticeExtractResponse']
export type LLMExtractResponse = Schemas['LLMNoticeExtractResponse']
export type ExtractResponse = MockExtractResponse | LLMExtractResponse
export type ConstructionNotice = Schemas['ConstructionNotice-Output']
export type ConstructionTask = Schemas['ConstructionTask']
export type SourceMetadata = Schemas['SourceMetadata']
export type ProvenanceStatus = Schemas['ProvenanceStatus']

/** S1 텍스트 입력: POST /api/notices/extract */
export function extractNoticeFromText(text: string, signal?: AbortSignal) {
  const body: ExtractRequest = { text }
  return postJson<ExtractResponse>('/api/notices/extract', body, signal)
}

/** S1 파일 업로드(txt/PDF): POST /api/notices/extract-file (multipart `file`) */
export function extractNoticeFromFile(file: File, signal?: AbortSignal) {
  const form = new FormData()
  form.append('file', file)
  // Content-Type은 브라우저가 boundary와 함께 자동으로 설정한다.
  return request<ExtractResponse>('/api/notices/extract-file', { method: 'POST', body: form, signal })
}

/** mock과 LLM 응답의 원문 근거를 동일하게 읽는다. */
export function getFieldEvidence(res: ExtractResponse): Record<string, unknown> {
  return 'field_evidence' in res && res.field_evidence ? (res.field_evidence as Record<string, unknown>) : {}
}

export function evidenceText(value: unknown): string | null {
  if (typeof value === 'string') return value
  if (value && typeof value === 'object' && 'evidence' in value) {
    const evidence = (value as { evidence?: unknown }).evidence
    return typeof evidence === 'string' ? evidence : null
  }
  return null
}

export function evidenceNeedsReview(value: unknown): boolean {
  return Boolean(value && typeof value === 'object' && 'needs_review' in value && value.needs_review)
}
