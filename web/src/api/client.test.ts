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
})
