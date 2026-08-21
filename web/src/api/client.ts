import type {
  ApiErrorBody,
  BackupRecord,
  BackupReport,
  BranchRecord,
  CharacterView,
  ConnectivityResult,
  JobEvent,
  InspectorPayload,
  MemoryView,
  OllamaAccount,
  PlaythroughExport,
  PlaythroughRecord,
  ProviderSettings,
  ProviderModelsResponse,
  ProviderTarget,
  RelationshipView,
  TimelineEvent,
  TurnJobView,
  WorldConfirmation,
  WorldRecord,
  WorldSeed,
  StoryTemplate
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

async function requestBlob(path: string): Promise<Blob> {
  const response = await fetch(`${BASE_URL}${path}`, { headers: requestHeaders({}) })
  if (!response.ok) throw new ApiError(`${response.status} ${response.statusText}`, response.status, 'http_error')
  return response.blob()
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
  listStoryTemplates: (): Promise<StoryTemplate[]> => request<StoryTemplate[]>('/api/story-templates'),
  deleteWorld: (worldId: string): Promise<void> =>
    request<void>(`/api/worlds/${encodeURIComponent(worldId)}`, { method: 'DELETE' }),
  generateWorldDraft: (prompt: string, templateId = 'school_romance'): Promise<WorldSeed> =>
    request<WorldSeed>('/api/world-drafts', jsonBody({ prompt, template_id: templateId })),
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
  regenerateBranch: (branchId: string, turnId: string): Promise<BranchRecord> =>
    request<BranchRecord>('/api/branches/regenerate', jsonBody({ branch_id: branchId, turn_id: turnId })),
  undoBranch: (branchId: string, headTurnId: string): Promise<BranchRecord> =>
    request<BranchRecord>('/api/branches/undo', jsonBody({ branch_id: branchId, head_turn_id: headTurnId })),
  switchBranch: (branchId: string, playthroughId: string): Promise<BranchRecord> =>
    request<BranchRecord>(`/api/branches/${encodeURIComponent(branchId)}/switch`, jsonBody({ playthrough_id: playthroughId })),
  branchAncestry: (branchId: string): Promise<BranchRecord[]> =>
    request<BranchRecord[]>(`/api/branches/${encodeURIComponent(branchId)}/ancestry`),
  exportPlaythrough: (playthroughId: string): Promise<PlaythroughExport> =>
    request<PlaythroughExport>(`/api/playthroughs/${encodeURIComponent(playthroughId)}/export`),
  downloadExportBundle: (playthroughId: string): Promise<Blob> =>
    requestBlob(`/api/playthroughs/${encodeURIComponent(playthroughId)}/export/bundle`),
  importExportBundle: (body: ArrayBuffer): Promise<PlaythroughExport> =>
    request<PlaythroughExport>('/api/exports/import', { method: 'POST', body }),
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
  inspector: (playthroughId: string, branchId: string): Promise<InspectorPayload> =>
    request<InspectorPayload>(
      `/api/playthroughs/${encodeURIComponent(playthroughId)}/branches/${encodeURIComponent(branchId)}/inspector`
    ),
  listBackups: (): Promise<BackupRecord[]> => request<BackupRecord[]>('/api/backups'),
  createBackup: (): Promise<BackupReport> => request<BackupReport>('/api/backups', jsonBody({})),
  restoreBackup: (name: string): Promise<BackupReport> =>
    request<BackupReport>('/api/backups/restore', jsonBody({ name })),
  databaseIntegrity: (): Promise<{ path: string; ok: boolean; message: string }> =>
    request<{ path: string; ok: boolean; message: string }>('/api/backups/integrity'),
  submitFeedback: (payload: { rating: number; comment: string; category: string; turn_run_id?: string }): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>('/api/feedback', jsonBody(payload)),
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
  retryJob: (jobId: string): Promise<TurnJobView> =>
    request<TurnJobView>(`/api/jobs/${encodeURIComponent(jobId)}/retry`, { method: 'POST' }),
  jobEventsUrl: (jobId: string): string =>
    `${BASE_URL}/api/jobs/${encodeURIComponent(jobId)}/events`,
  getProviderSettings: (): Promise<ProviderSettings | null> => request<ProviderSettings | null>('/api/providers/settings'),
  updateProviderSettings: (payload: Record<string, unknown>): Promise<ProviderSettings> =>
    request<ProviderSettings>('/api/providers/settings', jsonPut(payload)),
  listProviderModels: (target: ProviderTarget): Promise<ProviderModelsResponse> =>
    request<ProviderModelsResponse>('/api/providers/models', jsonBody({
      provider: target.provider,
      base_url: target.base_url,
      api_key_env: target.api_key_env,
      timeout_seconds: target.timeout_seconds
    })),
  getOllamaAccount: (baseUrl: string | null, timeoutSeconds = 10): Promise<OllamaAccount> =>
    request<OllamaAccount>('/api/providers/ollama/account', jsonBody({
      base_url: baseUrl,
      timeout_seconds: timeoutSeconds
    })),
  testProviderConnection: (): Promise<ConnectivityResult[]> =>
    request<ConnectivityResult[]>('/api/providers/test', { method: 'POST' })
}

export type { JobEvent }
