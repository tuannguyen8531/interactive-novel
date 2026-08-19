import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { ConnectivityResult, OllamaAccount, ProviderSettings, ProviderTarget } from '@/api/types'

export const PROVIDER_ROLES = [
  'planner',
  'simulator',
  'context_validator',
  'writer',
  'critic',
  'world_builder',
  'embedding'
] as const

type ProviderName = ProviderTarget['provider']

function errorText(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause)
}

export const useProviderStore = defineStore('provider', () => {
  const settings = ref<ProviderSettings | null>(null)
  const connectivity = ref<ConnectivityResult[]>([])
  const loading = ref(false)
  const testing = ref(false)
  const ollamaAccount = ref<OllamaAccount | null>(null)
  const ollamaAccountLoading = ref(false)
  const error = ref<string | null>(null)

  async function load(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      settings.value = await api.getProviderSettings()
      ensureRoutes()
    } catch (cause) {
      error.value = errorText(cause)
    } finally {
      loading.value = false
    }
  }

  async function save(mode: 'quality' | 'fast', allowCloud: boolean): Promise<void> {
    if (!settings.value) return
    ensureRoutes()
    normalizeRoutes()
    loading.value = true
    error.value = null
    try {
      settings.value = await api.updateProviderSettings({
        targets: Object.fromEntries(
          Object.entries(settings.value.targets).map(([name, target]) => [
            name,
            {
              name: target.name,
              provider: target.provider,
              model: target.model.trim(),
              base_url: target.base_url?.trim() || null,
              api_key_env: target.api_key_env?.trim() || null,
              timeout_seconds: target.timeout_seconds,
              max_retries: target.max_retries,
              backoff_base_seconds: target.backoff_base_seconds
            }
          ])
        ),
        role_routes: settings.value.role_routes,
        mode,
        allow_cloud: allowCloud
      })
    } catch (cause) {
      error.value = errorText(cause)
      throw cause
    } finally {
      loading.value = false
    }
  }

  async function test(): Promise<void> {
    testing.value = true
    error.value = null
    try {
      connectivity.value = await api.testProviderConnection()
    } catch (cause) {
      error.value = errorText(cause)
      throw cause
    } finally {
      testing.value = false
    }
  }

  async function loadOllamaAccount(baseUrl: string | null): Promise<void> {
    ollamaAccountLoading.value = true
    try {
      ollamaAccount.value = await api.getOllamaAccount(baseUrl)
    } catch (cause) {
      ollamaAccount.value = {
        signed_in: false,
        username: null,
        detail: errorText(cause)
      }
    } finally {
      ollamaAccountLoading.value = false
    }
  }

  function ensureRoutes(): void {
    if (!settings.value) return
    const firstTarget = Object.keys(settings.value.targets)[0]
    if (!firstTarget) return
    for (const role of PROVIDER_ROLES) {
      settings.value.role_routes[role] ??= { primary_target: firstTarget, fallback_targets: [] }
    }
  }

  function normalizeRoutes(): void {
    if (!settings.value) return
    const targetNames = new Set(Object.keys(settings.value.targets))
    for (const route of Object.values(settings.value.role_routes)) {
      route.fallback_targets = [...new Set(route.fallback_targets)].filter(
        (name) => name !== route.primary_target && targetNames.has(name)
      )
    }
  }

  function addTarget(provider: ProviderName = 'ollama'): string | null {
    if (!settings.value) return null
    let index = Object.keys(settings.value.targets).length + 1
    let name = `target-${index}`
    while (settings.value.targets[name]) {
      index += 1
      name = `target-${index}`
    }
    settings.value.targets[name] = targetDefaults(name, provider)
    ensureRoutes()
    return name
  }

  function removeTarget(name: string): void {
    if (!settings.value || Object.keys(settings.value.targets).length <= 1) return
    delete settings.value.targets[name]
    const replacement = Object.keys(settings.value.targets)[0]
    for (const route of Object.values(settings.value.role_routes)) {
      if (route.primary_target === name) route.primary_target = replacement
      route.fallback_targets = route.fallback_targets.filter((targetName) => targetName !== name)
    }
    normalizeRoutes()
  }

  function renameTarget(currentName: string, requestedName: string): string | null {
    if (!settings.value?.targets[currentName]) return 'Target no longer exists.'
    const nextName = requestedName.trim()
    if (!nextName) return 'Target name cannot be empty.'
    if (nextName.length > 160) return 'Target name must be 160 characters or fewer.'
    if (nextName === currentName) return null
    if (settings.value.targets[nextName]) return `Target "${nextName}" already exists.`

    settings.value.targets = Object.fromEntries(
      Object.entries(settings.value.targets).map(([name, target]) =>
        name === currentName ? [nextName, { ...target, name: nextName }] : [name, target]
      )
    )
    for (const route of Object.values(settings.value.role_routes)) {
      if (route.primary_target === currentName) route.primary_target = nextName
      route.fallback_targets = route.fallback_targets.map((name) => (name === currentName ? nextName : name))
    }
    normalizeRoutes()
    return null
  }

  function changeProvider(name: string, provider: ProviderName): void {
    const target = settings.value?.targets[name]
    if (!target) return
    const defaults = targetDefaults(name, provider)
    Object.assign(target, {
      provider,
      model: defaults.model,
      base_url: defaults.base_url,
      api_key_env: defaults.api_key_env
    })
  }

  function setPrimaryTarget(role: string, targetName: string): void {
    const route = settings.value?.role_routes[role]
    if (!route || !settings.value?.targets[targetName]) return
    route.primary_target = targetName
    route.fallback_targets = route.fallback_targets.filter((name) => name !== targetName)
  }

  function toggleFallback(role: string, targetName: string, enabled: boolean): void {
    const route = settings.value?.role_routes[role]
    if (!route || route.primary_target === targetName) return
    const values = new Set(route.fallback_targets)
    if (enabled) values.add(targetName)
    else values.delete(targetName)
    route.fallback_targets = [...values]
  }

  return {
    settings,
    connectivity,
    loading,
    testing,
    ollamaAccount,
    ollamaAccountLoading,
    error,
    load,
    save,
    test,
    loadOllamaAccount,
    addTarget,
    removeTarget,
    renameTarget,
    changeProvider,
    setPrimaryTarget,
    toggleFallback
  }
})

function targetDefaults(name: string, provider: ProviderName): ProviderTarget {
  const defaults: Record<ProviderName, Pick<ProviderTarget, 'model' | 'base_url' | 'api_key_env'>> = {
    ollama: {
      model: 'llama3.2:3b',
      base_url: 'http://localhost:11434/api',
      api_key_env: null
    },
    gemini: {
      model: 'gemini-2.5-flash',
      base_url: null,
      api_key_env: 'GEMINI_API_KEY'
    },
    openrouter: {
      model: 'qwen/qwen3-8b',
      base_url: null,
      api_key_env: 'OPENROUTER_API_KEY'
    }
  }
  return {
    name,
    provider,
    ...defaults[provider],
    timeout_seconds: 60,
    max_retries: 2,
    backoff_base_seconds: 0.25,
    header_names: []
  }
}
