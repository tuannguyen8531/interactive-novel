import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { api } from '@/api/client'
import type { JobEvent, TurnJobView } from '@/api/types'
import { useTurnJobStore, type TurnRequest } from '@/stores/turnJob'

const sse = vi.hoisted(() => ({ open: vi.fn() }))

vi.mock('@/api/sse', () => ({ openSse: sse.open }))

function job(status = 'running'): TurnJobView {
  return {
    idempotency_key: 'turn-key',
    turn_run_id: 'run-1',
    playthrough_id: 'play-1',
    branch_id: 'root',
    status,
    result: null,
    error: null,
    cancellation_requested: false,
    job_id: 'job-1',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z'
  }
}

function request(): TurnRequest {
  return {
    playthrough_id: 'play-1',
    branch_id: 'root',
    raw_input: 'open the door',
    base_revision: 1
  }
}

function event(id: string, terminal = false): JobEvent {
  return {
    id,
    job_id: 'job-1',
    turn_run_id: 'run-1',
    event_type: terminal ? 'failed' : 'writer_started',
    phase: 'writer',
    payload: terminal ? { status: 'failed', error: { message: 'provider failed' } } : {},
    payload_version: '1',
    created_at: '2026-01-01T00:00:00Z',
    terminal
  }
}

describe('turn job recovery', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    sse.open.mockReset()
    sse.open.mockReturnValue({ close: vi.fn() })
    vi.restoreAllMocks()
  })

  it('reconnects SSE using the last received event ID', async () => {
    vi.useFakeTimers()
    vi.spyOn(api, 'submitTurn').mockResolvedValue(job())
    const store = useTurnJobStore()

    await store.submit(request())
    const firstHandlers = sse.open.mock.calls[0][1]
    firstHandlers.onEvent({ id: '7', event: 'writer_started', data: JSON.stringify(event('7')) })
    firstHandlers.onError(new Error('network lost'))
    await vi.advanceTimersByTimeAsync(500)

    expect(sse.open).toHaveBeenCalledTimes(2)
    expect(sse.open.mock.calls[1][2]).toEqual({ lastEventId: '7' })
    vi.useRealTimers()
  })

  it('uses the server-owned idempotent retry workflow for a terminal failure', async () => {
    const submit = vi.spyOn(api, 'submitTurn').mockImplementation(async (payload, idempotencyKey) => ({
      ...job(),
      idempotency_key: idempotencyKey ?? '',
      turn_run_id: payload.turn_run_id ?? ''
    }))
    const retry = vi.spyOn(api, 'retryJob').mockResolvedValue({
      ...job(),
      idempotency_key: 'retry:job-1',
      turn_run_id: 'retry-run',
      job_id: 'retry-job'
    })
    const store = useTurnJobStore()

    await store.submit(request())
    const handlers = sse.open.mock.calls[0][1]
    handlers.onEvent({ id: '8', event: 'failed', data: JSON.stringify(event('8', true)) })
    await store.retry()

    expect(submit).toHaveBeenCalledOnce()
    expect(retry).toHaveBeenCalledWith('job-1')
    expect(store.current?.job_id).toBe('retry-job')
  })

  it('reuses submission identity after an uncertain network failure', async () => {
    const submit = vi.spyOn(api, 'submitTurn')
      .mockRejectedValueOnce(new Error('connection reset'))
      .mockImplementationOnce(async (payload, idempotencyKey) => ({
        ...job(),
        idempotency_key: idempotencyKey ?? '',
        turn_run_id: payload.turn_run_id ?? ''
      }))
    const store = useTurnJobStore()

    await expect(store.submit(request())).rejects.toThrow('connection reset')
    const firstRequest = submit.mock.calls[0][0]
    const firstKey = submit.mock.calls[0][1]
    await store.retry()

    expect(submit.mock.calls[1][1]).toBe(firstKey)
    expect(submit.mock.calls[1][0].turn_run_id).toBe(firstRequest.turn_run_id)
  })

  it('discovers an active durable job after a page reload', async () => {
    vi.spyOn(api, 'listJobs').mockResolvedValue([job('completed'), { ...job(), job_id: 'job-active' }])
    const store = useTurnJobStore()

    const resumed = await store.resume('play-1')

    expect(resumed?.job_id).toBe('job-active')
    expect(sse.open.mock.calls[0][0]).toContain('/api/jobs/job-active/events')
  })
})
