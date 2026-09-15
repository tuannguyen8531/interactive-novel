<script setup lang="ts">
import { computed, onMounted, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import EditableCombobox from '@/components/EditableCombobox.vue'
import VnBadge from '@/components/vn/VnBadge.vue'
import VnSelect from '@/components/vn/VnSelect.vue'
import StepProgress from '@/components/vn/StepProgress.vue'
import { useSharedWorldBuilder, resetSharedWorldBuilder } from '@/composables/worldBuilder'

const route = useRoute()
const router = useRouter()
const builder = reactive(useSharedWorldBuilder())
const templateQuery = route.query.template
if (typeof templateQuery === 'string' && templateQuery) builder.templateId = templateQuery

onMounted(async () => {
  // If we already have a draft and stage is review, redirect to review page
  if (builder.stage === 'review' && builder.draft) {
    await router.replace({ name: 'world-review' })
    return
  }
  // Reset to prompt stage when arriving fresh
  if (builder.stage !== 'prompt') {
    resetSharedWorldBuilder()
  }
  await builder.loadTemplates(typeof templateQuery === 'string' && !!templateQuery)
})

const wizardSteps = [
  { id: 'describe', label: '1. Premise & Theme', description: 'Describe your story world' },
  { id: 'review', label: '2. Cast & Continuity', description: 'Review characters and lore' },
  { id: 'ready', label: '3. Launch Story', description: 'Begin your visual novel' }
]

const selectedTemplate = computed(() => builder.templates.find((item) => item.id === builder.templateId))

const templateOptions = computed(() => [
  { value: '', label: 'Start from scratch' },
  ...builder.templates.filter((tpl) => tpl.id !== 'custom').map((tpl) => ({ value: tpl.id, label: tpl.name })),
])

const genderOptions = [
  { value: 'male', label: 'Male' },
  { value: 'female', label: 'Female' },
]

const ratingPresetOptions = [
  { value: 'teen_14_plus', label: 'Teen 14+' },
  { value: 'mature_16_plus', label: 'Mature 16+' },
  { value: 'adult_18_plus', label: 'Adult 18+' },
]

const violencePresetOptions = [
  { value: 'none', label: 'None' },
  { value: 'restrained', label: 'Restrained' },
  { value: 'detailed', label: 'Detailed' },
]

function toneLabel(value: string): string {
  return value
    .split(',')
    .map((part) => part.trim().replace(/\b\w/g, (letter) => letter.toLocaleUpperCase()))
    .join(' and ')
}

const toneOptions = computed(() => {
  const values = [
    'warm, reflective',
    'playful, hopeful',
    'quiet, bittersweet',
    ...builder.templates.map((template) => template.defaults.tone ?? ''),
    builder.tonePreset
  ]
  return [...new Set(values.filter(Boolean))].map((value) => ({
    value,
    label: toneLabel(value)
  }))
})

const ratingLabel = computed(() => {
  if (builder.ratingPreset === 'teen_14_plus') return 'Teen 14+'
  if (builder.ratingPreset === 'mature_16_plus') return 'Mature 16+'
  return 'Adult 18+'
})
const ratingDescription = computed(() => {
  if (builder.ratingPreset === 'teen_14_plus') return 'Keeps themes suitable for ages 14 and up.'
  if (builder.ratingPreset === 'mature_16_plus') return 'Allows heavier emotional and relationship themes.'
  return 'Allows adult themes and explicit adult content.'
})
const violenceLabel = computed(() => {
  if (builder.violencePreset === 'none') return 'No violence'
  if (builder.violencePreset === 'restrained') return 'Restrained violence'
  return 'Detailed violence'
})
const violenceDescription = computed(() => {
  if (builder.violencePreset === 'none') return 'Violent actions are not depicted.'
  if (builder.violencePreset === 'restrained') return 'Violence may occur without vivid physical detail.'
  return 'Violence and its physical consequences may be described directly.'
})

async function generate(): Promise<void> {
  try {
    await builder.generate()
    await router.push({ name: 'world-review' })
  } catch {
    // The builder exposes a safe error for the form.
  }
}

async function assist(): Promise<void> {
  try {
    await builder.assistPrompt()
  } catch {
    // The builder exposes a safe error for the form.
  }
}

function updateAnswer(questionId: string, event: Event): void {
  const target = event.target
  if (target instanceof HTMLInputElement) builder.setAnswer(questionId, target.value)
}

async function refineSelectedSuggestions(): Promise<void> {
  try {
    await builder.refineSelectedSuggestions()
  } catch {
    // The builder keeps the previous suggestion and exposes a safe error.
  }
}
</script>

<template>
  <div class="builder-container">
    <!-- Header with StepProgress -->
    <section class="page-heading">
      <div>
        <p class="eyebrow">World Creation Studio</p>
        <h1>Craft Your Story World</h1>
        <p class="lede">Describe the setting and cast you envision, then refine every detail before the curtain rises.</p>
      </div>
    </section>

    <!-- Stepper indicator -->
    <div class="stepper-wrapper">
      <StepProgress :steps="wizardSteps" :current-step="0" />
    </div>

    <!-- Prompt Form -->
    <section class="builder-layout">
      <form class="card builder-card" @submit.prevent="generate">
        <div class="form-title-row">
          <div>
            <VnBadge variant="brand">Step 1</VnBadge>
            <h2>Describe the World</h2>
          </div>
        </div>

        <label class="input-group">
          <span class="field-label">World Premise &amp; Story Hook</span>
          <textarea
            v-model="builder.prompt"
            rows="6"
            maxlength="20000"
            placeholder="Describe the setting, heroine archetype, relationship tensions, or the inciting event that begins the story…"
            @input="builder.dismissSuggestion"
          />
        </label>

        <div class="brief-assist-actions">
          <button
            class="secondary"
            type="button"
            :disabled="builder.loading || !builder.prompt.trim()"
            @click="assist"
          >
            <span v-if="builder.assisting" class="spin-icon">⏳</span>
            <span v-else>✨</span>
            <span>{{ builder.assisting ? 'Developing idea…' : 'Develop idea' }}</span>
          </button>
          <span class="muted small-copy">Suggests wording without changing your selected presets.</span>
        </div>

        <section
          v-if="builder.briefSuggestion"
          class="brief-assistant-panel"
          aria-live="polite"
          aria-labelledby="brief-assistant-title"
        >
          <div class="brief-assistant-heading">
            <div>
              <p class="eyebrow">Creative Brief</p>
              <h3 id="brief-assistant-title">A clearer version of your idea</h3>
            </div>
            <button class="secondary" type="button" :disabled="builder.loading" @click="builder.dismissSuggestion">
              Dismiss
            </button>
          </div>
          <div class="brief-refined-prompt" role="note">
            {{ builder.briefSuggestion.refined_prompt }}
          </div>
          <div v-if="builder.briefSuggestion.assumptions.length" class="brief-assistant-block">
            <span class="field-label">Assumptions</span>
            <ul class="brief-list">
              <li v-for="assumption in builder.briefSuggestion.assumptions" :key="assumption">{{ assumption }}</li>
            </ul>
          </div>
          <div v-if="builder.briefSuggestion.questions.length" class="brief-assistant-block">
            <span class="field-label">Clarify the direction</span>
            <div v-for="question in builder.briefSuggestion.questions" :key="question.id" class="brief-question">
              <p>{{ question.question }}</p>
              <div class="brief-suggestion-chips">
                <button
                  v-for="answer in question.suggestions"
                  :key="answer"
                  class="chip-button"
                  :class="{ selected: builder.selectedAnswers[question.id] === answer }"
                  type="button"
                  :disabled="builder.loading"
                  @click="builder.selectAnswer(question.id, answer)"
                >
                  {{ answer }}
                </button>
              </div>
              <input
                :value="builder.selectedAnswers[question.id] ?? ''"
                class="brief-answer-input"
                type="text"
                maxlength="256"
                placeholder="Or write your own answer"
                :disabled="builder.loading"
                @input="updateAnswer(question.id, $event)"
              />
            </div>
          </div>
          <div class="brief-assistant-footer">
            <button
              class="secondary"
              type="button"
              :disabled="builder.loading || !builder.hasSelectedAnswers"
              @click="refineSelectedSuggestions"
            >
              Update with selected answers
            </button>
            <button class="submit-btn" type="button" :disabled="builder.loading" @click="builder.applySuggestion">
              Apply to description
            </button>
          </div>
        </section>

        <div class="preset-grid">
          <div class="preset-row">
            <div class="input-group">
              <span class="field-label">Curated Template</span>
              <VnSelect
                v-model="builder.templateId"
                :options="templateOptions"
                @change="builder.applySelectedTemplateDefaults()"
              />
            </div>

            <div class="input-group">
              <span class="field-label">Atmospheric Tone</span>
              <EditableCombobox
                v-model="builder.tonePreset"
                label="Tone"
                placeholder="Leave blank to infer from your premise"
                :options="toneOptions"
              />
            </div>
          </div>

          <div v-if="selectedTemplate" class="template-notice">
            <span class="template-notice-icon">💡</span>
            <div>
              <strong>{{ selectedTemplate.name }}</strong>
              <p>{{ selectedTemplate.description }}</p>
            </div>
          </div>

          <div class="preset-row three-fields">
            <div class="input-group">
              <span class="field-label">Protagonist Gender</span>
              <VnSelect
                v-model="builder.playerGender"
                :options="genderOptions"
              />
            </div>
            <div class="input-group">
              <span class="field-label">Content Rating</span>
              <VnSelect
                v-model="builder.ratingPreset"
                :options="ratingPresetOptions"
              />
            </div>
            <div class="input-group">
              <span class="field-label">Violence Ceiling</span>
              <VnSelect
                v-model="builder.violencePreset"
                :options="violencePresetOptions"
              />
            </div>
          </div>

          <div class="policy-notice">
            <span class="policy-icon">🛡️</span>
            <div>
              <strong>{{ ratingLabel }} · {{ violenceLabel }}</strong>
              <p>{{ ratingDescription }} {{ violenceDescription }}</p>
            </div>
          </div>
        </div>

        <div v-if="builder.error" class="error-box" role="alert">
          <span>⚠️ {{ builder.error }}</span>
        </div>

        <button type="submit" class="submit-btn" :class="{ generating: builder.generating }" :disabled="builder.loading || !builder.prompt.trim()">
          <span v-if="builder.generating" class="spin-icon">⏳</span>
          <span v-else>🚀</span>
          <span>{{ builder.generating ? 'Forging World Seed…' : 'Generate World' }}</span>
        </button>
      </form>

      <aside class="guidance-sidebar">
        <div class="card guidance-card">
          <p class="eyebrow">Creative Guidelines</p>
          <h3>Bring Characters to Life</h3>
          <ul class="guidance-list">
            <li><strong>Sensory Details:</strong> Mention lighting, weather, or scents to ground the world.</li>
            <li><strong>Distinct Voices:</strong> Mention if a character speaks with precision, sarcasm, or shy pauses.</li>
            <li><strong>Hidden Stakes:</strong> Giving each character a secret or vulnerability deepens the relationship drama.</li>
          </ul>
        </div>
      </aside>
    </section>
  </div>
</template>

<style scoped>
.builder-container {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.lede {
  color: var(--muted);
  font-size: 1.05rem;
  max-width: 48rem;
  margin: 0;
  line-height: 1.6;
}

.stepper-wrapper {
  position: sticky;
  top: 4rem;
  z-index: 20;
  margin-bottom: 0.5rem;
  padding: 0.5rem 0;
  background: rgba(9, 10, 15, 0.85);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.builder-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(18rem, 0.75fr);
  gap: 1.5rem;
  align-items: start;
}

.builder-card,
.guidance-card {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.form-title-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.form-title-row h2 {
  margin: 0.35rem 0 0;
  font-size: 1.45rem;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.field-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: #cbd5e1;
}

.preset-grid {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.preset-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.preset-row.three-fields {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.wide-field {
  grid-column: 1 / -1;
}

.template-notice,
.policy-notice {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.85rem 1rem;
  border-radius: var(--radius-md);
  font-size: 0.85rem;
  line-height: 1.45;
}

.template-notice {
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.25);
  color: #c7d2fe;
}

.policy-notice {
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.25);
  color: #fde68a;
}

.template-notice p,
.policy-notice p {
  margin: 0.2rem 0 0;
  font-size: 0.8rem;
  opacity: 0.85;
}

.brief-assist-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.brief-assistant-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
  border: 1px solid rgba(129, 140, 248, 0.35);
  border-radius: var(--radius-md);
  background: rgba(99, 102, 241, 0.08);
}

.brief-assistant-heading,
.brief-assistant-footer {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.brief-assistant-heading {
  justify-content: space-between;
}

.brief-assistant-heading > div {
  min-width: 0;
}

.brief-assistant-footer {
  justify-content: flex-end;
}

.brief-assistant-footer .submit-btn {
  width: auto;
}

.brief-assistant-heading h3 {
  margin: 0.25rem 0 0;
  color: #fff;
  font-size: 1.05rem;
}

.brief-refined-prompt {
  display: block;
  min-width: 0;
  padding: 0.85rem 1rem;
  margin: 0;
  border: 1px solid rgba(165, 180, 252, 0.2);
  border-radius: var(--radius-sm);
  background: rgba(15, 23, 42, 0.35);
  color: #e0e7ff;
  line-height: 1.55;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.brief-assistant-block {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.brief-list {
  margin: 0;
  padding-left: 1.2rem;
  color: #cbd5e1;
  line-height: 1.5;
}

.brief-question p {
  margin: 0 0 0.5rem;
  color: #e2e8f0;
}

.brief-suggestion-chips {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.chip-button {
  padding: 0.4rem 0.65rem;
  border: 1px solid rgba(165, 180, 252, 0.4);
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.45);
  color: #c7d2fe;
  cursor: pointer;
}

.chip-button:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.3);
}

.chip-button.selected {
  border-color: #a5b4fc;
  background: rgba(99, 102, 241, 0.45);
  color: #fff;
}

.brief-answer-input {
  width: 100%;
  margin-top: 0.6rem;
  padding: 0.55rem 0.7rem;
  border: 1px solid rgba(165, 180, 252, 0.25);
  border-radius: var(--radius-sm);
  background: rgba(15, 23, 42, 0.45);
  color: #e2e8f0;
}

.submit-btn {
  position: relative;
  padding: 0.85rem 1.5rem;
  font-size: 0.95rem;
  font-weight: 700;
  width: 100%;
  background: transparent;
  border: 2px solid var(--brand);
  color: var(--ink);
  box-shadow: 0 0 12px rgba(99, 102, 241, 0.15);
  z-index: 0;
}

.submit-btn > * {
  position: relative;
  z-index: 2;
}

.submit-btn:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.08);
  box-shadow: 0 0 20px rgba(99, 102, 241, 0.25);
  filter: none;
}

.submit-btn.generating {
  border-color: rgba(99, 102, 241, 0.25);
  pointer-events: none;
  background: transparent;
}

.submit-btn.generating::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: inherit;
  padding: 2.5px;
  background: conic-gradient(
    from var(--border-angle, 0deg),
    transparent 0%,
    #6366f1 18%,
    #f472b6 36%,
    #ffffff 48%,
    transparent 52%,
    #6366f1 68%,
    #f472b6 86%,
    #ffffff 98%,
    transparent 100%
  );
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  mask-composite: exclude;
  animation: spin-border 1.6s linear infinite;
  z-index: 1;
}

@keyframes spin-border {
  to {
    --border-angle: 360deg;
  }
}

.guidance-sidebar {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.guidance-card h3 {
  margin: 0;
  font-size: 1.15rem;
  color: #fff;
}

.guidance-list {
  margin: 0;
  padding-left: 1.2rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  font-size: 0.86rem;
  color: var(--muted);
  line-height: 1.5;
}

.guidance-list strong {
  color: #e2e8f0;
}

@media (max-width: 900px) {
  .builder-layout {
    grid-template-columns: 1fr;
  }
  .preset-row,
  .preset-row.three-fields {
    grid-template-columns: 1fr;
  }
}
</style>

<style>
@property --border-angle {
  syntax: '<angle>';
  initial-value: 0deg;
  inherits: false;
}
</style>
