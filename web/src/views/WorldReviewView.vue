<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import VnBadge from '@/components/vn/VnBadge.vue'
import VnSelect from '@/components/vn/VnSelect.vue'
import StepProgress from '@/components/vn/StepProgress.vue'
import { formatWorldTime } from '@/play/guidance'
import { useSharedWorldBuilder, resetSharedWorldBuilder } from '@/composables/worldBuilder'

const router = useRouter()
const builder = reactive(useSharedWorldBuilder())
let active = true
onUnmounted(() => { active = false })

onMounted(() => {
  if (!builder.draft) {
    void router.replace({ name: 'world-builder' })
  }
})

const wizardSteps = [
  { id: 'describe', label: '1. Premise & Theme', description: 'Describe your story world' },
  { id: 'review', label: '2. Cast & Continuity', description: 'Review characters and lore' },
  { id: 'ready', label: '3. Launch Story', description: 'Begin your visual novel' }
]

const characters = computed(() =>
  builder.draft ? [builder.draft.player_character, ...builder.draft.npc_profiles] : []
)

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

function characterName(characterId: string): string {
  return characters.value.find((character) => character.character_id === characterId)?.name ?? characterId
}

async function validate(): Promise<void> {
  try {
    await builder.validate()
  } catch {
    // The builder exposes field diagnostics for the review panel.
  }
}

async function confirm(): Promise<void> {
  try {
    const result = await builder.confirm()
    if (!active) return
    resetSharedWorldBuilder()
    await router.push({ name: 'play', params: { playthroughId: result.playthrough.id } })
  } catch {
    // Confirmation errors stay on the editable draft.
  }
}

function cancel(): void {
  builder.cancelDraft()
  resetSharedWorldBuilder()
  void router.push({ name: 'home' })
}

function backToPrompt(): void {
  builder.stage = 'prompt'
  void router.push({ name: 'world-builder' })
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
  <div v-if="builder.draft" class="builder-container">
    <!-- Header -->
    <section class="page-heading">
      <div>
        <p class="eyebrow">World Creation Studio</p>
        <h1>Craft Your Story World</h1>
        <p class="lede">Review every detail before the curtain rises.</p>
      </div>
    </section>

    <!-- Stepper indicator -->
    <div class="stepper-wrapper">
      <StepProgress :steps="wizardSteps" :current-step="1" @select-step="backToPrompt" />
    </div>

    <!-- Review Form -->
    <form class="review-layout" @submit.prevent="confirm">
      <section class="review-main">
        <!-- World Core Information -->
        <div class="card">
          <div class="section-heading">
            <div>
              <VnBadge variant="brand">Step 2</VnBadge>
              <h2>World Core &amp; Setting</h2>
            </div>
            <button class="secondary" type="button" :disabled="builder.loading" @click="validate">
              {{ builder.validating ? 'Checking…' : 'Verify Integrity' }}
            </button>
          </div>

          <div v-if="builder.contentWarnings.length" class="warning-box" role="alert">
            <p v-for="warning in builder.contentWarnings" :key="warning">⚠️ {{ warning }}</p>
          </div>
          <div v-if="builder.validationMessages.length" class="error-box" role="alert">
            <p v-for="message in builder.validationMessages" :key="message">❌ {{ message }}</p>
          </div>

          <div class="field-grid">
            <label class="input-group">
              <span class="field-label">Title</span>
              <input v-model="builder.draft.title" maxlength="160" />
            </label>
            <label class="input-group">
              <span class="field-label">Genre</span>
              <input v-model="builder.draft.genre" maxlength="80" />
            </label>
            <label class="input-group wide-field">
              <span class="field-label">Premise</span>
              <textarea v-model="builder.draft.premise" rows="4" maxlength="20000" />
            </label>
            <label class="input-group">
              <span class="field-label">Tone</span>
              <input v-model="builder.draft.tone" maxlength="80" />
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
              <span class="muted count-tag">{{ characters.length }} Cast · {{ builder.npcCount }} NPCs</span>
              <button
                class="secondary"
                type="button"
                :disabled="builder.loading || !builder.canAddNpc"
                @click="builder.addNpc"
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
                      {{ character.character_id === builder.draft.player_character.character_id ? 'Protagonist (You)' : 'Supporting Heroine / NPC' }}
                      · {{ character.age }} y/o
                    </span>
                  </div>
                </div>
                <button
                  v-if="character.character_id !== builder.draft.player_character.character_id"
                  class="secondary danger-btn"
                  type="button"
                  :disabled="builder.loading || !builder.canRemoveNpc"
                  @click="builder.removeNpc(character.character_id)"
                >
                  Remove
                </button>
              </div>

              <div class="field-grid">
                <label class="input-group">
                  <span class="field-label">Name</span>
                  <input v-model="character.name" maxlength="160" @change="builder.syncNpcIdentity(character)" />
                </label>
                <label class="input-group">
                  <span class="field-label">Age</span>
                  <input
                    v-model.number="character.age"
                    type="number"
                    min="14"
                    max="120"
                    @change="builder.syncCharacterAge(character.character_id)"
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
                  <span class="field-label">Background</span>
                  <textarea
                    v-model="character.background"
                    rows="4"
                    maxlength="6000"
                    placeholder="Backstory, vulnerabilities, motivations, relationships, and unresolved hooks…"
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
              <p class="eyebrow">Atmosphere &amp; Lore</p>
              <h2>Locations &amp; Narrative Threads</h2>
            </div>
          </div>

          <div class="compact-editors-grid">
            <div v-for="location in builder.draft.locations" :key="location.location_id" class="compact-card">
              <label class="input-group">
                <span class="field-label">Location Name</span>
                <input v-model="location.name" maxlength="160" />
              </label>
              <label class="input-group">
                <span class="field-label">Sensory Description</span>
                <input v-model="location.description" maxlength="2000" />
              </label>
            </div>
            <div v-for="thread in builder.draft.threads" :key="thread.thread_id" class="compact-card">
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
          <p class="eyebrow">Safety &amp; Boundaries</p>
          <h3>Content Limits</h3>
          <div class="sidebar-inputs">
            <div class="input-group">
              <span class="field-label">Rating</span>
              <VnSelect
                v-model="builder.draft.content_boundaries.rating"
                :options="ratingPresetOptions"
              />
            </div>
            <div class="input-group">
              <span class="field-label">Violence Ceiling</span>
              <VnSelect
                v-model="builder.draft.content_boundaries.violence_ceiling"
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
              ⏰ {{ formatWorldTime(builder.draft.opening_scene.world_time) }}
            </VnBadge>
            <p class="opening-actions">{{ builder.draft.opening_scene.visible_actions.join(' · ') }}</p>
            <div class="participants-list">
              <span v-for="(age, characterId, index) in builder.draft.opening_scene.participants" :key="characterId">
                {{ index ? ' · ' : '' }}{{ characterName(characterId) }} ({{ age }})
              </span>
            </div>
          </div>
        </section>

        <div v-if="builder.error" class="error-box" role="alert">
          <span>⚠️ {{ builder.error }}</span>
        </div>

        <div class="review-actions">
          <button class="secondary" type="button" :disabled="builder.loading" @click="cancel">
            Start Over
          </button>
          <button
            type="submit"
            class="submit-btn"
            :class="{ generating: builder.confirming }"
            :disabled="builder.loading || builder.contentWarnings.length > 0"
          >
            {{ builder.confirming ? 'Initializing Session…' : 'Begin Story →' }}
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

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.wide-field {
  grid-column: 1 / -1;
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
  .review-layout {
    grid-template-columns: 1fr;
  }
  .field-grid {
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
