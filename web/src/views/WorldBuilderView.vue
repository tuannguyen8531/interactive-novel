<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import EditableCombobox from '@/components/EditableCombobox.vue'
import VnBadge from '@/components/vn/VnBadge.vue'
import VnSelect from '@/components/vn/VnSelect.vue'
import StepProgress from '@/components/vn/StepProgress.vue'
import { formatWorldTime } from '@/play/guidance'
import { useWorldBuilderStore } from '@/stores/worldBuilder'

const route = useRoute()
const router = useRouter()
const store = useWorldBuilderStore()

onMounted(async () => {
  await store.loadTemplates()
  const templateQuery = route.query.template
  if (typeof templateQuery === 'string' && templateQuery) {
    store.templateId = templateQuery
    store.applySelectedTemplateDefaults()
  }
})

const currentStepIndex = computed(() => {
  if (store.stage === 'prompt') return 0
  if (store.stage === 'review') return 1
  return 2
})

const wizardSteps = [
  { id: 'describe', label: '1. Premise & Theme', description: 'Describe your story world' },
  { id: 'review', label: '2. Cast & Continuity', description: 'Review characters and lore' },
  { id: 'ready', label: '3. Launch Story', description: 'Begin your visual novel' }
]

const characters = computed(() =>
  store.draft ? [store.draft.player_character, ...store.draft.npc_profiles] : []
)
const selectedTemplate = computed(() => store.templates.find((item) => item.id === store.templateId))

const templateOptions = computed(() => [
  { value: '', label: 'Start from scratch' },
  ...store.templates.map((tpl) => ({ value: tpl.id, label: tpl.name })),
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
    ...store.templates.map((template) => template.defaults.tone),
    store.tonePreset
  ]
  return [...new Set(values.filter(Boolean))].map((value) => ({
    value,
    label: toneLabel(value)
  }))
})

const ratingLabel = computed(() => {
  if (store.ratingPreset === 'teen_14_plus') return 'Teen 14+'
  if (store.ratingPreset === 'mature_16_plus') return 'Mature 16+'
  return 'Adult 18+'
})
const ratingDescription = computed(() => {
  if (store.ratingPreset === 'teen_14_plus') return 'Keeps themes suitable for ages 14 and up.'
  if (store.ratingPreset === 'mature_16_plus') return 'Allows heavier emotional and relationship themes.'
  return 'Allows adult themes and explicit adult content.'
})
const violenceLabel = computed(() => {
  if (store.violencePreset === 'none') return 'No violence'
  if (store.violencePreset === 'restrained') return 'Restrained violence'
  return 'Detailed violence'
})
const violenceDescription = computed(() => {
  if (store.violencePreset === 'none') return 'Violent actions are not depicted.'
  if (store.violencePreset === 'restrained') return 'Violence may occur without vivid physical detail.'
  return 'Violence and its physical consequences may be described directly.'
})

function characterName(characterId: string): string {
  return characters.value.find((character) => character.character_id === characterId)?.name ?? characterId
}

async function generate(): Promise<void> {
  try {
    await store.generate()
  } catch {
    // The store exposes a safe error for the form.
  }
}

async function validate(): Promise<void> {
  try {
    await store.validate()
  } catch {
    // The store exposes field diagnostics for the review panel.
  }
}

async function confirm(): Promise<void> {
  try {
    const result = await store.confirm()
    await router.push({ name: 'play', params: { playthroughId: result.playthrough.id } })
  } catch {
    // Confirmation errors stay on the editable draft.
  }
}

function cancel(): void {
  store.cancelDraft()
  void router.push({ name: 'home' })
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase()
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
      <StepProgress :steps="wizardSteps" :current-step="currentStepIndex" />
    </div>

    <!-- Mode 1: Initial Generation Prompt Form -->
    <section v-if="store.stage === 'prompt'" class="builder-layout">
      <form class="card builder-card" @submit.prevent="generate">
        <div class="form-title-row">
          <div>
            <VnBadge variant="brand">Step 1</VnBadge>
            <h2>Describe the World</h2>
          </div>
        </div>

        <label class="input-group">
          <span class="field-label">World Premise & Story Hook</span>
          <textarea
            v-model="store.prompt"
            rows="6"
            maxlength="20000"
            placeholder="Describe the setting, heroine archetype, relationship tensions, or the inciting event that begins the story…"
          />
        </label>

        <div class="preset-grid">
          <div class="preset-row">
            <div class="input-group">
              <span class="field-label">Curated Template</span>
              <VnSelect
                v-model="store.templateId"
                :options="templateOptions"
                @change="store.applySelectedTemplateDefaults"
              />
            </div>

            <div class="input-group">
              <span class="field-label">Atmospheric Tone</span>
              <EditableCombobox
                v-model="store.tonePreset"
                label="Tone"
                placeholder="Choose or type a tone"
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
                v-model="store.playerGender"
                :options="genderOptions"
              />
            </div>
            <div class="input-group">
              <span class="field-label">Content Rating</span>
              <VnSelect
                v-model="store.ratingPreset"
                :options="ratingPresetOptions"
              />
            </div>
            <div class="input-group">
              <span class="field-label">Violence Ceiling</span>
              <VnSelect
                v-model="store.violencePreset"
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

        <div v-if="store.error" class="error-box" role="alert">
          <span>⚠️ {{ store.error }}</span>
        </div>

        <button type="submit" class="submit-btn" :disabled="store.loading || !store.prompt.trim()">
          <span v-if="store.generating" class="spin-icon">⏳</span>
          <span v-else>🚀</span>
          <span>{{ store.generating ? 'Forging World Seed…' : 'Generate World with AI' }}</span>
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

    <!-- Mode 2: Detailed Review and Refinement Form -->
    <form v-else-if="store.draft" class="review-layout" @submit.prevent="confirm">
      <section class="review-main">
        <!-- World Core Information -->
        <div class="card">
          <div class="section-heading">
            <div>
              <VnBadge variant="brand">Step 2</VnBadge>
              <h2>World Core & Setting</h2>
            </div>
            <button class="secondary" type="button" :disabled="store.loading" @click="validate">
              {{ store.validating ? 'Checking…' : 'Verify Integrity' }}
            </button>
          </div>

          <div v-if="store.contentWarnings.length" class="warning-box" role="alert">
            <p v-for="warning in store.contentWarnings" :key="warning">⚠️ {{ warning }}</p>
          </div>
          <div v-if="store.validationMessages.length" class="error-box" role="alert">
            <p v-for="message in store.validationMessages" :key="message">❌ {{ message }}</p>
          </div>

          <div class="field-grid">
            <label class="input-group">
              <span class="field-label">Title</span>
              <input v-model="store.draft.title" maxlength="160" />
            </label>
            <label class="input-group">
              <span class="field-label">Genre</span>
              <input v-model="store.draft.genre" maxlength="80" />
            </label>
            <label class="input-group wide-field">
              <span class="field-label">Premise</span>
              <textarea v-model="store.draft.premise" rows="4" maxlength="20000" />
            </label>
            <label class="input-group">
              <span class="field-label">Tone</span>
              <input v-model="store.draft.tone" maxlength="80" />
            </label>
          </div>
        </div>

        <!-- Characters Section -->
        <div class="card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Dramatis Personae</p>
              <h2>Character Cast</h2>
              <p class="muted small-copy">Every character possesses unique traits, motivations, and hidden layers.</p>
            </div>
            <div class="section-heading-actions">
              <span class="muted count-tag">{{ characters.length }} Cast · {{ store.npcCount }} NPCs</span>
              <button
                class="secondary"
                type="button"
                :disabled="store.loading || !store.canAddNpc"
                @click="store.addNpc"
              >
                + Add NPC
              </button>
            </div>
          </div>

          <div class="characters-editor-list">
            <div
              v-for="character in characters"
              :key="character.character_id"
              class="character-card-editor"
            >
              <div class="char-card-header">
                <div class="char-id-meta">
                  <div class="char-avatar-badge">
                    <span>{{ getInitials(character.name || 'NN') }}</span>
                  </div>
                  <div>
                    <h4 class="char-name-display">{{ character.name || 'Unnamed Character' }}</h4>
                    <span class="char-badge-tag">
                      {{ character.character_id === store.draft.player_character.character_id ? 'Protagonist (You)' : 'Supporting Heroine / NPC' }}
                      · {{ character.age }} y/o
                    </span>
                  </div>
                </div>
                <button
                  v-if="character.character_id !== store.draft.player_character.character_id"
                  class="secondary danger-btn"
                  type="button"
                  :disabled="store.loading || !store.canRemoveNpc"
                  @click="store.removeNpc(character.character_id)"
                >
                  Remove
                </button>
              </div>

              <div class="field-grid">
                <label class="input-group">
                  <span class="field-label">Name</span>
                  <input v-model="character.name" maxlength="160" @change="store.syncNpcIdentity(character)" />
                </label>
                <label class="input-group">
                  <span class="field-label">Age</span>
                  <input
                    v-model.number="character.age"
                    type="number"
                    min="14"
                    max="120"
                    @change="store.syncCharacterAge(character.character_id)"
                  />
                </label>
                <div class="input-group">
                  <span class="field-label">Gender</span>
                  <VnSelect
                    v-model="character.gender"
                    :options="genderOptions"
                  />
                </div>
                <label class="input-group">
                  <span class="field-label">Archetype / Role</span>
                  <input v-model="character.role" maxlength="160" placeholder="e.g. Club President, Childhood Friend" />
                </label>
                <label class="input-group">
                  <span class="field-label">Voice / Demeanor</span>
                  <input v-model="character.voice" maxlength="300" placeholder="e.g. Warm but guarded, formal cadence" />
                </label>
                <label class="input-group wide-field">
                  <span class="field-label">Background & Secrets</span>
                  <textarea
                    v-model="character.background"
                    rows="4"
                    maxlength="6000"
                    placeholder="Backstory, vulnerabilities, underlying motivations, and personal secrets…"
                  />
                </label>
              </div>
            </div>
          </div>
        </div>

        <!-- Places and Narrative Threads -->
        <div class="card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Atmosphere & Lore</p>
              <h2>Locations & Narrative Threads</h2>
            </div>
          </div>

          <div class="compact-editors-grid">
            <div v-for="location in store.draft.locations" :key="location.location_id" class="compact-card">
              <label class="input-group">
                <span class="field-label">Location Name</span>
                <input v-model="location.name" maxlength="160" />
              </label>
              <label class="input-group">
                <span class="field-label">Sensory Description</span>
                <input v-model="location.description" maxlength="2000" />
              </label>
            </div>
            <div v-for="thread in store.draft.threads" :key="thread.thread_id" class="compact-card">
              <label class="input-group">
                <span class="field-label">Plot Thread</span>
                <input v-model="thread.premise" maxlength="2000" />
              </label>
              <label class="input-group">
                <span class="field-label">Stakes</span>
                <input v-model="thread.stakes" maxlength="2000" />
              </label>
            </div>
          </div>
        </div>
      </section>

      <!-- Sidebar -->
      <aside class="review-sidebar">
        <section class="card">
          <p class="eyebrow">Safety & Boundaries</p>
          <h3>Content Limits</h3>
          <div class="sidebar-inputs">
            <div class="input-group">
              <span class="field-label">Rating</span>
              <VnSelect
                v-model="store.draft.content_boundaries.rating"
                :options="ratingPresetOptions"
              />
            </div>
            <div class="input-group">
              <span class="field-label">Violence Ceiling</span>
              <VnSelect
                v-model="store.draft.content_boundaries.violence_ceiling"
                :options="violencePresetOptions"
              />
            </div>
          </div>
        </section>

        <section class="card opening-card">
          <p class="eyebrow">The Inciting Incident</p>
          <h3>Opening Scene</h3>
          <div class="opening-meta">
            <VnBadge variant="neutral">
              ⏰ {{ formatWorldTime(store.draft.opening_scene.world_time) }}
            </VnBadge>
            <p class="opening-actions">{{ store.draft.opening_scene.visible_actions.join(' · ') }}</p>
            <div class="participants-list">
              <span v-for="(age, characterId, index) in store.draft.opening_scene.participants" :key="characterId">
                {{ index ? ' · ' : '' }}{{ characterName(characterId) }} ({{ age }})
              </span>
            </div>
          </div>
        </section>

        <div v-if="store.error" class="error-box" role="alert">
          <span>⚠️ {{ store.error }}</span>
        </div>

        <div class="review-actions">
          <button class="secondary" type="button" :disabled="store.loading" @click="cancel">
            Start Over
          </button>
          <button
            type="submit"
            class="submit-btn"
            :disabled="store.loading || store.contentWarnings.length > 0"
          >
            {{ store.confirming ? 'Initializing Session…' : 'Begin Story →' }}
          </button>
        </div>
      </aside>
    </form>
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

.builder-layout,
.review-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(18rem, 0.75fr);
  gap: 1.5rem;
  align-items: start;
}

.review-main {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
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

.preset-row,
.field-grid {
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

.submit-btn {
  padding: 0.85rem 1.5rem;
  font-size: 0.95rem;
  font-weight: 700;
  width: 100%;
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

/* Review Section */
.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.25rem;
  gap: 1rem;
}

.section-heading h2 {
  margin: 0.25rem 0 0;
  font-size: 1.35rem;
}

.section-heading-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.count-tag {
  font-size: 0.82rem;
}

.warning-box {
  padding: 0.75rem 1rem;
  border-radius: var(--radius-md);
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.35);
  color: #fbbf24;
  font-size: 0.85rem;
  margin-bottom: 1rem;
}

.characters-editor-list {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.character-card-editor {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.char-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.char-id-meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.char-avatar-badge {
  width: 2.4rem;
  height: 2.4rem;
  border-radius: 9999px;
  background: linear-gradient(135deg, #6366f1, #ec4899);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.85rem;
  color: #fff;
}

.char-name-display {
  margin: 0;
  font-size: 1.05rem;
  color: #fff;
}

.char-badge-tag {
  font-size: 0.75rem;
  color: var(--muted);
}

.danger-btn {
  font-size: 0.8rem;
  padding: 0.35rem 0.7rem;
}

.compact-editors-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
  gap: 1rem;
}

.compact-card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--radius-md);
  padding: 1rem;
}

.review-sidebar {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  position: sticky;
  top: 5rem;
}

.review-sidebar h3 {
  margin: 0;
  font-size: 1.15rem;
  color: #fff;
}

.sidebar-inputs {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  margin-top: 0.85rem;
}

.opening-meta {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  margin-top: 0.6rem;
}

.opening-actions {
  margin: 0;
  font-size: 0.88rem;
  color: #cbd5e1;
  line-height: 1.5;
}

.participants-list {
  font-size: 0.78rem;
  color: var(--muted);
}

.review-actions {
  display: flex;
  gap: 0.75rem;
}

@media (max-width: 900px) {
  .builder-layout,
  .review-layout {
    grid-template-columns: 1fr;
  }
  .preset-row,
  .preset-row.three-fields,
  .field-grid {
    grid-template-columns: 1fr;
  }
}
</style>
