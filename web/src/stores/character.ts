import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import { usePlaythroughStore } from './playthrough'
import type { MemoryView, RelationshipView } from '@/api/types'

export const useCharacterStore = defineStore('character', () => {
  const playthrough = usePlaythroughStore()
  const characters = computed(() => playthrough.characters)
  const selectedId = ref<string | null>(null)
  const memories = ref<MemoryView[]>([])
  const relationships = ref<RelationshipView[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const selected = computed(() => characters.value.find((character) => character.id === selectedId.value) ?? null)

  async function select(characterId: string): Promise<void> {
    selectedId.value = characterId
    if (playthrough.fixtureMode || !playthrough.playthrough || !playthrough.activeBranch) return
    loading.value = true
    error.value = null
    try {
      const [memory, relation] = await Promise.all([
        api.characterMemory(playthrough.playthrough.id, playthrough.activeBranch.id, characterId),
        api.relationships(playthrough.playthrough.id, playthrough.activeBranch.id)
      ])
      memories.value = memory
      relationships.value = relation.filter((item) => item.source_id === characterId || item.target_id === characterId)
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : String(cause)
    } finally {
      loading.value = false
    }
  }

  function clear(): void {
    selectedId.value = null
    memories.value = []
    relationships.value = []
    error.value = null
  }

  return { characters, selectedId, selected, memories, relationships, loading, error, select, clear }
})
