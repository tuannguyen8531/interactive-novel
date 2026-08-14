import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'
import type { HealthResponse } from '@/api/types'

export const useAppStore = defineStore('app', () => {
  const health = ref<HealthResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function checkHealth(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      health.value = await api.health()
    } catch (cause) {
      health.value = null
      error.value = cause instanceof Error ? cause.message : String(cause)
    } finally {
      loading.value = false
    }
  }

  return { health, loading, error, checkHealth }
})
