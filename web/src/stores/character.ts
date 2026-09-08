import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { usePlaythroughStore } from './playthrough'

export const useCharacterStore = defineStore('character', () => {
  const playthrough = usePlaythroughStore()
  const characters = computed(() => playthrough.characters)
  const selectedId = ref<string | null>(null)
  const selected = computed(() => characters.value.find((character) => character.id === selectedId.value) ?? null)

  async function select(characterId: string): Promise<void> {
    selectedId.value = characterId
  }

  function clear(): void {
    selectedId.value = null
  }

  return { characters, selectedId, selected, select, clear }
})
