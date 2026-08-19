<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useLibraryStore } from '@/stores/library'
import { FIXTURE_PLAYTHROUGH_ID } from '@/fixtures/fixture'

const router = useRouter()
const appStore = useAppStore()
const library = useLibraryStore()

onMounted(() => {
  void Promise.all([appStore.checkHealth(), library.load()])
})

function openFixture(): void {
  void router.push({ name: 'play', params: { playthroughId: FIXTURE_PLAYTHROUGH_ID } })
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
      <button class="secondary" type="button" :disabled="library.loading" @click="library.load()">Refresh library</button>
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
    <div v-else-if="library.playthroughs.length === 0" class="empty-state">
      No server playthroughs yet. The fixture above is ready for a browser test.
    </div>
    <div v-else class="library-grid">
      <article v-for="playthrough in library.playthroughs" :key="playthrough.id" class="card story-card">
        <p class="eyebrow">Playthrough</p>
        <h3>{{ library.worlds.find((world) => world.id === playthrough.world_id)?.name ?? playthrough.world_id }}</h3>
        <p class="muted">Clock {{ playthrough.world_clock_minutes }} minutes · {{ playthrough.lifecycle }}</p>
        <button type="button" @click="router.push({ name: 'play', params: { playthroughId: playthrough.id } })">
          Continue
        </button>
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
  margin-bottom: 0.45rem;
}

.story-card p {
  min-height: 2.5rem;
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
}
</style>
