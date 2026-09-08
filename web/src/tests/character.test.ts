import { createPinia, setActivePinia } from 'pinia'
import { expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import { FIXTURE_PLAYTHROUGH_ID } from '@/fixtures/fixture'
import { useCharacterStore } from '@/stores/character'
import { usePlaythroughStore } from '@/stores/playthrough'

it('selects a public profile without requesting NPC internals', async () => {
  setActivePinia(createPinia())
  const playthrough = usePlaythroughStore()
  await playthrough.open(FIXTURE_PLAYTHROUGH_ID)
  playthrough.fixtureMode = false
  const memory = vi.spyOn(api, 'characterMemory')
  const relationships = vi.spyOn(api, 'relationships')
  try {
    const store = useCharacterStore()
    await store.select(playthrough.characters[0]!.id)
    expect(store.selected?.id).toBe(playthrough.characters[0]!.id)
    expect(memory).not.toHaveBeenCalled()
    expect(relationships).not.toHaveBeenCalled()
  } finally {
    vi.restoreAllMocks()
  }
})
