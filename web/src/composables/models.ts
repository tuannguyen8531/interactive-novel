import { ref, toValue, watch, type MaybeRefOrGetter } from 'vue'
import { api } from '@/api/client'
import type { ProviderTarget } from '@/api/types'

export function useProviderModels(target: MaybeRefOrGetter<ProviderTarget>) {
  const models = ref<string[]>([])
  const loading = ref(false)
  const loadError = ref<string | null>(null)

  async function refresh(): Promise<void> {
    loading.value = true
    loadError.value = null
    try {
      models.value = (await api.listProviderModels(toValue(target))).models
    } catch (cause) {
      loadError.value = cause instanceof Error ? cause.message : String(cause)
      models.value = []
    } finally {
      loading.value = false
    }
  }

  watch(
    () => {
      const value = toValue(target)
      return `${value.provider}\n${value.base_url ?? ''}\n${value.api_key_env ?? ''}`
    },
    refresh,
    { immediate: true }
  )

  return { models, loading, loadError, refresh }
}
