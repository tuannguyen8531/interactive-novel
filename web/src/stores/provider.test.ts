import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { api } from '@/api/client'
import type { ProviderSettings } from '@/api/types'
import { useProviderStore } from './provider'

vi.mock('@/api/client', () => ({
  api: {
    getProviderSettings: vi.fn(),
    updateProviderSettings: vi.fn(),
    testProviderConnection: vi.fn(),
    getOllamaAccount: vi.fn()
  }
}))

function fixture(): ProviderSettings {
  return {
    schema_version: 1,
    mode: 'quality',
    allow_cloud: false,
    targets: {
      local: {
        name: 'local',
        provider: 'ollama',
        model: 'llama3.2:3b',
        base_url: 'http://localhost:11434/api',
        api_key_env: null,
        timeout_seconds: 60,
        max_retries: 2,
        backoff_base_seconds: 0.25,
        header_names: []
      }
    },
    role_routes: {
      planner: { primary_target: 'local', fallback_targets: [] }
    }
  }
}

describe('provider store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('edits targets and role routing while keeping secrets environment-only', async () => {
    vi.mocked(api.getProviderSettings).mockResolvedValue(fixture())
    vi.mocked(api.updateProviderSettings).mockImplementation(async (payload) => ({
      ...(payload as unknown as ProviderSettings),
      schema_version: 1
    }))
    const store = useProviderStore()
    await store.load()

    const cloudName = store.addTarget('gemini')!
    store.setPrimaryTarget('writer', cloudName)
    store.toggleFallback('writer', 'local', true)
    await store.save('fast', true)

    const payload = vi.mocked(api.updateProviderSettings).mock.calls[0][0] as Record<string, any>
    expect(payload.mode).toBe('fast')
    expect(payload.targets[cloudName]).toMatchObject({
      provider: 'gemini',
      model: 'gemini-2.5-flash',
      api_key_env: 'GEMINI_API_KEY'
    })
    expect(payload.targets[cloudName]).not.toHaveProperty('api_key')
    expect(payload.targets[cloudName]).not.toHaveProperty('header_names')
    expect(payload.role_routes.writer).toEqual({ primary_target: cloudName, fallback_targets: ['local'] })
    expect(Object.keys(payload.role_routes)).toEqual(expect.arrayContaining(['embedding', 'world_builder']))
  })

  it('reassigns routes when a target is removed', async () => {
    const value = fixture()
    value.targets.secondary = {
      ...value.targets.local,
      name: 'secondary',
      model: 'another-model'
    }
    value.role_routes.writer = { primary_target: 'secondary', fallback_targets: ['local'] }
    vi.mocked(api.getProviderSettings).mockResolvedValue(value)
    const store = useProviderStore()
    await store.load()

    store.removeTarget('secondary')

    expect(store.settings?.role_routes.writer).toEqual({ primary_target: 'local', fallback_targets: [] })
  })

  it('loads the Ollama Cloud account without exposing credentials', async () => {
    vi.mocked(api.getOllamaAccount).mockResolvedValue({
      signed_in: true,
      username: 'fixture-user',
      detail: null
    })
    const store = useProviderStore()

    await store.loadOllamaAccount('http://localhost:11434/api')

    expect(store.ollamaAccount?.username).toBe('fixture-user')
    expect(api.getOllamaAccount).toHaveBeenCalledWith('http://localhost:11434/api')
  })

  it('keeps multiple fallback targets in selection order', async () => {
    const value = fixture()
    value.targets.secondary = { ...value.targets.local, name: 'secondary', model: 'secondary-model' }
    value.targets.third = { ...value.targets.local, name: 'third', model: 'third-model' }
    vi.mocked(api.getProviderSettings).mockResolvedValue(value)
    const store = useProviderStore()
    await store.load()

    store.toggleFallback('writer', 'secondary', true)
    store.toggleFallback('writer', 'third', true)

    expect(store.settings?.role_routes.writer.fallback_targets).toEqual(['secondary', 'third'])
    store.setPrimaryTarget('writer', 'secondary')
    expect(store.settings?.role_routes.writer).toEqual({
      primary_target: 'secondary',
      fallback_targets: ['third']
    })
  })

  it('renames a target and updates every route reference atomically', async () => {
    const value = fixture()
    value.targets.secondary = { ...value.targets.local, name: 'secondary', model: 'secondary-model' }
    value.role_routes.writer = { primary_target: 'secondary', fallback_targets: ['local'] }
    value.role_routes.critic = { primary_target: 'local', fallback_targets: ['secondary'] }
    vi.mocked(api.getProviderSettings).mockResolvedValue(value)
    const store = useProviderStore()
    await store.load()

    expect(store.renameTarget('secondary', 'creative')).toBeNull()

    expect(store.settings?.targets.secondary).toBeUndefined()
    expect(store.settings?.targets.creative.name).toBe('creative')
    expect(store.settings?.role_routes.writer.primary_target).toBe('creative')
    expect(store.settings?.role_routes.critic.fallback_targets).toEqual(['creative'])
    expect(store.renameTarget('creative', 'local')).toBe('Target "local" already exists.')
  })
})
