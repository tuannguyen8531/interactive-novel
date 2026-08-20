import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import { openSse, type SseClient } from '@/api/sse'
import type { JobEvent, TurnJobView, TurnRecord } from '@/api/types'

export interface TurnRequest {
  playthrough_id: string
  branch_id: string
  raw_input: string
  base_revision: number
  actor_id?: string
  parent_turn_id?: string | null
  config_snapshot_id?: string
  turn_run_id?: string
}

const RESUME_STORAGE_KEY = 'interactive-novel.active-turn.v1'
const TERMINAL_STATUSES = new Set(['completed', 'failed', 'cancelled', 'interrupted'])

function errorText(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause)
}

function newId(prefix: string): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return `${prefix}-${crypto.randomUUID()}`
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export const useTurnJobStore = defineStore('turnJob', () => {
  const current = ref<TurnJobView | null>(null)
  const events = ref<JobEvent[]>([])
  const progress = ref('idle')
  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastRequest = ref<TurnRequest | null>(null)
  let stream: SseClient | null = null
  let lastEventId: string | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectAttempts = 0
  let streamGeneration = 0
  let lastIdempotencyKey: string | null = null
  let fixtureCancelled = false
  let lastFixtureCommit: (() => TurnRecord) | null = null

  const active = computed(() => current.value !== null && !TERMINAL_STATUSES.has(current.value.status))
  const terminal = computed(() => current.value !== null && !active.value)

  function closeStream(): void {
    streamGeneration += 1
    if (reconnectTimer !== null) clearTimeout(reconnectTimer)
    reconnectTimer = null
    stream?.close()
    stream = null
  }

  function setError(cause: unknown): void {
    error.value = errorText(cause)
    loading.value = false
  }

  async function submit(request: TurnRequest, existingIdempotencyKey?: string): Promise<TurnJobView> {
    closeStream()
    loading.value = true
    error.value = null
    events.value = []
    progress.value = 'Submitting action…'
    const preparedRequest = { ...request, turn_run_id: request.turn_run_id ?? newId('run') }
    lastRequest.value = preparedRequest
    lastEventId = null
    lastFixtureCommit = null
    try {
      const idempotencyKey = existingIdempotencyKey ?? newId('turn')
      lastIdempotencyKey = idempotencyKey
      const job = await api.submitTurn(preparedRequest, idempotencyKey)
      current.value = job
      persistResumeState()
      const jobId = job.job_id
      if (jobId) openStream(jobId)
      else loading.value = false
      return job
    } catch (cause) {
      setError(cause)
      throw cause
    }
  }

  function openStream(jobId: string): void {
    closeStream()
    const generation = streamGeneration
    stream = openSse(api.jobEventsUrl(jobId), {
      onOpen: () => {
        if (generation !== streamGeneration) return
        reconnectAttempts = 0
        progress.value = 'Connected to turn progress.'
      },
      onEvent: (raw) => {
        if (generation !== streamGeneration) return
        try {
          const event = JSON.parse(raw.data) as JobEvent
          lastEventId = raw.id ?? event.id ?? lastEventId
          if (!events.value.some((existing) => existing.id === event.id)) events.value.push(event)
          progress.value = progressLabel(event)
          persistResumeState()
          if (event.terminal || TERMINAL_STATUSES.has(event.event_type)) {
            const terminal = terminalJob(event)
            current.value = mergeJob(current.value, terminal)
            if (terminal.status === 'failed' || terminal.status === 'interrupted') {
              error.value = jobErrorText(terminal.error) ?? `Turn ${terminal.status}.`
            }
            loading.value = false
            closeStream()
            clearResumeState()
          }
        } catch (cause) {
          setError(new Error(`Invalid progress event: ${errorText(cause)}`))
        }
      },
      onError: (cause) => {
        if (generation !== streamGeneration || terminal.value) return
        progress.value = `Connection lost; reconnecting… (${errorText(cause)})`
        scheduleReconnect(jobId, generation)
      },
      onClose: () => {
        if (generation !== streamGeneration || terminal.value) return
        progress.value = 'Progress stream closed; reconnecting…'
        scheduleReconnect(jobId, generation)
      }
    }, { lastEventId })
  }

  function scheduleReconnect(jobId: string, generation: number): void {
    if (reconnectTimer !== null || generation !== streamGeneration || terminal.value) return
    const delayMs = Math.min(500 * 2 ** reconnectAttempts, 5000)
    reconnectAttempts += 1
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      if (generation === streamGeneration && !terminal.value) openStream(jobId)
    }, delayMs)
  }

  async function resume(playthroughId: string): Promise<TurnJobView | null> {
    closeStream()
    current.value = null
    error.value = null
    events.value = []
    loading.value = false
    progress.value = 'idle'
    const saved = readResumeState()
    let job: TurnJobView | null = null
    try {
      if (saved?.job.playthrough_id === playthroughId && saved.job.job_id) {
        lastEventId = saved.lastEventId
        job = await api.getJob(saved.job.job_id)
      }
      if (!job || TERMINAL_STATUSES.has(job.status)) {
        const jobs = await api.listJobs(playthroughId)
        job = jobs
          .filter((candidate) => !TERMINAL_STATUSES.has(candidate.status))
          .sort((left, right) => right.updated_at.localeCompare(left.updated_at))[0] ?? null
        lastEventId = null
      }
      if (!job) {
        clearResumeState()
        return null
      }
      current.value = job
      loading.value = true
      progress.value = 'Resuming turn progress…'
      persistResumeState()
      if (job.job_id) openStream(job.job_id)
      return job
    } catch (cause) {
      setError(cause)
      return null
    }
  }

  async function cancel(): Promise<void> {
    if (!current.value || !active.value) return
    if (current.value.job_id?.startsWith('fixture-job-')) {
      fixtureCancelled = true
      current.value = { ...current.value, status: 'cancelled', cancellation_requested: true }
      progress.value = 'Action cancelled.'
      loading.value = false
      return
    }
    try {
      const jobId = current.value.job_id
      if (!jobId) return
      current.value = await api.cancelJob(jobId)
      progress.value = 'Cancellation requested.'
    } catch (cause) {
      setError(cause)
      throw cause
    }
  }

  async function retry(): Promise<TurnJobView | null> {
    if (lastRequest.value && lastFixtureCommit) return runFixture(lastRequest.value, lastFixtureCommit)
    if (current.value?.job_id && TERMINAL_STATUSES.has(current.value.status)) {
      closeStream()
      loading.value = true
      error.value = null
      events.value = []
      progress.value = 'Retrying action…'
      try {
        const retried = await api.retryJob(current.value.job_id)
        current.value = retried
        lastIdempotencyKey = retried.idempotency_key
        lastEventId = null
        persistResumeState()
        if (retried.job_id) openStream(retried.job_id)
        else loading.value = false
        return retried
      } catch (cause) {
        setError(cause)
        throw cause
      }
    }
    return lastRequest.value ? submit(lastRequest.value, lastIdempotencyKey ?? undefined) : null
  }

  async function runFixture(request: TurnRequest, commit: () => TurnRecord): Promise<TurnJobView> {
    closeStream()
    loading.value = true
    error.value = null
    events.value = []
    progress.value = 'Preparing fixture turn…'
    lastRequest.value = { ...request }
    lastFixtureCommit = commit
    fixtureCancelled = false
    const jobId = newId('fixture-job')
    const job: TurnJobView = {
      idempotency_key: jobId,
      turn_run_id: newId('fixture-run'),
      playthrough_id: request.playthrough_id,
      branch_id: request.branch_id,
      status: 'running',
      result: null,
      error: null,
      cancellation_requested: false,
      job_id: jobId,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }
    current.value = job
    await delay(12)
    publishFixtureEvent(jobId, 'context_started', 'context', 'Reading branch context.')
    await delay(12)
    publishFixtureEvent(jobId, 'writer_token', 'writer', 'Draft narrative ready.')
    await delay(12)
    if (fixtureCancelled) {
      current.value = { ...job, status: 'cancelled', cancellation_requested: true, updated_at: new Date().toISOString() }
      loading.value = false
      progress.value = 'Action cancelled.'
      return current.value
    }
    let turn: TurnRecord
    try {
      turn = commit()
    } catch (cause) {
      const failed: TurnJobView = {
        ...job,
        status: 'failed',
        error: { message: errorText(cause) },
        updated_at: new Date().toISOString()
      }
      current.value = failed
      loading.value = false
      error.value = errorText(cause)
      progress.value = 'Turn failed; retry is available.'
      return failed
    }
    const completed: TurnJobView = {
      ...job,
      status: 'completed',
      result: turn,
      updated_at: new Date().toISOString()
    }
    publishFixtureEvent(jobId, 'completed', 'job', 'Canonical fixture turn saved.', true)
    current.value = completed
    loading.value = false
    progress.value = 'Turn saved.'
    return completed
  }

  function publishFixtureEvent(jobId: string, eventType: string, phase: string, message: string, terminal = false): void {
    events.value.push({
      id: `${jobId}-${events.value.length + 1}`,
      job_id: jobId,
      turn_run_id: current.value?.turn_run_id ?? jobId,
      event_type: eventType,
      phase,
      payload: { message },
      payload_version: 'fixture-1',
      created_at: new Date().toISOString(),
      terminal
    })
    progress.value = message
  }

  function persistResumeState(): void {
    const storage = persistableStorage()
    if (!storage || !current.value || TERMINAL_STATUSES.has(current.value.status)) return
    storage.setItem(RESUME_STORAGE_KEY, JSON.stringify({ job: current.value, lastEventId }))
  }

  function clearResumeState(): void {
    persistableStorage()?.removeItem(RESUME_STORAGE_KEY)
  }

  function clear(): void {
    closeStream()
    current.value = null
    events.value = []
    progress.value = 'idle'
    error.value = null
    loading.value = false
    lastFixtureCommit = null
    lastEventId = null
    lastIdempotencyKey = null
    clearResumeState()
  }

  return {
    current,
    events,
    progress,
    loading,
    error,
    lastRequest,
    active,
    terminal,
    submit,
    resume,
    cancel,
    retry,
    runFixture,
    clear
  }
})

function persistableStorage(): Storage | null {
  return typeof window === 'undefined' ? null : window.sessionStorage
}

function readResumeState(): { job: TurnJobView; lastEventId: string | null } | null {
  const storage = persistableStorage()
  const raw = storage?.getItem(RESUME_STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as { job: TurnJobView; lastEventId: string | null }
  } catch {
    storage?.removeItem(RESUME_STORAGE_KEY)
    return null
  }
}

function progressLabel(event: JobEvent): string {
  const message = event.payload.message
  if (typeof message === 'string') return message
  return event.event_type.replaceAll('_', ' ')
}

function terminalJob(event: JobEvent): TurnJobView {
  const payloadStatus = event.payload.status
  const status = typeof payloadStatus === 'string' ? payloadStatus : event.event_type
  return {
    idempotency_key: '',
    turn_run_id: event.turn_run_id,
    playthrough_id: '',
    branch_id: '',
    status,
    result: event.payload.result ?? null,
    error: isRecord(event.payload.error) ? event.payload.error : null,
    cancellation_requested: status === 'cancelled',
    job_id: event.job_id,
    created_at: event.created_at,
    updated_at: event.created_at
  }
}

function mergeJob(current: TurnJobView | null, terminal: TurnJobView): TurnJobView {
  return current
    ? {
        ...current,
        ...terminal,
        idempotency_key: current.idempotency_key,
        turn_run_id: current.turn_run_id,
        playthrough_id: current.playthrough_id,
        branch_id: current.branch_id
      }
    : terminal
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function jobErrorText(value: Record<string, unknown> | null): string | null {
  if (value === null) return null
  if (typeof value.message === 'string') return value.message
  if (Array.isArray(value.diagnostics)) {
    const messages = value.diagnostics
      .map((item) => (isRecord(item) && typeof item.message === 'string' ? item.message : null))
      .filter((item): item is string => item !== null)
    if (messages.length > 0) return messages.join('; ')
  }
  return typeof value.code === 'string' ? value.code : null
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds))
}
