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

/** mock 응답만 field_evidence를 갖는다. */
export function getFieldEvidence(res: ExtractResponse): Record<string, unknown> {
  return 'field_evidence' in res && res.field_evidence ? (res.field_evidence as Record<string, unknown>) : {}
}
