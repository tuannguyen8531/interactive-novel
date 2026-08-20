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
})
