import { ApiError } from '../api/client'

/** 화면별 비동기 요청 상태 */
export type Async<T> = { status: 'loading' } | { status: 'error'; message: string } | { status: 'success'; data: T }

export const errorMessage = (err: unknown) => (err instanceof ApiError ? err.message : '알 수 없는 오류가 발생했습니다.')
export const isAbort = (err: unknown) => err instanceof DOMException && err.name === 'AbortError'
