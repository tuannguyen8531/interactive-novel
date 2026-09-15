import { beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import { api } from '@/api/client'
import type { WorldBriefSuggestion, WorldConfirmation, WorldSeed } from '@/api/types'
import { useWorldBuilder } from '@/composables/worldBuilder'

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
      violence_ceiling: 'none'
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

function brief(overrides: Partial<WorldBriefSuggestion> = {}): WorldBriefSuggestion {
  return {
    schema_version: 'world-brief-suggestion',
    role: 'world_guide',
    run_id: 'guide-run-1',
    prompt_version: '1.0.0',
    physical_call_id: 'guide-call-1',
    refined_prompt: 'A quiet romance around a festival-bound school club.',
    assumptions: ['The relationship develops through shared preparation.'],
    questions: [
      {
        id: 'conflict',
        question: 'What creates the central tension?',
        suggestions: ['A deadline', 'A hidden secret']
      },
      {
        id: 'relationship',
        question: 'How should the relationship develop?',
        suggestions: ['From rivalry to trust', 'Through shared vulnerability']
      }
    ],
    ...overrides
  }
}

describe('world builder composable', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('generates, edits, validates and confirms a draft', async () => {
    const draft = seed()
    vi.spyOn(api, 'generateWorldDraft').mockResolvedValue(draft)
    vi.spyOn(api, 'validateWorldDraft').mockImplementation(async (value) => value)
    vi.spyOn(api, 'confirmWorldDraft').mockImplementation(async (value) => confirmation(value))
    const store = reactive(useWorldBuilder())

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
    const store = reactive(useWorldBuilder())
    const confirmSpy = vi.spyOn(api, 'confirmWorldDraft')
    store.draft = seed()
    store.stage = 'review'

    store.cancelDraft()

    expect(store.draft).toBeNull()
    expect(store.stage).toBe('prompt')
    expect(confirmSpy).not.toHaveBeenCalled()
  })

  it('sends typed presets for an adult world', async () => {
    vi.spyOn(api, 'generateWorldDraft').mockResolvedValue(seed())
    const store = reactive(useWorldBuilder())
    store.ratingPreset = 'adult_18_plus'

    await store.generate()

    expect(vi.mocked(api.generateWorldDraft).mock.calls[0][0]).toMatchObject({
      template_id: 'custom',
      tone: undefined,
      rating: 'adult_18_plus',
      violence_ceiling: 'none',
      player_gender: 'male'
    })
  })

  it('starts a custom world with no previous draft, template, suggestions, or presets', async () => {
    let store = reactive(useWorldBuilder())
    store.draft = seed()
    store.confirmation = confirmation(seed())
    store.stage = 'confirmed'
    store.prompt = 'Previous premise'
    store.templateId = 'mystery'
    store.tonePreset = 'tense'
    store.ratingPreset = 'adult_18_plus'
    store.violencePreset = 'detailed'
    store.playerGender = 'female'
    store.briefSuggestion = brief()
    store.selectedAnswers = { secret: 'Old answer' }
    store.error = 'Old error'
    store.validationMessages = ['Old diagnostic']

    store = reactive(useWorldBuilder())

    expect(store.stage).toBe('prompt')
    expect(store.prompt).toBe('')
    expect(store.templateId).toBe('')
    expect(store.draft).toBeNull()
    expect(store.confirmation).toBeNull()
    expect(store.briefSuggestion).toBeNull()
    expect(store.selectedAnswers).toEqual({})
    expect(store.error).toBeNull()
    expect(store.validationMessages).toEqual([])
    expect(store.tonePreset).toBe('')
    expect(store.ratingPreset).toBe('teen_14_plus')
    expect(store.violencePreset).toBe('none')
    expect(store.playerGender).toBe('male')
    expect(store.loading).toBe(false)

    vi.spyOn(api, 'generateWorldDraft').mockResolvedValue(seed())
    vi.spyOn(api, 'assistWorldDraft').mockResolvedValue(brief())
    store.prompt = 'My new world'
    await store.assistPrompt()
    await store.generate()
    expect(api.assistWorldDraft).toHaveBeenCalledWith(expect.objectContaining({ template_id: 'custom', tone: undefined }))
    expect(api.generateWorldDraft).toHaveBeenCalledWith(expect.objectContaining({ template_id: 'custom', tone: undefined }))
  })

  it('ignores a previous generation that finishes after starting a new world', async () => {
    let finish!: (value: WorldSeed) => void
    vi.spyOn(api, 'generateWorldDraft').mockReturnValue(new Promise((resolve) => { finish = resolve }))
    let store = reactive(useWorldBuilder())
    const pending = store.generate()

    store = reactive(useWorldBuilder())
    finish(seed())
    await pending

    expect(store.stage).toBe('prompt')
    expect(store.draft).toBeNull()
    expect(store.loading).toBe(false)
  })

  it('keeps custom blank when a previous template catalog request finishes', async () => {
    let store = reactive(useWorldBuilder())
    const templates = [...store.templates]
    let finish!: (value: typeof templates) => void
    vi.spyOn(api, 'listStoryTemplates').mockReturnValue(new Promise((resolve) => { finish = resolve }))
    const pending = store.loadTemplates(true)

    store = reactive(useWorldBuilder())
    finish(templates)
    await pending

    expect(store.prompt).toBe('')
    expect(store.templateId).toBe('')
  })

  it('assists a prompt without changing it until the user applies the suggestion', async () => {
    const suggestion = brief()
    vi.spyOn(api, 'assistWorldDraft').mockResolvedValue(suggestion)
    const store = reactive(useWorldBuilder())
    store.prompt = 'A rough idea about a school club.'
    store.tonePreset = 'quiet, bittersweet'
    store.ratingPreset = 'mature_16_plus'
    store.violencePreset = 'restrained'
    store.playerGender = 'female'

    await store.assistPrompt()

    expect(vi.mocked(api.assistWorldDraft).mock.calls[0][0]).toMatchObject({
      prompt: 'A rough idea about a school club.',
      tone: 'quiet, bittersweet',
      player_gender: 'female'
    })
    expect(vi.mocked(api.assistWorldDraft).mock.calls[0][0]).not.toHaveProperty('rating')
    expect(vi.mocked(api.assistWorldDraft).mock.calls[0][0]).not.toHaveProperty('violence_ceiling')
    expect(store.prompt).toBe('A rough idea about a school club.')
    expect(store.briefSuggestion?.refined_prompt).toBe(suggestion.refined_prompt)

    store.applySuggestion()

    expect(store.prompt).toBe(suggestion.refined_prompt)
    expect(store.tonePreset).toBe('quiet, bittersweet')
    expect(store.briefSuggestion).toBeNull()
  })

  it('collects answers for multiple questions and makes one refine call', async () => {
    const first = brief()
    const second = brief({ refined_prompt: 'A festival deadline forces two guarded students to cooperate.' })
    vi.spyOn(api, 'assistWorldDraft').mockResolvedValueOnce(first).mockResolvedValueOnce(second)
    const store = reactive(useWorldBuilder())
    store.prompt = 'The rough idea.'

    await store.assistPrompt()
    store.selectAnswer('conflict', 'A hidden secret')
    store.selectAnswer('relationship', 'Through shared vulnerability')
    await store.refineSelectedSuggestions()

    expect(vi.mocked(api.assistWorldDraft).mock.calls[1][0].prompt).toContain(first.refined_prompt)
    expect(vi.mocked(api.assistWorldDraft).mock.calls[1][0].prompt).toContain('A hidden secret')
    expect(vi.mocked(api.assistWorldDraft).mock.calls[1][0].prompt).toContain('Through shared vulnerability')
    expect(store.prompt).toBe('The rough idea.')
    expect(store.briefSuggestion?.refined_prompt).toBe(second.refined_prompt)
    expect(store.selectedAnswers).toEqual({})
  })

  it('allows a custom answer and does not call the API without a selection', async () => {
    const suggestion = brief()
    const assistSpy = vi.spyOn(api, 'assistWorldDraft').mockResolvedValue(suggestion)
    const store = reactive(useWorldBuilder())
    store.prompt = 'A rough idea about a school club.'

    await store.assistPrompt()
    await expect(store.refineSelectedSuggestions()).rejects.toThrow('at least one clarification')
    expect(assistSpy).toHaveBeenCalledTimes(1)

    store.setAnswer('relationship', 'Slowly, after they survive the festival together')
    expect(store.hasSelectedAnswers).toBe(true)
  })

  it('dismisses a brief without changing the prompt', async () => {
    vi.spyOn(api, 'assistWorldDraft').mockResolvedValue(brief())
    const store = reactive(useWorldBuilder())
    store.prompt = 'The rough idea.'

    await store.assistPrompt()
    store.dismissSuggestion()

    expect(store.prompt).toBe('The rough idea.')
    expect(store.briefSuggestion).toBeNull()
  })

  it('applies data-driven defaults when the selected template changes', () => {
    const store = reactive(useWorldBuilder())
    store.templates.push({
      id: 'gothic_romance',
      name: 'Gothic romance',
      description: 'Secrets and dangerous attraction.',
      starter_prompt: 'A young conservator finds a love letter hidden inside a portrait in a secluded manor.',
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
    store.briefSuggestion = brief()

    store.applySelectedTemplateDefaults()

    expect(store.prompt).toBe('A young conservator finds a love letter hidden inside a portrait in a secluded manor.')
    expect(store.briefSuggestion).toBeNull()
    expect(store.tonePreset).toBe('intimate, ominous')
    expect(store.ratingPreset).toBe('adult_18_plus')
    expect(store.violencePreset).toBe('detailed')
  })

  it('preserves a custom premise when refreshing the template catalog', async () => {
    const store = reactive(useWorldBuilder())
    vi.spyOn(api, 'listStoryTemplates').mockResolvedValue([...store.templates])
    store.prompt = 'My own story premise.'

    await store.loadTemplates()

    expect(store.prompt).toBe('My own story premise.')
  })

  it('loads the selected premise from the API catalog', async () => {
    const store = reactive(useWorldBuilder())
    vi.spyOn(api, 'listStoryTemplates').mockResolvedValue([{
      id: 'school_romance', name: 'School romance', description: 'Catalog description',
      starter_prompt: 'A new premise supplied by the catalog.', genre: 'school_romance',
      prompt_instructions: 'Build a romance.',
      defaults: { tone: 'gentle', rating: 'teen_14_plus', violence_ceiling: 'none' },
      narrative_profile: { primary_focus: 'romance', romance_priority: 'high', relationship_pacing: 'slow_burn' },
      opening_guidance: [], version: 'test'
    }])
    store.templateId = 'school_romance'

    await store.loadTemplates(true)

    expect(store.prompt).toBe('A new premise supplied by the catalog.')
    expect(store.tonePreset).toBe('gentle')
  })

  it('reports an unavailable catalog without inventing fallback templates', async () => {
    const store = reactive(useWorldBuilder())
    vi.spyOn(api, 'listStoryTemplates').mockRejectedValue(new Error('Offline'))

    await store.loadTemplates(true)

    expect(store.templates).toEqual([])
    expect(store.prompt).toBe('')
    expect(store.error).toContain('Unable to load story templates')
  })

  it('clears the premise when selecting start from scratch', () => {
    const store = reactive(useWorldBuilder())
    store.templateId = ''

    store.applySelectedTemplateDefaults()

    expect(store.prompt).toBe('')
  })

  it('edits character ages and keeps opening participants synchronized', () => {
    const store = reactive(useWorldBuilder())
    store.draft = seed()

    store.syncCharacterAge('alice')
    store.draft!.npc_profiles[0].age = 19
    store.syncCharacterAge('alice')

    expect(store.draft!.npc_profiles[0].age).toBe(19)
    expect(store.draft!.opening_scene.participants.alice).toBe(19)
  })

  it('adds and removes NPC profiles within the contract bounds', () => {
    const store = reactive(useWorldBuilder())
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
    const store = reactive(useWorldBuilder())
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
