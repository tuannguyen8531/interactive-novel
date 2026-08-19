import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { ConnectivityResult, ProviderSettings } from '@/api/types'

function errorText(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause)
}

export const useProviderStore = defineStore('provider', () => {
  const settings = ref<ProviderSettings | null>(null)
  const connectivity = ref<ConnectivityResult[]>([])
  const loading = ref(false)
  const testing = ref(false)
  const error = ref<string | null>(null)

  async function load(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      settings.value = await api.getProviderSettings()
    } catch (cause) {
      error.value = errorText(cause)
    } finally {
      loading.value = false
    }
  }

  async function save(mode: 'quality' | 'fast', allowCloud: boolean): Promise<void> {
    if (!settings.value) return
    loading.value = true
    error.value = null
    try {
      settings.value = await api.updateProviderSettings({
        targets: settings.value.targets,
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

  return { settings, connectivity, loading, testing, error, load, save, test }
})
