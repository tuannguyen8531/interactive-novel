<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
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
      <p class="lede">Describe a setting for the selected story template. The builder creates a draft first, then lets you edit every important seed before anything is saved.</p>
    </div>
    <span class="stage-pill">{{ store.stage === 'prompt' ? 'Draft prompt' : store.stage === 'review' ? 'Review draft' : 'Confirmed' }}</span>
  </section>

  <section v-if="store.stage === 'prompt'" class="builder-layout">
    <form class="card builder-card" @submit.prevent="generate">
      <p class="eyebrow">1 · Describe</p>
      <h2>What kind of story should begin?</h2>
      <label>
        World description
        <textarea v-model="store.prompt" rows="7" maxlength="20000" placeholder="Describe the setting, characters, conflict, or mystery you want to explore…" />
      </label>
      <div class="preset-grid">
        <label>
          Story template
          <select v-model="store.templateId">
            <option v-for="template in store.templates" :key="template.id" :value="template.id">{{ template.name }}</option>
          </select>
        </label>
        <label>
          Tone preset
          <select v-model="store.tonePreset">
            <option value="warm, reflective">Warm and reflective</option>
            <option value="playful, hopeful">Playful and hopeful</option>
            <option value="quiet, bittersweet">Quiet and bittersweet</option>
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
            <option value="non_graphic">Non-graphic</option>
          </select>
        </label>
      </div>
      <div class="notice-box">
        <strong>{{ selectedTemplate?.name ?? 'Story template' }}</strong>
        <p>{{ selectedTemplate?.description ?? 'Choose a story template to shape the generated world.' }}</p>
      </div>
      <button type="submit" :disabled="store.loading || !store.prompt.trim()">
        {{ store.generating ? 'Creating draft…' : 'Create world draft' }}
      </button>
    </form>

    <aside class="card guidance-card">
      <p class="eyebrow">Before confirmation</p>
      <h2>Your draft stays private</h2>
      <ul>
        <li>AI output is checked against the typed WorldSeed contract.</li>
        <li>You can edit title, premise, characters, locations and boundaries.</li>
        <li>Canceling this screen makes no database request.</li>
      </ul>
    </aside>
  </section>

  <form v-else-if="store.draft" class="review-layout" @submit.prevent="confirm">
    <section class="review-main">
      <div class="card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">2 · Review and edit</p>
            <h2>Shape the world before it becomes canon</h2>
          </div>
          <button class="secondary" type="button" :disabled="store.loading" @click="validate">
            {{ store.validating ? 'Checking…' : 'Validate draft' }}
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
            <h2>Seeds with room to act</h2>
            <p class="muted small-copy">Adjust ages (14+) and keep between two and four NPC profiles.</p>
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
              <code>{{ character.character_id }}</code>
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
              <input v-model="character.name" maxlength="160" />
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
              Role
              <input v-model="character.role" maxlength="160" />
            </label>
            <label>
              Voice
              <input v-model="character.voice" maxlength="300" />
            </label>
            <label class="wide-field">
              Background
              <textarea v-model="character.background" rows="2" maxlength="2000" />
            </label>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Locations and threads</p>
            <h2>Where the first threads can move</h2>
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
            Thread premise
            <input v-model="thread.premise" maxlength="2000" />
          </label>
          <label>
            Stakes
            <input v-model="thread.stakes" maxlength="2000" />
          </label>
        </div>
      </div>
    </section>

    <aside class="review-sidebar">
      <section class="card">
        <p class="eyebrow">Content boundaries</p>
        <h2>Safety presets</h2>
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
            <option value="non_graphic">Non-graphic</option>
            <option value="graphic">Graphic</option>
          </select>
        </label>
        <label class="checkbox-row">
          <input v-model="store.draft.content_boundaries.adult_explicit_opt_in" type="checkbox" />
          Allow explicit adult content (18+ participants only)
        </label>
        <p class="muted small-copy">Adult explicit scenes still require every participant to be 18+, player opt-in and valid consent.</p>
      </section>

      <section class="card">
        <p class="eyebrow">Opening scene</p>
        <h2>{{ store.draft.opening_scene.scene_id }}</h2>
        <p class="muted small-copy">{{ store.draft.opening_scene.tone }} · {{ store.draft.opening_scene.pov }}</p>
        <p>{{ store.draft.opening_scene.visible_actions.join(' · ') }}</p>
        <p class="small-copy">
          Participants:
          <span v-for="(age, characterId, index) in store.draft.opening_scene.participants" :key="characterId">
            {{ index ? ' · ' : '' }}{{ characterName(characterId) }} ({{ age }})
          </span>
        </p>
        <span class="draft-status">Awaiting confirmation</span>
      </section>

      <section class="card">
        <p class="eyebrow">Typed seed</p>
        <p class="small-copy">{{ store.draft.initial_claims.length }} claims · {{ store.draft.initial_relationships.length }} relations · {{ store.draft.initial_beliefs.length }} beliefs · {{ store.draft.threads.length }} threads</p>
        <p class="muted small-copy">Confirm creates these records together with the world, playthrough, root branch and opening turn.</p>
      </section>

      <div v-if="store.error" class="error-box" role="alert">{{ store.error }}</div>
      <div class="review-actions">
        <button class="secondary" type="button" :disabled="store.loading" @click="cancel">Discard draft</button>
        <button type="submit" :disabled="store.loading || store.contentWarnings.length > 0">
          {{ store.confirming ? 'Confirming…' : 'Confirm and open story' }}
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

label {
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

.preset-grid,
.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.9rem;
}

.preset-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.wide-field {
  grid-column: 1 / -1;
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

.character-editor-heading code {
  color: var(--muted);
  font-size: 0.75rem;
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
  .preset-grid,
  .field-grid,
  .compact-editor {
    grid-template-columns: 1fr;
  }
}
</style>
