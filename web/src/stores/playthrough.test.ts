import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { api } from '@/api/client'
import { FIXTURE_PLAYTHROUGH_ID } from '@/fixtures/fixture'
import type { BranchRecord, PlaythroughExport } from '@/api/types'
import { usePlaythroughStore } from './playthrough'

describe('backend playthrough branch workflows', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('persists a newly forked branch as the server-side active branch', async () => {
    const store = usePlaythroughStore()
    await store.open(FIXTURE_PLAYTHROUGH_ID)
    const turn = store.appendFixture('first choice')
    store.playthrough = { ...store.playthrough!, id: 'play-1' }
    store.fixtureMode = false
    const child: BranchRecord = {
      id: 'child',
      playthrough_id: 'play-1',
      parent_branch_id: 'fixture-root',
      fork_turn_id: turn.id,
      head_turn_id: turn.id,
      depth: 1,
      head_revision: 0,
      lifecycle: 'active',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z'
    }
    const switched = { ...store.playthrough!, active_branch_id: child.id }
    const exported = {
      format_version: 'playthrough-export',
      exported_at: '2026-01-01T00:00:00Z',
      world: store.world!,
      playthrough: switched,
      branches: [...store.branches, child],
      turns: store.turns,
      characters: store.characters,
      events: [],
      relationships: [],
      derived_jobs: [],
      metadata: {}
    } satisfies PlaythroughExport
    vi.spyOn(api, 'forkBranch').mockResolvedValue(child)
    const switchBranch = vi.spyOn(api, 'switchBranch').mockResolvedValue(child)
    vi.spyOn(api, 'exportPlaythrough').mockResolvedValue(exported)

    await store.fork(turn.id)

    expect(switchBranch).toHaveBeenCalledWith(child.id, store.playthrough!.id)
    expect(store.playthrough?.active_branch_id).toBe(child.id)
    expect(store.activeBranch?.id).toBe(child.id)
  })
})
