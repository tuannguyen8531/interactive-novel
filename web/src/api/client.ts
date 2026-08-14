import type { ApiErrorBody, HealthResponse } from './types'

const BASE_URL = ''

let authToken: string | null = null

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly details: Record<string, unknown>

  constructor(message: string, status: number, code: string, details: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
  }
}

export function setAuthToken(token: string | null): void {
  authToken = token
}

export function getAuthToken(): string | null {
  return authToken
}

function requestHeaders(init: RequestInit): Headers {
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (authToken) {
    headers.set('Authorization', `Bearer ${authToken}`)
  }
  return headers
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== 'object' || value === null || !('error' in value)) return false
  const error = value.error
  return typeof error === 'object' && error !== null && 'code' in error && 'message' in error
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: requestHeaders(init)
  })
  if (!response.ok) {
    let code = 'http_error'
    let message = `${response.status} ${response.statusText}`
    let details: Record<string, unknown> = {}
    try {
      const body: unknown = await response.json()
      if (isApiErrorBody(body)) {
        code = body.error.code
        message = body.error.message
        details = body.error.details ?? {}
      }
    } catch {
      // Keep the status-based fallback when the server returned non-JSON data.
    }
    throw new ApiError(message, response.status, code, details)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  health: (): Promise<HealthResponse> => request<HealthResponse>('/api/health')
}
