import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { api } from '@/api/client'
import type { WorldConfirmation, WorldSeed } from '@/api/types'
import { useWorldBuilderStore } from '@/stores/worldBuilder'

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
      gender: 'female',
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
        gender: 'female',
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
        gender: 'male',
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

  it('sends typed presets and lets the backend derive adult explicit opt-in', async () => {
    vi.spyOn(api, 'generateWorldDraft').mockResolvedValue(seed())
    const store = useWorldBuilderStore()
    store.ratingPreset = 'adult_18_plus'

    await store.generate()

    expect(vi.mocked(api.generateWorldDraft).mock.calls[0][0]).toMatchObject({
      template_id: 'school_romance',
      tone: 'warm, reflective',
      rating: 'adult_18_plus',
      violence_ceiling: 'none',
      player_gender: 'male'
    })
  })

  it('applies data-driven defaults when the selected template changes', () => {
    const store = useWorldBuilderStore()
    store.templates.push({
      id: 'gothic_romance',
      name: 'Gothic romance',
      description: 'Secrets and dangerous attraction.',
      genre: 'gothic_romance',
      prompt_instructions: 'Keep romance central.',
      defaults: {
        tone: 'intimate, ominous',
        rating: 'adult_18_plus',
        violence_ceiling: 'detailed'
      },
      narrative_profile: {
        primary_focus: 'romance',
        romance_priority: 'high',
        relationship_pacing: 'slow_burn'
      },
      opening_guidance: ['Begin with attraction and uncertainty.'],
      version: '1'
    })
    store.templateId = 'gothic_romance'

    store.applySelectedTemplateDefaults()

    expect(store.tonePreset).toBe('intimate, ominous')
    expect(store.ratingPreset).toBe('adult_18_plus')
    expect(store.violencePreset).toBe('detailed')
  })

  it('edits character ages and keeps opening participants synchronized', () => {
    const store = useWorldBuilderStore()
    store.draft = seed()

    store.syncCharacterAge('alice')
    store.draft!.npc_profiles[0].age = 19
    store.syncCharacterAge('alice')

    expect(store.draft!.npc_profiles[0].age).toBe(19)
    expect(store.draft!.opening_scene.participants.alice).toBe(19)
  })

  it('adds and removes NPC profiles within the contract bounds', () => {
    const store = useWorldBuilderStore()
    store.draft = seed()

    store.addNpc()
    store.addNpc()
    expect(store.npcCount).toBe(3)
    expect(store.canAddNpc).toBe(false)

    const addedNpcId = store.draft!.npc_profiles[2].character_id
    expect(addedNpcId).toBe('new_character_3')
    expect(store.draft!.npc_profiles[2]).toMatchObject({
      gender: 'male',
      background: 'Describe this character’s history, current circumstances, motivations, important relationships, and a story-relevant hook.'
    })
    store.removeNpc(addedNpcId)
    expect(store.npcCount).toBe(2)
    store.removeNpc('alice')
    expect(store.npcCount).toBe(1)
    store.removeNpc('bob')
    expect(store.npcCount).toBe(1)
  })

  it('derives an NPC ID from its name and remaps character references', () => {
    const store = useWorldBuilderStore()
    store.draft = seed()
    const alice = store.draft.npc_profiles[0]
    store.draft.initial_relationships = [{ source_id: 'alice', target_id: 'player', values: {} }]
    store.draft.goals = [{ goal_id: 'alice_goal', owner_id: 'alice', description: 'Help the club.', priority: 0.8 }]
    store.draft.threads = [
      { thread_id: 'festival', premise: 'Prepare.', participant_ids: ['player', 'alice'], stakes: 'Trust.' }
    ]
    store.draft.opening_scene.consent = { 'alice:explicit': 'granted' }
    store.draft.opening_scene.pov = 'alice'

    alice.name = 'Lâm Như Nguyệt'
    store.syncNpcIdentity(alice)

    expect(alice.character_id).toBe('lam_nhu_nguyet')
    expect(store.draft.opening_scene.participants).toEqual({ player: 17, lam_nhu_nguyet: 17 })
    expect(store.draft.opening_scene.consent).toEqual({ 'lam_nhu_nguyet:explicit': 'granted' })
    expect(store.draft.opening_scene.pov).toBe('lam_nhu_nguyet')
    expect(store.draft.initial_relationships[0].source_id).toBe('lam_nhu_nguyet')
    expect(store.draft.goals[0].owner_id).toBe('lam_nhu_nguyet')
    expect(store.draft.threads[0].participant_ids).toEqual(['player', 'lam_nhu_nguyet'])
  })
})
