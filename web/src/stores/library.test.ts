import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { api } from '@/api/client'
import type { PlaythroughRecord, WorldRecord } from '@/api/types'
import { useLibraryStore } from './library'

describe('library store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('removes the deleted world and all of its local playthroughs', async () => {
    vi.spyOn(api, 'deleteWorld').mockResolvedValue()
    const store = useLibraryStore()
    store.worlds = [
      { id: 'world-1', name: 'First' } as WorldRecord,
      { id: 'world-2', name: 'Second' } as WorldRecord
    ]
    store.playthroughs = [
      { id: 'play-1', world_id: 'world-1' } as PlaythroughRecord,
      { id: 'play-2', world_id: 'world-2' } as PlaythroughRecord
    ]

    const deleted = await store.deleteWorld('world-1')

    expect(deleted).toBe(true)
    expect(store.worlds.map((world) => world.id)).toEqual(['world-2'])
    expect(store.playthroughs.map((playthrough) => playthrough.id)).toEqual(['play-2'])
    expect(store.deletingWorldId).toBeNull()
  })
})
