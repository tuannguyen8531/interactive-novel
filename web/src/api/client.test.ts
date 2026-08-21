import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './client'

describe('API client', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('uses POST for the provider connectivity action', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            provider: 'ollama',
            model: 'llama3.2',
            reachable: true,
            latency_ms: 1
          }
        ]),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.testProviderConnection()

    expect(result[0].reachable).toBe(true)
    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchMock.mock.calls[0][0]).toBe('/api/providers/test')
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('POST')
  })

  it('deletes a world with the encoded resource path', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await api.deleteWorld('world/one')

    expect(fetchMock.mock.calls[0][0]).toBe('/api/worlds/world%2Fone')
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('DELETE')
  })

  it('requests models using secret-safe target metadata', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ provider: 'ollama', models: ['llama3.2:3b'] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.listProviderModels({
      name: 'local',
      provider: 'ollama',
      model: 'llama3.2:3b',
      base_url: 'http://localhost:11434/api',
      api_key_env: null,
      timeout_seconds: 60,
      max_retries: 2,
      backoff_base_seconds: 0.25,
      header_names: []
    })

    expect(result.models).toEqual(['llama3.2:3b'])
    expect(fetchMock.mock.calls[0][0]).toBe('/api/providers/models')
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual({
      provider: 'ollama',
      base_url: 'http://localhost:11434/api',
      api_key_env: null,
      timeout_seconds: 60
    })
  })

  it('requests the Ollama Cloud account through the local daemon', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ signed_in: true, username: 'fixture-user', detail: null }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    const account = await api.getOllamaAccount('http://localhost:11434/api', 8)

    expect(account.username).toBe('fixture-user')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/providers/ollama/account')
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual({
      base_url: 'http://localhost:11434/api',
      timeout_seconds: 8
    })
  })

  it('uses dedicated history-preserving regenerate and undo endpoints', async () => {
    const branch = {
      id: 'branch-new',
      playthrough_id: 'play-1',
      parent_branch_id: 'root',
      fork_turn_id: 'turn-1',
      head_turn_id: 'turn-1',
      depth: 1,
      head_revision: 0,
      lifecycle: 'active',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z'
    }
    const fetchMock = vi.fn().mockImplementation(async () =>
      new Response(JSON.stringify(branch), { status: 201, headers: { 'Content-Type': 'application/json' } })
    )
    vi.stubGlobal('fetch', fetchMock)

    await api.regenerateBranch('root', 'turn-2')
    await api.undoBranch('root', 'turn-2')

    expect(fetchMock.mock.calls[0][0]).toBe('/api/branches/regenerate')
    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))).toEqual({
      branch_id: 'root',
      turn_id: 'turn-2'
    })
    expect(fetchMock.mock.calls[1][0]).toBe('/api/branches/undo')
  })

  it('posts a portable bundle as raw JSON bytes for canonical import', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ format_version: 'playthrough-export' }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' }
      })
    )
    vi.stubGlobal('fetch', fetchMock)
    const body = new TextEncoder().encode('{"format_version":"playthrough-export-bundle"}').buffer

    await api.importExportBundle(body)

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(fetchMock.mock.calls[0][0]).toBe('/api/exports/import')
    expect(init.method).toBe('POST')
    expect(init.body).toBe(body)
  })

  it('retries a durable job through its stable server workflow', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ job_id: 'retry-job', status: 'queued' }), {
        status: 202,
        headers: { 'Content-Type': 'application/json' }
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    await api.retryJob('job/source')

    expect(fetchMock.mock.calls[0][0]).toBe('/api/jobs/job%2Fsource/retry')
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('POST')
  })
})
