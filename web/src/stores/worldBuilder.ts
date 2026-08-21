import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { ApiError, api } from '@/api/client'
import type { StoryTemplate, WorldCharacterSeed, WorldConfirmation, WorldRecord, WorldSeed } from '@/api/types'

export type WorldBuilderStage = 'prompt' | 'review' | 'confirmed'

const MIN_NPC_PROFILES = 2
const MAX_NPC_PROFILES = 4

function errorText(cause: unknown): string {
  if (cause instanceof ApiError) {
    const diagnostics = cause.details.diagnostics
    if (Array.isArray(diagnostics)) {
      const messages = diagnostics
        .filter((item): item is { path?: string; message?: string } => typeof item === 'object' && item !== null)
        .map((item) => (item.path ?? 'draft') + ': ' + (item.message ?? 'invalid value'))
      if (messages.length) return messages.join(' · ')
    }
  }
  return cause instanceof Error ? cause.message : String(cause)
}

export const useWorldBuilderStore = defineStore('worldBuilder', () => {
  const prompt = ref('A gentle school romance around a culture club preparing for its first festival.')
  const tonePreset = ref('warm, reflective')
  const ratingPreset = ref('teen_14_plus')
  const templateId = ref('school_romance')
  const templates = ref<StoryTemplate[]>([
    {
      id: 'school_romance',
      name: 'School romance',
      description: 'A character-driven romance around school, class, or club life.',
      genre: 'school_romance',
      default_tone: 'warm, reflective',
      default_presets: {},
      opening_guidance: [],
      version: '1'
    }
  ])
  const violencePreset = ref('none')
  const stage = ref<WorldBuilderStage>('prompt')
  const draft = ref<WorldSeed | null>(null)
  const confirmation = ref<WorldConfirmation | null>(null)
  const generating = ref(false)
  const validating = ref(false)
  const confirming = ref(false)
  const error = ref<string | null>(null)
  const validationMessages = ref<string[]>([])

  const loading = computed(() => generating.value || validating.value || confirming.value)
  const createdWorld = computed<WorldRecord | null>(() => confirmation.value?.world ?? null)
  const npcCount = computed(() => draft.value?.npc_profiles.length ?? 0)
  const canAddNpc = computed(() => npcCount.value < MAX_NPC_PROFILES)
  const canRemoveNpc = computed(() => npcCount.value > MIN_NPC_PROFILES)

  async function loadTemplates(): Promise<void> {
    try {
      templates.value = await api.listStoryTemplates()
    } catch {
      // Keep the built-in school-romance fallback when the catalog is unavailable.
    }
  }

  function syncCharacterAge(characterId: string): void {
    if (!draft.value) return
    const character = [draft.value.player_character, ...draft.value.npc_profiles].find(
      (item) => item.character_id === characterId
    )
    if (!character) return
    character.age = Number.isFinite(character.age) ? Math.max(14, Math.trunc(character.age)) : 14
    if (characterId in draft.value.opening_scene.participants) {
      draft.value.opening_scene.participants[characterId] = character.age
    }
  }

  function addNpc(): void {
    if (!draft.value) return
    if (!canAddNpc.value) {
      error.value = 'A world can contain at most four NPC profiles.'
      return
    }
    const existingIds = new Set([draft.value.player_character, ...draft.value.npc_profiles].map((item) => item.character_id))
    let suffix = draft.value.npc_profiles.length + 1
    let characterId = 'npc_' + suffix
    while (existingIds.has(characterId)) {
      suffix += 1
      characterId = 'npc_' + suffix
    }
    const character: WorldCharacterSeed = {
      character_id: characterId,
      name: 'New character',
      aliases: [],
      age: draft.value.player_character.age,
      role: 'supporting character',
      background: 'A new character with room to develop.',
      voice: 'Natural speaking style',
      traits: ['curious'],
      values: [],
      goal_ids: [],
      private_claim_ids: []
    }
    draft.value.npc_profiles.push(character)
    error.value = null
  }

  function removeNpc(characterId: string): void {
    if (!draft.value) return
    if (characterId === draft.value.player_character.character_id) {
      error.value = 'The player character cannot be removed from the world.'
      return
    }
    if (!canRemoveNpc.value) {
      error.value = 'A world must contain at least two NPC profiles.'
      return
    }
    draft.value.npc_profiles = draft.value.npc_profiles.filter((item) => item.character_id !== characterId)
    delete draft.value.opening_scene.participants[characterId]
    error.value = null
  }
  const contentWarnings = computed(() => {
    if (!draft.value) return []
    const warnings: string[] = []
    if (draft.value.opening_scene.guard_approved) {
      warnings.push('Opening scene must remain unapproved until confirmation.')
    }
    if (draft.value.content_boundaries.adult_explicit_opt_in && [draft.value.player_character, ...draft.value.npc_profiles].some((item) => item.age < 18)) {
      warnings.push('Adult explicit content cannot be enabled with a minor character.')
    }
    if (draft.value.locations.length === 0) warnings.push('At least one starting location is required.')
    return warnings
  })

  function requestPrompt(): string {
    return [
      prompt.value.trim(),
      'Template: ' + templateId.value + '.',
      'Tone preset: ' + tonePreset.value + '.',
      'Content preset: rating=' + ratingPreset.value + ', violence=' + violencePreset.value + ', adult_explicit_opt_in=' + (ratingPreset.value === 'adult_18_plus') + '.'
    ].join('\n')
  }

  async function generate(): Promise<WorldSeed> {
    generating.value = true
    error.value = null
    validationMessages.value = []
    try {
      const generated = await api.generateWorldDraft(requestPrompt(), templateId.value)
      draft.value = generated
      confirmation.value = null
      stage.value = 'review'
      return generated
    } catch (cause) {
      error.value = errorText(cause)
      throw cause
    } finally {
      generating.value = false
    }
  }

  async function validate(): Promise<WorldSeed | null> {
    if (!draft.value) return null
    validating.value = true
    error.value = null
    validationMessages.value = []
    try {
      const validated = await api.validateWorldDraft(draft.value)
      draft.value = validated
      return validated
    } catch (cause) {
      error.value = errorText(cause)
      validationMessages.value = [error.value]
      throw cause
    } finally {
      validating.value = false
    }
  }

  async function confirm(): Promise<WorldConfirmation> {
    if (!draft.value) throw new Error('No world draft is ready for confirmation.')
    confirming.value = true
    error.value = null
    validationMessages.value = []
    try {
      const result = await api.confirmWorldDraft(draft.value)
      confirmation.value = result
      stage.value = 'confirmed'
      return result
    } catch (cause) {
      error.value = errorText(cause)
      validationMessages.value = [error.value]
      throw cause
    } finally {
      confirming.value = false
    }
  }

  function cancelDraft(): void {
    draft.value = null
    confirmation.value = null
    validationMessages.value = []
    error.value = null
    stage.value = 'prompt'
  }

  return {
    prompt,
    tonePreset,
    ratingPreset,
    templateId,
    templates,
    violencePreset,
    stage,
    draft,
    confirmation,
    createdWorld,
    generating,
    validating,
    confirming,
    loading,
    npcCount,
    canAddNpc,
    canRemoveNpc,
    error,
    validationMessages,
    contentWarnings,
    loadTemplates,
    syncCharacterAge,
    addNpc,
    removeNpc,
    generate,
    validate,
    confirm,
    cancelDraft
  }
})
