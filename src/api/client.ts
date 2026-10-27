/**
 * 개발 서버(npm run dev)에서는 상대 경로(/api/...)로 요청하고 vite.config.ts 프록시가 백엔드로 전달한다(CORS 회피).
 * 빌드 결과물에서는 VITE_SHH_API_BASE_URL로 직접 요청한다(백엔드 CORS 허용 필요).
 */
export const API_BASE_URL = import.meta.env.DEV ? '' : (import.meta.env.VITE_SHH_API_BASE_URL ?? '').replace(/\/+$/, '')

if (!import.meta.env.DEV && !API_BASE_URL) {
  console.warn('VITE_SHH_API_BASE_URL이 설정되지 않았습니다. .env 파일을 확인하세요.')
}

/** 서버가 non-2xx로 응답했거나 네트워크 요청 자체가 실패한 경우 */
export class ApiError extends Error {
  readonly status: number | null
  readonly detail: unknown

  constructor(message: string, status: number | null, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

type ValidationItem = { loc?: (string | number)[]; msg?: string }
type DomainError = { category?: string; message?: string }

/** FastAPI 오류 본문({detail: string | ValidationItem[]})을 사람이 읽을 문구로 바꾼다. */
function describeDetail(detail: unknown): string | null {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return (detail as ValidationItem[])
      .map((d) => {
        const field = d.loc?.filter((p) => p !== 'body').join('.')
        return field ? `${field}: ${d.msg ?? ''}` : (d.msg ?? '')
      })
      .join('\n')
  }
  if (detail && typeof detail === 'object') {
    const error = detail as DomainError
    if (error.message) return error.category ? `${error.message} (${error.category})` : error.message
  }
  return null
}

const STATUS_MESSAGE: Record<number, string> = {
  404: '요청한 데이터를 찾을 수 없습니다.',
  415: '지원하지 않는 파일 형식입니다. UTF-8 텍스트(.txt) 또는 텍스트 추출이 가능한 PDF만 올릴 수 있습니다.',
  422: '입력값을 확인해 주세요.',
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...init.headers },
    })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new ApiError(`서버에 연결할 수 없습니다. (${API_BASE_URL})`, null)
  }

  const payload: unknown = await response.json().catch(() => null)

  // 개발 프록시는 백엔드에 연결하지 못하면 본문 없는 5xx를 돌려준다.
  if (import.meta.env.DEV && response.status >= 500 && payload === null) {
    throw new ApiError('백엔드에 연결할 수 없습니다. 백엔드가 실행 중인지, .env의 VITE_SHH_API_BASE_URL 주소가 맞는지 확인하세요.', null)
  }

  if (!response.ok) {
    const detail = (payload as { detail?: unknown } | null)?.detail
    // FastAPI의 기본 라우트 404({"detail":"Not Found"}). 계약의 도메인 404(알 수 없는 시나리오 등)와 구분한다.
    if (response.status === 404 && detail === 'Not Found') {
      const method = (init.method ?? 'GET').toUpperCase()
      throw new ApiError(
        `실행 중인 백엔드에 ${method} ${path} API가 없습니다.\n` +
          '프론트엔드는 API 계약 v3.4(33개 API) 기준입니다. 백엔드 버전을 확인해 주세요.',
        404,
        detail,
      )
    }
    const base = STATUS_MESSAGE[response.status] ?? `서버 오류가 발생했습니다. (HTTP ${response.status})`
    const extra = response.status === 415 ? null : describeDetail(detail)
    throw new ApiError(extra ? `${base}\n${extra}` : base, response.status, detail)
  }
  return payload as T
}

export function postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
}
