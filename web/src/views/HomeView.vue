<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useLibraryStore } from '@/stores/library'
import { api } from '@/api/client'
import { FIXTURE_PLAYTHROUGH_ID } from '@/fixtures/fixture'
import type { PlaythroughRecord, WorldRecord } from '@/api/types'

const router = useRouter()
const appStore = useAppStore()
const library = useLibraryStore()

onMounted(() => {
  void Promise.all([appStore.checkHealth(), library.load()])
})

function openFixture(): void {
  void router.push({ name: 'play', params: { playthroughId: FIXTURE_PLAYTHROUGH_ID } })
}

function worldPlaythroughs(worldId: string): PlaythroughRecord[] {
  return library.playthroughs.filter((playthrough) => playthrough.world_id === worldId)
}

async function deleteWorld(world: WorldRecord): Promise<void> {
  const confirmed = window.confirm(
    `Delete “${world.name}” and all of its playthroughs? This cannot be undone.`
  )
  if (confirmed) await library.deleteWorld(world.id)
}

async function exportPlaythrough(playthrough: PlaythroughRecord, world: WorldRecord): Promise<void> {
  const blob = await api.downloadExportBundle(playthrough.id)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${world.name.toLowerCase().replace(/[^a-z0-9]+/g, '-') || 'story'}-${playthrough.id.slice(0, 8)}.json`
  link.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <section class="page-heading">
    <div>
      <p class="eyebrow">Library</p>
      <h1>Stories with a living memory</h1>
      <p class="lede">Choose a playthrough, or step into the deterministic fixture to explore the full turn loop.</p>
    </div>
    <div class="health-pill" aria-live="polite">
      <span class="health-dot" :class="{ connected: appStore.health }" />
      {{ appStore.health ? 'Backend connected' : appStore.loading ? 'Checking backend…' : 'Fixture available offline' }}
    </div>
  </section>

  <section class="hero-grid">
    <article class="card fixture-card">
      <div>
        <p class="eyebrow">Playable fixture</p>
        <h2>Moonlight Academy</h2>
        <p>A small school-romance world with three characters, branchable history and ten calm turns to play.</p>
      </div>
      <button type="button" @click="openFixture">Open fixture</button>
    </article>

    <article class="card backend-card">
      <p class="eyebrow">Local runtime</p>
      <h2>{{ library.worlds.length }} worlds · {{ library.playthroughs.length }} playthroughs</h2>
      <p v-if="library.loading" class="muted">Loading the library…</p>
      <p v-else-if="library.error" class="muted">{{ library.error }}</p>
      <p v-else class="muted">Server data remains the source of truth when the API is available.</p>
      <div class="backend-actions">
        <button type="button" @click="router.push({ name: 'world-builder' })">Create a world</button>
        <button class="secondary" type="button" :disabled="library.loading" @click="library.load()">Refresh library</button>
      </div>
    </article>
  </section>

  <section class="library-section">
    <div class="section-heading">
      <div>
        <p class="eyebrow">Saved worlds</p>
        <h2>Continue a story</h2>
      </div>
    </div>

    <div v-if="library.loading" class="empty-state">Loading saved worlds…</div>
    <div v-else-if="library.error" class="error-box" role="alert">{{ library.error }}</div>
    <div v-else-if="library.worlds.length === 0" class="empty-state">
      No saved worlds yet. Create one above, or open the fixture for a browser test.
    </div>
    <div v-else class="library-grid">
      <article v-for="world in library.worlds" :key="world.id" class="card story-card">
        <div class="story-heading">
          <div>
            <p class="eyebrow">World</p>
            <h3>{{ world.name }}</h3>
          </div>
          <button
            class="danger delete-world-button"
            type="button"
            :aria-label="`Delete ${world.name}`"
            :disabled="library.deletingWorldId !== null"
            @click="deleteWorld(world)"
          >
            {{ library.deletingWorldId === world.id ? 'Deleting…' : 'Delete world' }}
          </button>
        </div>
        <p v-if="world.premise" class="world-premise">{{ world.premise }}</p>
        <p v-if="worldPlaythroughs(world.id).length === 0" class="muted no-playthroughs">No playthroughs in this world.</p>
        <div v-else class="playthrough-list">
          <div v-for="playthrough in worldPlaythroughs(world.id)" :key="playthrough.id" class="playthrough-row">
            <span class="muted">Clock {{ playthrough.world_clock_minutes }} minutes · {{ playthrough.lifecycle }}</span>
            <span class="playthrough-actions">
              <button class="secondary" type="button" @click="exportPlaythrough(playthrough, world)">Export</button>
              <button
                class="secondary"
                type="button"
                @click="router.push({ name: 'play', params: { playthroughId: playthrough.id } })"
              >
                Continue
              </button>
            </span>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.lede {
  max-width: 42rem;
  margin-bottom: 0;
  color: var(--muted);
  font-size: 1.05rem;
  line-height: 1.65;
}

.health-pill {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  white-space: nowrap;
  color: var(--muted);
  font-size: 0.85rem;
}

.health-dot {
  width: 0.65rem;
  height: 0.65rem;
  border-radius: 50%;
  background: #b58a47;
}

.health-dot.connected {
  background: var(--green);
}

.hero-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(16rem, 0.65fr);
  gap: 1rem;
  margin-bottom: 3rem;
}

.fixture-card {
  display: flex;
  min-height: 12rem;
  flex-direction: column;
  justify-content: space-between;
  background: linear-gradient(135deg, #fffdf8, #f6e5d8);
}

.fixture-card h2,
.backend-card h2 {
  margin-bottom: 0.5rem;
}

.fixture-card p:not(.eyebrow),
.backend-card p:not(.eyebrow) {
  max-width: 42rem;
  line-height: 1.55;
}

.backend-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.backend-actions {
  display: grid;
  gap: 0.65rem;
}

.section-heading {
  margin-bottom: 1rem;
}

.section-heading h2 {
  margin-bottom: 0;
}

.library-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
  gap: 1rem;
}

.story-card h3 {
  margin: 0;
}

.story-heading,
.playthrough-row {
  display: flex;
  gap: 1rem;
  align-items: center;
  justify-content: space-between;
}

.delete-world-button {
  flex: 0 0 auto;
  padding: 0.55rem 0.75rem;
  font-size: 0.85rem;
}

.world-premise {
  margin: 1rem 0;
  color: var(--muted);
  line-height: 1.5;
}

.no-playthroughs {
  margin: 1rem 0 0;
}

.playthrough-list {
  display: grid;
  gap: 0.65rem;
  margin-top: 1rem;
}

.playthrough-row {
  padding-top: 0.65rem;
  border-top: 1px solid var(--line);
}

.playthrough-row button {
  flex: 0 0 auto;
}

.playthrough-actions {
  display: flex;
  gap: 0.45rem;
}

@media (max-width: 700px) {
  .page-heading,
  .hero-grid {
    display: block;
  }

  .health-pill {
    margin-top: 1rem;
  }

  .backend-card {
    margin-top: 1rem;
  }

  .story-heading,
  .playthrough-row {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
