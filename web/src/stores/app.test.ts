import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { api } from '@/api/client'
import { useAppStore } from './app'

vi.mock('@/api/client', () => ({
  api: { health: vi.fn() }
}))

describe('app store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('stores a successful backend health response', async () => {
    vi.mocked(api.health).mockResolvedValue({ status: 'ok', service: 'interactive-novel', version: '0.1.0' })
    const store = useAppStore()

    await store.checkHealth()

    expect(store.health).toEqual({ status: 'ok', service: 'interactive-novel', version: '0.1.0' })
    expect(store.error).toBeNull()
    expect(store.loading).toBe(false)
  })

  it('exposes a recoverable error when health fails', async () => {
    vi.mocked(api.health).mockRejectedValue(new Error('backend unavailable'))
    const store = useAppStore()

    await store.checkHealth()

    expect(store.health).toBeNull()
    expect(store.error).toBe('backend unavailable')
    expect(store.loading).toBe(false)
  })
})
