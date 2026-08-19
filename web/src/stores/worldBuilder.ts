import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { WorldRecord } from '@/api/types'

export interface WorldDraft {
  name: string
  premise: string
  genre: string
  tone: string
}

export const useWorldBuilderStore = defineStore('worldBuilder', () => {
  const draft = ref<WorldDraft>({ name: '', premise: '', genre: 'school_romance', tone: 'warm, reflective' })
  const createdWorld = ref<WorldRecord | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function confirm(): Promise<WorldRecord> {
    loading.value = true
    error.value = null
    try {
      createdWorld.value = await api.createWorld({ ...draft.value })
      return createdWorld.value
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : String(cause)
      throw cause
    } finally {
      loading.value = false
    }
  }

  return { draft, createdWorld, loading, error, confirm }
})
