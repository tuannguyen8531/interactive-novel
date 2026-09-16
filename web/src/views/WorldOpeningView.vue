<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import StepProgress from '@/components/vn/StepProgress.vue'
import VnBadge from '@/components/vn/VnBadge.vue'
import { resetSharedWorldBuilder, useSharedWorldBuilder } from '@/composables/worldBuilder'
import { formatWorldTime } from '@/play/guidance'

const router = useRouter()
const builder = reactive(useSharedWorldBuilder())
let active = true

onUnmounted(() => { active = false })

onMounted(() => {
  if (!builder.draft) {
    void router.replace({ name: 'world-builder' })
  } else if (!builder.openingPreview) {
    builder.stage = 'review'
    void router.replace({ name: 'world-review' })
  }
})

const wizardSteps = [
  { id: 'describe', label: '1. Premise & Theme', description: 'Describe your story world' },
  { id: 'review', label: '2. Cast & Continuity', description: 'Review characters and lore' },
  { id: 'ready', label: '3. Opening Scene', description: 'Preview the beginning' }
]

const location = computed(() => builder.draft?.locations[0] ?? null)
const characterNames = computed(() => {
  if (!builder.draft) return []
  const participants = new Set(Object.keys(builder.draft.opening_scene.participants))
  return [builder.draft.player_character, ...builder.draft.npc_profiles]
    .filter((character) => participants.has(character.character_id))
    .map((character) => character.name)
})

async function regenerate(): Promise<void> {
  try {
    await builder.generateOpening()
  } catch {
    // The previous preview remains visible and the builder exposes the error.
  }
}

async function beginStory(): Promise<void> {
  try {
    const result = await builder.confirm()
    if (!active) return
    resetSharedWorldBuilder()
    await router.push({ name: 'play', params: { playthroughId: result.playthrough.id } })
  } catch {
    // Confirmation errors keep the reviewed opening available for retry.
  }
}

function goToEarlierStep(index = 1): void {
  builder.stage = index === 0 ? 'prompt' : 'review'
  void router.push({ name: index === 0 ? 'world-builder' : 'world-review' })
}
</script>

<template>
  <div v-if="builder.draft && builder.openingPreview" class="opening-container">
    <section class="page-heading">
      <div>
        <p class="eyebrow">World Creation Studio</p>
        <h1>Preview the Opening</h1>
        <p class="lede">Read the opening your players will see. The world has not been created yet.</p>
      </div>
    </section>

    <div class="stepper-wrapper">
      <StepProgress :steps="wizardSteps" :current-step="2" @select-step="goToEarlierStep" />
    </div>

    <section class="opening-layout">
      <main class="card scene-card">
        <div class="scene-heading">
          <div>
            <VnBadge variant="brand">Opening Scene</VnBadge>
            <h2>{{ builder.draft.title }}</h2>
          </div>
          <div class="scene-meta">
            <VnBadge variant="neutral">📍 {{ location?.name ?? 'Opening location' }}</VnBadge>
            <VnBadge variant="neutral">⏰ {{ formatWorldTime(builder.draft.opening_scene.world_time) }}</VnBadge>
          </div>
        </div>

        <p class="participants">Featuring {{ characterNames.join(' · ') }}</p>
        <div class="narrative" aria-label="Opening narrative preview">
          <p v-for="paragraph in builder.openingPreview.narrative_text.split(/\n\s*\n/)" :key="paragraph">
            {{ paragraph }}
          </p>
        </div>
      </main>

      <aside class="opening-sidebar">
        <div v-if="builder.error" class="error-box" role="alert">⚠️ {{ builder.error }}</div>

        <div class="actions">
          <button class="secondary" type="button" :disabled="builder.loading" @click="goToEarlierStep(1)">
            Back to Review
          </button>
          <button class="secondary" type="button" :disabled="builder.loading" @click="regenerate">
            {{ builder.generatingOpening ? 'Writing…' : 'Regenerate' }}
          </button>
          <button class="begin-button" type="button" :disabled="builder.loading" @click="beginStory">
            {{ builder.confirming ? 'Creating World…' : 'Begin Story →' }}
          </button>
        </div>
      </aside>
    </section>
  </div>
</template>

<style scoped>
.opening-container {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.lede, .participants {
  color: var(--muted);
}

.lede {
  margin: 0;
  line-height: 1.6;
}

.stepper-wrapper {
  padding: 0.25rem 0;
}

.opening-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(18rem, 0.7fr);
  gap: 1.5rem;
  align-items: start;
}

.scene-card {
  padding: 2rem;
}

.scene-heading, .scene-meta {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.scene-heading h2 {
  margin: 0.7rem 0 0;
}

.scene-meta {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.participants {
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-subtle);
  font-size: 0.85rem;
}

.narrative {
  margin-top: 1.5rem;
  font-size: 1.05rem;
  line-height: 1.85;
  color: #e2e8f0;
}

.opening-sidebar, .actions {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.opening-sidebar {
  position: sticky;
  top: 5rem;
}

.begin-button {
  width: 100%;
  padding: 0.85rem 1.5rem;
  border: 2px solid var(--brand);
  background: rgba(99, 102, 241, 0.08);
  color: var(--ink);
  font-weight: 700;
}

@media (max-width: 900px) {
  .opening-layout {
    grid-template-columns: 1fr;
  }
  .scene-heading {
    flex-direction: column;
  }
  .scene-meta {
    justify-content: flex-start;
  }
}
</style>
