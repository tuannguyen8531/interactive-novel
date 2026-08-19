import type {
  ApiErrorBody,
  BranchRecord,
  CharacterView,
  ConnectivityResult,
  JobEvent,
  MemoryView,
  PlaythroughExport,
  PlaythroughRecord,
  ProviderSettings,
  RelationshipView,
  TimelineEvent,
  TurnJobView,
  WorldConfirmation,
  WorldRecord,
  WorldSeed
} from './types'
import type { HealthResponse } from './types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

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
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
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

function query(params: Record<string, string | number | null | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') search.set(key, String(value))
  }
  const encoded = search.toString()
  return encoded ? `?${encoded}` : ''
}

function jsonBody(value: unknown): RequestInit {
  return { method: 'POST', body: JSON.stringify(value) }
}

function jsonPut(value: unknown): RequestInit {
  return { method: 'PUT', body: JSON.stringify(value) }
}

export const api = {
  health: (): Promise<HealthResponse> => request<HealthResponse>('/api/health'),
  listWorlds: (): Promise<WorldRecord[]> => request<WorldRecord[]>('/api/worlds'),
  getWorld: (worldId: string): Promise<WorldRecord> => request<WorldRecord>(`/api/worlds/${encodeURIComponent(worldId)}`),
  createWorld: (payload: Record<string, unknown>): Promise<WorldRecord> =>
    request<WorldRecord>('/api/worlds', jsonBody(payload)),
  generateWorldDraft: (prompt: string): Promise<WorldSeed> =>
    request<WorldSeed>('/api/world-drafts', jsonBody({ prompt })),
  validateWorldDraft: (draft: WorldSeed): Promise<WorldSeed> =>
    request<WorldSeed>('/api/world-drafts/validate', jsonBody({ draft })),
  confirmWorldDraft: (draft: WorldSeed, worldId?: string): Promise<WorldConfirmation> =>
    request<WorldConfirmation>('/api/world-drafts/confirm', jsonBody({ draft, world_id: worldId })),
  listPlaythroughs: (worldId?: string): Promise<PlaythroughRecord[]> =>
    request<PlaythroughRecord[]>(`/api/playthroughs${query({ world_id: worldId })}`),
  getPlaythrough: (playthroughId: string): Promise<PlaythroughRecord> =>
    request<PlaythroughRecord>(`/api/playthroughs/${encodeURIComponent(playthroughId)}`),
  createPlaythrough: (payload: Record<string, unknown>): Promise<PlaythroughRecord> =>
    request<PlaythroughRecord>('/api/playthroughs', jsonBody(payload)),
  listBranches: (playthroughId: string): Promise<BranchRecord[]> =>
    request<BranchRecord[]>(`/api/playthroughs/${encodeURIComponent(playthroughId)}/branches`),
  createRootBranch: (payload: { playthrough_id: string; branch_id?: string }): Promise<BranchRecord> =>
    request<BranchRecord>('/api/branches/root', jsonBody(payload)),
  forkBranch: (payload: { parent_branch_id: string; fork_turn_id: string; branch_id?: string }): Promise<BranchRecord> =>
    request<BranchRecord>('/api/branches/fork', jsonBody(payload)),
  switchBranch: (branchId: string, playthroughId: string): Promise<BranchRecord> =>
    request<BranchRecord>(`/api/branches/${encodeURIComponent(branchId)}/switch`, jsonBody({ playthrough_id: playthroughId })),
  branchAncestry: (branchId: string): Promise<BranchRecord[]> =>
    request<BranchRecord[]>(`/api/branches/${encodeURIComponent(branchId)}/ancestry`),
  exportPlaythrough: (playthroughId: string): Promise<PlaythroughExport> =>
    request<PlaythroughExport>(`/api/playthroughs/${encodeURIComponent(playthroughId)}/export`),
  listCharacters: (playthroughId: string, branchId?: string): Promise<CharacterView[]> =>
    request<CharacterView[]>(
      `/api/playthroughs/${encodeURIComponent(playthroughId)}/characters${query({ branch_id: branchId })}`
    ),
  getCharacter: (playthroughId: string, characterId: string, branchId?: string): Promise<CharacterView> =>
    request<CharacterView>(
      `/api/playthroughs/${encodeURIComponent(playthroughId)}/characters/${encodeURIComponent(characterId)}${query({ branch_id: branchId })}`
    ),
  characterMemory: (playthroughId: string, branchId: string, characterId: string): Promise<MemoryView[]> =>
    request<MemoryView[]>(
      `/api/playthroughs/${encodeURIComponent(playthroughId)}/branches/${encodeURIComponent(branchId)}/characters/${encodeURIComponent(characterId)}/memory`
    ),
  relationships: (playthroughId: string, branchId: string): Promise<RelationshipView[]> =>
    request<RelationshipView[]>(
      `/api/playthroughs/${encodeURIComponent(playthroughId)}/branches/${encodeURIComponent(branchId)}/relationships`
    ),
  timeline: (playthroughId: string, branchId: string): Promise<TimelineEvent[]> =>
    request<TimelineEvent[]>(
      `/api/playthroughs/${encodeURIComponent(playthroughId)}/branches/${encodeURIComponent(branchId)}/timeline`
    ),
  submitTurn: (
    payload: {
      playthrough_id: string
      branch_id: string
      raw_input: string
      base_revision: number
      actor_id?: string
      turn_run_id?: string
      idempotency_key?: string
      parent_turn_id?: string | null
      config_snapshot_id?: string
    },
    idempotencyKey?: string
  ): Promise<TurnJobView> =>
    request<TurnJobView>('/api/turns', {
      ...jsonBody(payload),
      headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined
    }),
  getJob: (jobId: string): Promise<TurnJobView> => request<TurnJobView>(`/api/jobs/${encodeURIComponent(jobId)}`),
  listJobs: (playthroughId?: string, branchId?: string): Promise<TurnJobView[]> =>
    request<TurnJobView[]>(`/api/jobs${query({ playthrough_id: playthroughId, branch_id: branchId })}`),
  cancelJob: (jobId: string): Promise<TurnJobView> =>
    request<TurnJobView>(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' }),
  jobEventsUrl: (jobId: string): string =>
    `${BASE_URL}/api/jobs/${encodeURIComponent(jobId)}/events`,
  getProviderSettings: (): Promise<ProviderSettings | null> => request<ProviderSettings | null>('/api/providers/settings'),
  updateProviderSettings: (payload: Record<string, unknown>): Promise<ProviderSettings> =>
    request<ProviderSettings>('/api/providers/settings', jsonPut(payload)),
  testProviderConnection: (): Promise<ConnectivityResult[]> =>
    request<ConnectivityResult[]>('/api/providers/test', { method: 'POST' })
}

export type { JobEvent }
