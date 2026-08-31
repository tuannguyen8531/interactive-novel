<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import EditableCombobox from '@/components/EditableCombobox.vue'
import { useWorldBuilderStore } from '@/stores/worldBuilder'

const router = useRouter()
const store = useWorldBuilderStore()

onMounted(() => {
  void store.loadTemplates()
})

const characters = computed(() =>
  store.draft ? [store.draft.player_character, ...store.draft.npc_profiles] : []
)
const selectedTemplate = computed(() => store.templates.find((item) => item.id === store.templateId))
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
  if (store.ratingPreset === 'teen_14_plus') return 'Teen'
  if (store.ratingPreset === 'mature_16_plus') return 'Mature'
  return 'Adult'
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
</script>

<template>
  <section class="page-heading">
    <div>
      <p class="eyebrow">World Builder</p>
      <h1>Make a world worth remembering</h1>
      <p class="lede">Describe the story you want, then review and shape its world before you begin.</p>
    </div>
    <span class="stage-pill">{{ store.stage === 'prompt' ? 'Describe' : store.stage === 'review' ? 'Review' : 'Ready' }}</span>
  </section>

  <section v-if="store.stage === 'prompt'" class="builder-layout">
    <form class="card builder-card" @submit.prevent="generate">
      <p class="eyebrow">1 · Describe</p>
      <h2>What kind of story should begin?</h2>
      <label>
        World description
        <textarea v-model="store.prompt" rows="7" maxlength="20000" placeholder="Describe the setting, characters, conflict, or mystery you want to explore…" />
      </label>
      <div class="preset-groups">
        <div class="preset-row">
          <label>
            Story template
            <select v-model="store.templateId" @change="store.applySelectedTemplateDefaults">
              <option v-for="template in store.templates" :key="template.id" :value="template.id">{{ template.name }}</option>
            </select>
          </label>
          <div class="preset-field">
            <span>Tone</span>
            <EditableCombobox
              v-model="store.tonePreset"
              label="Tone"
              placeholder="Choose or type a tone"
              :options="toneOptions"
            />
          </div>
        </div>
        <div class="notice-box preset-description">
          <strong>{{ selectedTemplate?.name ?? 'Story template' }}</strong>
          <p :title="selectedTemplate?.description">{{ selectedTemplate?.description ?? 'Choose a story template to shape the generated world.' }}</p>
        </div>
        <div class="preset-row three-fields">
          <label>
            Player gender
            <select v-model="store.playerGender">
              <option value="male">Male</option>
              <option value="female">Female</option>
            </select>
          </label>
          <label>
            Content rating
            <select v-model="store.ratingPreset">
              <option value="teen_14_plus">Teen 14+</option>
              <option value="mature_16_plus">Mature 16+</option>
              <option value="adult_18_plus">Adult 18+</option>
            </select>
          </label>
          <label>
            Violence ceiling
            <select v-model="store.violencePreset">
              <option value="none">None</option>
              <option value="restrained">Restrained</option>
              <option value="detailed">Detailed</option>
            </select>
          </label>
        </div>
        <div class="notice-box preset-description policy-notice">
          <strong>{{ ratingLabel }} with {{ violenceLabel }}</strong>
          <p>{{ ratingDescription }} {{ violenceDescription }}</p>
        </div>
      </div>
      <button type="submit" :disabled="store.loading || !store.prompt.trim()">
        {{ store.generating ? 'Creating your world…' : 'Create world' }}
      </button>
    </form>

    <aside class="card guidance-card">
      <p class="eyebrow">Before you begin</p>
      <h2>Shape the story your way</h2>
      <ul>
        <li>Review the world before starting the story.</li>
        <li>Edit its title, premise, characters, places and content limits.</li>
        <li>Nothing is saved until you choose to begin.</li>
      </ul>
    </aside>
  </section>

  <form v-else-if="store.draft" class="review-layout" @submit.prevent="confirm">
    <section class="review-main">
      <div class="card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">2 · Review and edit</p>
            <h2>Make the world feel right</h2>
          </div>
          <button class="secondary" type="button" :disabled="store.loading" @click="validate">
            {{ store.validating ? 'Checking…' : 'Check changes' }}
          </button>
        </div>
        <div v-if="store.contentWarnings.length" class="warning-list" role="alert">
          <p v-for="warning in store.contentWarnings" :key="warning">{{ warning }}</p>
        </div>
        <div v-if="store.validationMessages.length" class="error-box" role="alert">
          <p v-for="message in store.validationMessages" :key="message">{{ message }}</p>
        </div>
        <div class="field-grid">
          <label>
            Title
            <input v-model="store.draft.title" maxlength="160" />
          </label>
          <label>
            Genre
            <input v-model="store.draft.genre" maxlength="80" />
          </label>
          <label class="wide-field">
            Premise
            <textarea v-model="store.draft.premise" rows="4" maxlength="20000" />
          </label>
          <label>
            Tone
            <input v-model="store.draft.tone" maxlength="80" />
          </label>
        </div>
      </div>

      <div class="card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Characters</p>
            <h2>Characters with room to grow</h2>
            <p class="muted small-copy">Create between one and three supporting characters, all aged 14 or older.</p>
          </div>
          <div class="section-heading-actions">
            <span class="muted">{{ characters.length }} created · {{ store.npcCount }} NPCs</span>
            <button class="secondary" type="button" :disabled="store.loading || !store.canAddNpc" @click="store.addNpc">
              Add NPC
            </button>
          </div>
        </div>
        <div v-for="character in characters" :key="character.character_id" class="character-editor">
          <div class="character-editor-heading">
            <div>
              <strong>{{ character.character_id === store.draft.player_character.character_id ? 'Player' : 'NPC' }}</strong>
              <span class="muted"> · {{ character.age }} years old</span>
            </div>
            <div class="section-heading-actions">
              <button
                v-if="character.character_id !== store.draft.player_character.character_id"
                class="secondary"
                type="button"
                :disabled="store.loading || !store.canRemoveNpc"
                @click="store.removeNpc(character.character_id)"
              >
                Remove
              </button>
            </div>
          </div>
          <div class="field-grid">
            <label>
              Name
              <input v-model="character.name" maxlength="160" @change="store.syncNpcIdentity(character)" />
            </label>
            <label>
              Age
              <input
                v-model.number="character.age"
                type="number"
                min="14"
                max="120"
                @change="store.syncCharacterAge(character.character_id)"
              />
            </label>
            <label>
              Gender
              <select v-model="character.gender">
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </label>
            <label>
              Role
              <input v-model="character.role" maxlength="160" />
            </label>
            <label>
              Voice
              <input v-model="character.voice" maxlength="300" />
            </label>
            <label class="wide-field background-field">
              Background
              <textarea
                v-model="character.background"
                rows="6"
                maxlength="6000"
                placeholder="Formative history, current circumstances, motivations, important relationships or tensions, and a story hook…"
              />
            </label>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Places and storylines</p>
            <h2>Where the story can unfold</h2>
          </div>
        </div>
        <div v-for="location in store.draft.locations" :key="location.location_id" class="compact-editor">
          <label>
            Location
            <input v-model="location.name" maxlength="160" />
          </label>
          <label>
            Description
            <input v-model="location.description" maxlength="2000" />
          </label>
        </div>
        <div v-for="thread in store.draft.threads" :key="thread.thread_id" class="compact-editor">
          <label>
            Storyline
            <input v-model="thread.premise" maxlength="2000" />
          </label>
          <label>
            What's at stake
            <input v-model="thread.stakes" maxlength="2000" />
          </label>
        </div>
      </div>
    </section>

    <aside class="review-sidebar">
      <section class="card">
        <p class="eyebrow">Story limits</p>
        <h2>Content settings</h2>
        <label>
          Rating
          <select v-model="store.draft.content_boundaries.rating">
            <option value="teen_14_plus">Teen 14+</option>
            <option value="mature_16_plus">Mature 16+</option>
            <option value="adult_18_plus">Adult 18+</option>
          </select>
        </label>
        <label>
          Violence ceiling
          <select v-model="store.draft.content_boundaries.violence_ceiling">
            <option value="none">None</option>
            <option value="restrained">Restrained</option>
            <option value="detailed">Detailed</option>
          </select>
        </label>
        <p class="muted small-copy">Adult 18+ permits explicit adult content by default. Scene age and the selected violence ceiling still apply.</p>
      </section>

      <section class="card">
        <p class="eyebrow">Opening scene</p>
        <h2>How the story begins</h2>
        <p>{{ store.draft.opening_scene.visible_actions.join(' · ') }}</p>
        <p class="small-copy">
          Participants:
          <span v-for="(age, characterId, index) in store.draft.opening_scene.participants" :key="characterId">
            {{ index ? ' · ' : '' }}{{ characterName(characterId) }} ({{ age }})
          </span>
        </p>
        <span class="draft-status">Ready to begin</span>
      </section>

      <div v-if="store.error" class="error-box" role="alert">{{ store.error }}</div>
      <div class="review-actions">
        <button class="secondary" type="button" :disabled="store.loading" @click="cancel">Start over</button>
        <button type="submit" :disabled="store.loading || store.contentWarnings.length > 0">
          {{ store.confirming ? 'Starting…' : 'Begin story' }}
        </button>
      </div>
    </aside>
  </form>
</template>

<style scoped>
.lede {
  max-width: 48rem;
  margin-bottom: 0;
  color: var(--muted);
  line-height: 1.6;
}

.stage-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.45rem 0.7rem;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent-dark);
  font-size: 0.78rem;
  font-weight: 800;
}

.builder-layout,
.review-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(18rem, 0.7fr);
  gap: 1rem;
  align-items: start;
}

.review-main {
  display: grid;
  gap: 1rem;
}

.builder-card,
.guidance-card,
.review-main > .card {
  display: grid;
  gap: 1rem;
}

label,
.preset-field {
  display: grid;
  gap: 0.4rem;
  color: var(--muted);
  font-size: 0.85rem;
  font-weight: 700;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.checkbox-row input {
  width: auto;
  padding: 0;
}

input,
textarea,
select {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 0.55rem;
  padding: 0.7rem;
  background: #fff;
  color: var(--ink);
}

textarea {
  resize: vertical;
  line-height: 1.5;
}

.preset-row,
.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.9rem;
}

.preset-row.three-fields {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.preset-groups {
  display: grid;
  gap: 0.75rem;
}

.preset-description {
  display: grid;
  height: 7.25rem;
  grid-template-rows: auto 1fr;
  align-content: start;
  gap: 0.25rem;
  margin: 0;
  padding-bottom: 1.1rem;
  overflow: hidden;
}

.preset-description strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preset-description p {
  margin: 0;
}

.policy-notice {
  border-color: #d8aa99;
  background: #fae9e1;
  box-shadow: inset 0.22rem 0 var(--accent);
  color: var(--accent-dark);
}

.wide-field {
  grid-column: 1 / -1;
}

.background-field textarea {
  min-height: 10rem;
}

.notice-box p,
.guidance-card li {
  line-height: 1.5;
}

.guidance-card ul {
  display: grid;
  gap: 0.8rem;
  margin: 0;
  padding-left: 1.2rem;
  color: var(--muted);
}

.section-heading,
.character-editor-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.section-heading-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.6rem;
}

.section-heading h2 {
  margin-bottom: 0;
}

.character-editor {
  display: grid;
  gap: 0.8rem;
  padding-top: 1rem;
  border-top: 1px solid var(--line);
}

.character-editor:first-of-type {
  padding-top: 0;
  border-top: 0;
}

.warning-list {
  display: grid;
  gap: 0.4rem;
  padding: 0.8rem 1rem;
  border: 1px solid #e5d3a4;
  border-radius: 0.65rem;
  background: #fff7df;
  color: #6f5721;
}

.warning-list p,
.error-box p {
  margin-bottom: 0;
}

.compact-editor {
  display: grid;
  grid-template-columns: minmax(8rem, 0.7fr) minmax(0, 1.3fr);
  gap: 0.8rem;
  padding: 0.8rem 0;
  border-top: 1px solid var(--line);
}

.compact-editor:first-of-type {
  padding-top: 0;
  border-top: 0;
}

.review-sidebar {
  display: grid;
  gap: 1rem;
  position: sticky;
  top: 1rem;
}

.review-sidebar > .card {
  display: grid;
  gap: 0.8rem;
}

.small-copy {
  line-height: 1.5;
}

.draft-status {
  display: inline-flex;
  width: fit-content;
  padding: 0.4rem 0.65rem;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent-dark);
  font-size: 0.78rem;
  font-weight: 800;
}

.review-actions {
  display: flex;
  gap: 0.7rem;
}

.review-actions button {
  flex: 1;
}

@media (max-width: 820px) {
  .page-heading,
  .builder-layout,
  .review-layout {
    display: block;
  }

  .stage-pill {
    margin-top: 1rem;
  }

  .guidance-card,
  .review-sidebar {
    margin-top: 1rem;
  }

  .review-sidebar {
    position: static;
  }
}

@media (max-width: 560px) {
  .preset-row,
  .preset-row.three-fields,
  .field-grid,
  .compact-editor {
    grid-template-columns: 1fr;
  }

  .preset-description {
    height: 8.5rem;
  }
}
</style>
