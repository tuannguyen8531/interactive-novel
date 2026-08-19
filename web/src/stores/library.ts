import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'
import type { PlaythroughRecord, WorldRecord } from '@/api/types'

export const useLibraryStore = defineStore('library', () => {
  const worlds = ref<WorldRecord[]>([])
  const playthroughs = ref<PlaythroughRecord[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const loaded = ref(false)

  async function load(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const [worldList, playthroughList] = await Promise.all([api.listWorlds(), api.listPlaythroughs()])
      worlds.value = worldList
      playthroughs.value = playthroughList
      loaded.value = true
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : String(cause)
    } finally {
      loading.value = false
    }
  }

  return { worlds, playthroughs, loading, error, loaded, load }
})
