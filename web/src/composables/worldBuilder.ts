import { computed, ref, watch } from 'vue'
import { ApiError, api } from '@/api/client'
import type {
  BinaryGender,
  ContentRating,
  OpeningPreview,
  StoryTemplate,
  ViolenceCeiling,
  WorldBriefSuggestion,
  WorldCharacterSeed,
  WorldConfirmation,
  WorldRecord,
  WorldSeed
} from '@/api/types'

export type WorldBuilderStage = 'prompt' | 'review' | 'opening' | 'confirmed'

const MIN_NPC_PROFILES = 1
const MAX_NPC_PROFILES = 3
const SESSION_KEY = 'interactive-novel.world-builder.v1'

function newConfirmationId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `world-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function characterIdFromName(name: string): string {
  const slug = name
    .replaceAll('Đ', 'D')
    .replaceAll('đ', 'd')
    .normalize('NFKD')
    .replace(/\p{M}+/gu, '')
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 36)
    .replace(/_+$/g, '')
  return slug || 'npc'
}

function uniqueCharacterId(baseId: string, usedIds: Set<string>): string {
  if (!usedIds.has(baseId.toLocaleLowerCase())) return baseId
  let suffix = 2
  while (true) {
    const suffixText = '_' + suffix
    const candidate = baseId.slice(0, 36 - suffixText.length).replace(/_+$/g, '') + suffixText
    if (!usedIds.has(candidate.toLocaleLowerCase())) return candidate
    suffix += 1
  }
}

function remapConsentKey(key: string, oldId: string, newId: string): string {
  if (key === oldId) return newId
  return key.startsWith(oldId + ':') ? newId + key.slice(oldId.length) : key
}

function errorText(cause: unknown): string {
  if (cause instanceof ApiError) {
    const diagnostics = cause.details.diagnostics
    if (Array.isArray(diagnostics)) {
      const messages = diagnostics
        .filter((item): item is { path?: string; message?: string } => typeof item === 'object' && item !== null)
        .map((item) => item.message ?? 'Some information needs attention.')
      if (messages.length) return messages.join(' · ')
    }
  }
  return cause instanceof Error ? cause.message : String(cause)
}

export function useWorldBuilder() {
  const prompt = ref('')
  const tonePreset = ref('')
  const ratingPreset = ref<ContentRating>('teen_14_plus')
  const templateId = ref('')
  const templates = ref<StoryTemplate[]>([])
  const violencePreset = ref<ViolenceCeiling>('none')
  const playerGender = ref<BinaryGender>('male')
  const stage = ref<WorldBuilderStage>('prompt')
  const draft = ref<WorldSeed | null>(null)
  const openingPreview = ref<OpeningPreview | null>(null)
  const confirmationId = ref<string | null>(null)
  const confirmation = ref<WorldConfirmation | null>(null)
  const generating = ref(false)
  const validating = ref(false)
  const confirming = ref(false)
  const generatingOpening = ref(false)
  const assisting = ref(false)
  const briefSuggestion = ref<WorldBriefSuggestion | null>(null)
  const selectedAnswers = ref<Record<string, string>>({})
  const error = ref<string | null>(null)
  const validationMessages = ref<string[]>([])

  const loading = computed(
    () => assisting.value || generating.value || validating.value || generatingOpening.value || confirming.value
  )
  const hasSelectedAnswers = computed(() =>
    Object.values(selectedAnswers.value).some((answer) => answer.trim().length > 0)
  )
  const createdWorld = computed<WorldRecord | null>(() => confirmation.value?.world ?? null)
  const npcCount = computed(() => draft.value?.npc_profiles.length ?? 0)
  const canAddNpc = computed(() => npcCount.value < MAX_NPC_PROFILES)
  const canRemoveNpc = computed(() => npcCount.value > MIN_NPC_PROFILES)

  async function loadTemplates(updatePrompt = false): Promise<void> {
    try {
      templates.value = await api.listStoryTemplates()
      applySelectedTemplateDefaults(updatePrompt)
    } catch {
      error.value = 'Unable to load story templates. Please reopen the builder to try again.'
    }
  }

  function applySelectedTemplateDefaults(updatePrompt = true): void {
    const selected = templates.value.find((item) => item.id === templateId.value)
    if (updatePrompt) {
      prompt.value = selected?.starter_prompt ?? selected?.description ?? ''
      dismissSuggestion()
    }
    if (!selected) {
      if (!templateId.value) tonePreset.value = ''
      return
    }
    tonePreset.value = selected.defaults.tone ?? ''
    ratingPreset.value = selected.defaults.rating
    violencePreset.value = selected.defaults.violence_ceiling
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

  function syncNpcIdentity(character: WorldCharacterSeed): void {
    if (!draft.value || character === draft.value.player_character) return
    const oldId = character.character_id
    const usedIds = new Set(
      [draft.value.player_character, ...draft.value.npc_profiles]
        .flatMap((item) => (item === character ? item.aliases : [item.character_id, ...item.aliases]))
        .map((item) => item.toLocaleLowerCase())
    )
    const newId = uniqueCharacterId(characterIdFromName(character.name), usedIds)
    if (newId === oldId) return

    const remap = (value: string): string => (value === oldId ? newId : value)
    character.character_id = newId
    character.background_claims.forEach((claim) => {
      claim.subject_id = remap(claim.subject_id)
      if (claim.object_id !== null) claim.object_id = remap(claim.object_id)
      claim.branch_scope = remap(claim.branch_scope)
    })
    draft.value.initial_claims.forEach((claim) => {
      claim.subject_id = remap(claim.subject_id)
      if (claim.object_id !== null) claim.object_id = remap(claim.object_id)
      claim.branch_scope = remap(claim.branch_scope)
    })
    draft.value.initial_relationships.forEach((relationship) => {
      relationship.source_id = remap(relationship.source_id)
      relationship.target_id = remap(relationship.target_id)
    })
    draft.value.initial_beliefs.forEach((belief) => {
      belief.believer_id = remap(belief.believer_id)
      belief.branch_scope = remap(belief.branch_scope)
    })
    draft.value.goals.forEach((goal) => {
      goal.owner_id = remap(goal.owner_id)
    })
    draft.value.tensions.forEach((tension) => {
      tension.observer_id = remap(tension.observer_id)
      tension.rival_id = remap(tension.rival_id)
      tension.focus_id = remap(tension.focus_id)
    })
    draft.value.threads.forEach((thread) => {
      thread.participant_ids = thread.participant_ids.map(remap)
    })
    if (oldId in draft.value.opening_scene.participants) {
      const participantAge = draft.value.opening_scene.participants[oldId]
      delete draft.value.opening_scene.participants[oldId]
      draft.value.opening_scene.participants[newId] = participantAge
    }
    draft.value.opening_scene.consent = Object.fromEntries(
      Object.entries(draft.value.opening_scene.consent).map(([key, value]) => [remapConsentKey(key, oldId, newId), value])
    )
    draft.value.opening_scene.pov = remap(draft.value.opening_scene.pov)
  }

  function addNpc(): void {
    if (!draft.value) return
    if (!canAddNpc.value) {
      error.value = 'A world can contain at most three supporting characters.'
      return
    }
    const existingIds = new Set(
      [draft.value.player_character, ...draft.value.npc_profiles]
        .flatMap((item) => [item.character_id, ...item.aliases])
        .map((item) => item.toLocaleLowerCase())
    )
    let suffix = draft.value.npc_profiles.length + 1
    let name = 'New Character ' + suffix
    let characterId = characterIdFromName(name)
    while (existingIds.has(characterId.toLocaleLowerCase())) {
      suffix += 1
      name = 'New Character ' + suffix
      characterId = characterIdFromName(name)
    }
    const character: WorldCharacterSeed = {
      character_id: characterId,
      name,
      aliases: [],
      age: draft.value.player_character.age,
      gender: 'male',
      role: 'supporting character',
      background: 'Describe this character’s history, current circumstances, motivations, important relationships, and a story-relevant hook.',
      background_claims: [
        {
          schema_version: 'knowledge-claim-proposal',
          proposal_id: 'claim_' + characterId + '_background',
          source_role: 'world_builder',
          source_run_id: draft.value.run_id,
          claim_type: 'knowledge_claim',
          subject_id: characterId,
          predicate: 'public_fact',
          object_id: null,
          typed_value: name + ' is a supporting character.',
          polarity: 'positive',
          qualifiers: { source: 'character_background' },
          valid_time: { start: draft.value.opening_scene.world_time, end: null },
          branch_scope: 'public',
          provenance: {
            source_type: 'world_seed',
            source_id: draft.value.run_id,
            run_id: draft.value.run_id,
            prompt_version: draft.value.prompt_version,
            model_metadata: {}
          }
        }
      ],
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
      error.value = 'A world must contain at least one supporting character.'
      return
    }
    draft.value.npc_profiles = draft.value.npc_profiles.filter((item) => item.character_id !== characterId)
    delete draft.value.opening_scene.participants[characterId]
    draft.value.opening_scene.consent = Object.fromEntries(
      Object.entries(draft.value.opening_scene.consent).filter(
        ([key]) => key !== characterId && !key.startsWith(characterId + ':')
      )
    )
    draft.value.initial_relationships = draft.value.initial_relationships.filter(
      (item) => item.source_id !== characterId && item.target_id !== characterId
    )
    const removedClaimIds = new Set(
      draft.value.initial_claims
        .filter(
          (item) =>
            item.subject_id === characterId || item.object_id === characterId || item.branch_scope === characterId
        )
        .map((item) => item.proposal_id)
    )
    draft.value.initial_claims = draft.value.initial_claims.filter((item) => !removedClaimIds.has(item.proposal_id))
    draft.value.initial_beliefs = draft.value.initial_beliefs.filter(
      (item) => item.believer_id !== characterId && !removedClaimIds.has(item.claim_id) && item.branch_scope !== characterId
    )
    const removedGoalIds = new Set(
      draft.value.goals.filter((item) => item.owner_id === characterId).map((item) => item.goal_id)
    )
    draft.value.goals = draft.value.goals.filter((item) => !removedGoalIds.has(item.goal_id))
    for (const character of [draft.value.player_character, ...draft.value.npc_profiles]) {
      character.goal_ids = character.goal_ids.filter((goalId) => !removedGoalIds.has(goalId))
      character.private_claim_ids = character.private_claim_ids.filter((claimId) => !removedClaimIds.has(claimId))
    }
    draft.value.tensions = draft.value.tensions.filter(
      (item) =>
        item.observer_id !== characterId && item.rival_id !== characterId && item.focus_id !== characterId
    )
    draft.value.threads = draft.value.threads
      .map((item) => ({ ...item, participant_ids: item.participant_ids.filter((id) => id !== characterId) }))
      .filter((item) => item.participant_ids.length > 0)
    if (draft.value.opening_scene.pov === characterId) draft.value.opening_scene.pov = 'second_person'
    error.value = null
  }
  const contentWarnings = computed(() => {
    if (!draft.value) return []
    const warnings: string[] = []
    if (draft.value.opening_scene.guard_approved) {
      warnings.push('The opening scene needs to be checked again before the story can begin.')
    }
    if (draft.value.locations.length === 0) warnings.push('At least one starting location is required.')
    return warnings
  })

  async function generate(): Promise<WorldSeed> {
    if (loading.value) throw new Error('Another world-builder operation is already in progress.')
    generating.value = true
    error.value = null
    validationMessages.value = []
    try {
      const generated = await api.generateWorldDraft({
        prompt: prompt.value.trim(),
        template_id: templateId.value || 'custom',
        tone: tonePreset.value.trim() || undefined,
        rating: ratingPreset.value,
        violence_ceiling: violencePreset.value,
        player_gender: playerGender.value
      })
      draft.value = generated
      openingPreview.value = null
      confirmationId.value = null
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

  async function assistPrompt(overridePrompt?: string): Promise<WorldBriefSuggestion> {
    const sourcePrompt = (overridePrompt ?? prompt.value).trim()
    if (!sourcePrompt) {
      const cause = new Error('World assist prompt must not be empty.')
      error.value = cause.message
      throw cause
    }
    if (loading.value) throw new Error('Another world-builder operation is already in progress.')
    assisting.value = true
    error.value = null
    try {
      const suggestion = await api.assistWorldDraft({
        prompt: sourcePrompt,
        template_id: templateId.value || 'custom',
        tone: tonePreset.value.trim() || undefined,
        player_gender: playerGender.value
      })
      briefSuggestion.value = suggestion
      selectedAnswers.value = {}
      return suggestion
    } catch (cause) {
      error.value = errorText(cause)
      throw cause
    } finally {
      assisting.value = false
    }
  }

  function applySuggestion(): void {
    if (!briefSuggestion.value) return
    prompt.value = briefSuggestion.value.refined_prompt
    briefSuggestion.value = null
    selectedAnswers.value = {}
    error.value = null
  }

  function dismissSuggestion(): void {
    briefSuggestion.value = null
    selectedAnswers.value = {}
  }

  function setAnswer(questionId: string, answer: string): void {
    selectedAnswers.value = { ...selectedAnswers.value, [questionId]: answer }
  }

  function selectAnswer(questionId: string, answer: string): void {
    setAnswer(questionId, answer)
  }

  async function refineSelectedSuggestions(): Promise<WorldBriefSuggestion> {
    const suggestion = briefSuggestion.value
    if (!suggestion) throw new Error('No world brief suggestion is available to refine.')
    const clarifications = suggestion.questions
      .filter((question) => selectedAnswers.value[question.id]?.trim())
      .map((question) => {
        const answer = selectedAnswers.value[question.id]?.trim() ?? ''
        return `- ${question.question} → ${answer}`
      })
    if (!clarifications.length) {
      const cause = new Error('Select or write at least one clarification before updating the brief.')
      error.value = cause.message
      throw cause
    }
    const refinementPrompt = `${suggestion.refined_prompt}\n\n[Clarifications]\n${clarifications.join('\n')}`
    return assistPrompt(refinementPrompt)
  }

  async function validate(): Promise<WorldSeed | null> {
    if (!draft.value) return null
    validating.value = true
    error.value = null
    validationMessages.value = []
    try {
      const validated = await api.validateWorldDraft(draft.value)
      draft.value = validated
      openingPreview.value = null
      confirmationId.value = null
      return validated
    } catch (cause) {
      error.value = errorText(cause)
      validationMessages.value = [error.value]
      throw cause
    } finally {
      validating.value = false
    }
  }

  async function generateOpening(): Promise<OpeningPreview> {
    if (!draft.value) throw new Error('No world draft is ready for an opening preview.')
    if (loading.value) throw new Error('Another world-builder operation is already in progress.')
    const source = JSON.stringify(draft.value)
    generatingOpening.value = true
    error.value = null
    validationMessages.value = []
    try {
      const preview = await api.generateOpeningPreview(draft.value)
      if (!draft.value || JSON.stringify(draft.value) !== source) {
        throw new Error('The world changed while its opening was being written. Please continue again.')
      }
      openingPreview.value = preview
      confirmationId.value = newConfirmationId()
      stage.value = 'opening'
      return preview
    } catch (cause) {
      error.value = errorText(cause)
      validationMessages.value = [error.value]
      throw cause
    } finally {
      generatingOpening.value = false
    }
  }

  async function confirm(): Promise<WorldConfirmation> {
    if (!draft.value) throw new Error('No world draft is ready for confirmation.')
    if (!openingPreview.value) throw new Error('Generate and review the opening before beginning the story.')
    confirming.value = true
    error.value = null
    validationMessages.value = []
    try {
      confirmationId.value ??= newConfirmationId()
      const result = await api.confirmWorldDraft(draft.value, openingPreview.value, confirmationId.value)
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
    openingPreview.value = null
    confirmationId.value = null
    confirmation.value = null
    briefSuggestion.value = null
    selectedAnswers.value = {}
    validationMessages.value = []
    error.value = null
    stage.value = 'prompt'
  }

  function restoreSession(): void {
    if (typeof window === 'undefined') return
    const saved = window.sessionStorage.getItem(SESSION_KEY)
    if (!saved) return
    try {
      const value = JSON.parse(saved) as {
        stage?: WorldBuilderStage
        draft?: WorldSeed | null
        openingPreview?: OpeningPreview | null
        confirmationId?: string | null
      }
      if (value.draft && ['review', 'opening'].includes(value.stage ?? '')) {
        draft.value = value.draft
        openingPreview.value = value.openingPreview ?? null
        confirmationId.value = value.confirmationId ?? null
        stage.value = value.stage === 'opening' && value.openingPreview ? 'opening' : 'review'
      }
    } catch {
      window.sessionStorage.removeItem(SESSION_KEY)
    }
  }

  function persistSession(): void {
    if (typeof window === 'undefined') return
    if (!draft.value || !['review', 'opening'].includes(stage.value)) {
      window.sessionStorage.removeItem(SESSION_KEY)
      return
    }
    window.sessionStorage.setItem(
      SESSION_KEY,
      JSON.stringify({
        stage: stage.value,
        draft: draft.value,
        openingPreview: openingPreview.value,
        confirmationId: confirmationId.value
      })
    )
  }

  function reset(): void {
    prompt.value = ''
    tonePreset.value = ''
    ratingPreset.value = 'teen_14_plus'
    templateId.value = ''
    violencePreset.value = 'none'
    playerGender.value = 'male'
    cancelDraft()
    if (typeof window !== 'undefined') window.sessionStorage.removeItem(SESSION_KEY)
  }

  return {
    prompt,
    tonePreset,
    ratingPreset,
    templateId,
    templates,
    violencePreset,
    playerGender,
    stage,
    draft,
    openingPreview,
    confirmationId,
    confirmation,
    createdWorld,
    generating,
    validating,
    confirming,
    generatingOpening,
    assisting,
    briefSuggestion,
    selectedAnswers,
    hasSelectedAnswers,
    loading,
    npcCount,
    canAddNpc,
    canRemoveNpc,
    error,
    validationMessages,
    contentWarnings,
    loadTemplates,
    applySelectedTemplateDefaults,
    syncCharacterAge,
    syncNpcIdentity,
    addNpc,
    removeNpc,
    generate,
    assistPrompt,
    applySuggestion,
    dismissSuggestion,
    setAnswer,
    selectAnswer,
    refineSelectedSuggestions,
    validate,
    generateOpening,
    confirm,
    cancelDraft,
    reset,
    restoreSession,
    persistSession
  }
}

export type WorldBuilder = ReturnType<typeof useWorldBuilder>

let shared: WorldBuilder | null = null

/**
 * Returns a module-level singleton of the world builder so state persists
 * when navigating between the prompt and review pages. Call `resetSharedWorldBuilder()`
 * to reset the state back to defaults.
 */
export function useSharedWorldBuilder(): WorldBuilder {
  if (!shared) {
    shared = useWorldBuilder()
    shared.restoreSession()
    watch([shared.stage, shared.draft, shared.openingPreview], shared.persistSession, { deep: true })
  }
  return shared
}

/** Reset the shared singleton to default blank state. */
export function resetSharedWorldBuilder(): void {
  if (shared) {
    shared.reset()
  }
}
