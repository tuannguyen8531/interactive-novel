import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { ApiError, api } from '@/api/client'
import type { WorldConfirmation, WorldRecord, WorldSeed } from '@/api/types'

export type WorldBuilderStage = 'prompt' | 'review' | 'confirmed'

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
  const contentWarnings = computed(() => {
    if (!draft.value) return []
    const warnings: string[] = []
    if (draft.value.opening_scene.guard_approved) {
      warnings.push('Opening scene must remain unapproved until confirmation.')
    }
    if (draft.value.content_boundaries.adult_explicit_opt_in && draft.value.npc_profiles.some((item) => item.age < 18)) {
      warnings.push('Adult explicit content cannot be enabled with a minor character.')
    }
    if (draft.value.locations.length === 0) warnings.push('At least one starting location is required.')
    return warnings
  })

  function requestPrompt(): string {
    return [
      prompt.value.trim(),
      'Template: school_romance.',
      'Tone preset: ' + tonePreset.value + '.',
      'Content preset: rating=' + ratingPreset.value + ', violence=' + violencePreset.value + ', adult_explicit_opt_in=false.'
    ].join('\n')
  }

  async function generate(): Promise<WorldSeed> {
    generating.value = true
    error.value = null
    validationMessages.value = []
    try {
      const generated = await api.generateWorldDraft(requestPrompt())
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
    violencePreset,
    stage,
    draft,
    confirmation,
    createdWorld,
    generating,
    validating,
    confirming,
    loading,
    error,
    validationMessages,
    contentWarnings,
    generate,
    validate,
    confirm,
    cancelDraft
  }
})
