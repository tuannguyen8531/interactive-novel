import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { api } from '@/api/client'
import type { WorldConfirmation, WorldSeed } from '@/api/types'
import { useWorldBuilderStore } from './worldBuilder'

function seed(): WorldSeed {
  return {
    schema_version: 'world-seed',
    role: 'world_builder',
    run_id: 'world-run-1',
    prompt_version: '1.0.0',
    physical_call_id: 'world-call-1',
    title: 'Quiet Courtyard',
    premise: 'A club prepares for a festival.',
    genre: 'school_romance',
    tone: 'gentle',
    content_boundaries: {
      rating: 'teen_14_plus',
      topic_boundaries: { adult_explicit: 'excluded' },
      violence_ceiling: 'none',
      adult_explicit_opt_in: false
    },
    locations: [{ location_id: 'library', name: 'Library', description: 'A quiet room.' }],
    player_character: {
      character_id: 'player',
      name: 'Mina',
      aliases: [],
      age: 17,
      role: 'student',
      background: 'New to the club.',
      voice: 'curious',
      traits: ['observant'],
      values: ['honesty'],
      goal_ids: [],
      private_claim_ids: []
    },
    npc_profiles: [
      {
        character_id: 'alice',
        name: 'Alice',
        aliases: [],
        age: 17,
        role: 'club president',
        background: 'Organized.',
        voice: 'precise',
        traits: ['diligent'],
        values: ['reliability'],
        goal_ids: [],
        private_claim_ids: []
      },
      {
        character_id: 'bob',
        name: 'Bob',
        aliases: [],
        age: 17,
        role: 'treasurer',
        background: 'Practical.',
        voice: 'dry',
        traits: ['careful'],
        values: ['fairness'],
        goal_ids: [],
        private_claim_ids: []
      }
    ],
    initial_claims: [],
    initial_relationships: [],
    initial_beliefs: [],
    goals: [],
    tensions: [],
    threads: [],
    opening_scene: {
      scene_id: 'opening-scene',
      source_role: 'world_builder',
      source_run_id: 'world-run-1',
      guard_approved: false,
      world_time: 0,
      tags: ['romance'],
      participants: { player: 17, alice: 17 },
      consent: {},
      approved_beats: ['meet'],
      visible_actions: ['enter library'],
      allowed_dialogue_intents: ['greeting'],
      pov: 'second_person',
      tone: 'gentle',
      continuity_details: [],
      allowed_claims: [],
      forbidden_claims: [],
      length_target: 300
    }
  }
}

const confirmation = (draft: WorldSeed): WorldConfirmation =>
  ({
    world: { id: 'world-1' },
    playthrough: { id: 'playthrough-1' },
    branch: { id: 'branch-1' },
    opening_scene: draft.opening_scene,
    opening_turn: { id: 'turn-1' }
  }) as unknown as WorldConfirmation

describe('world builder store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('generates, edits, validates and confirms a draft', async () => {
    const draft = seed()
    vi.spyOn(api, 'generateWorldDraft').mockResolvedValue(draft)
    vi.spyOn(api, 'validateWorldDraft').mockImplementation(async (value) => value)
    vi.spyOn(api, 'confirmWorldDraft').mockImplementation(async (value) => confirmation(value))
    const store = useWorldBuilderStore()

    await store.generate()
    expect(store.stage).toBe('review')
    store.draft!.title = 'Edited Courtyard'
    await store.validate()
    const result = await store.confirm()

    expect(result.playthrough.id).toBe('playthrough-1')
    expect(store.createdWorld?.id).toBe('world-1')
    expect(store.stage).toBe('confirmed')
    expect(vi.mocked(api.confirmWorldDraft).mock.calls[0][0].title).toBe('Edited Courtyard')
  })

  it('discards a draft without calling confirmation', () => {
    const store = useWorldBuilderStore()
    const confirmSpy = vi.spyOn(api, 'confirmWorldDraft')
    store.draft = seed()
    store.stage = 'review'

    store.cancelDraft()

    expect(store.draft).toBeNull()
    expect(store.stage).toBe('prompt')
    expect(confirmSpy).not.toHaveBeenCalled()
  })

  it('requests adult explicit opt-in for an adult rating', async () => {
    vi.spyOn(api, 'generateWorldDraft').mockResolvedValue(seed())
    const store = useWorldBuilderStore()
    store.ratingPreset = 'adult_18_plus'

    await store.generate()

    expect(vi.mocked(api.generateWorldDraft).mock.calls[0][0]).toContain('adult_explicit_opt_in=true')
  })
})
