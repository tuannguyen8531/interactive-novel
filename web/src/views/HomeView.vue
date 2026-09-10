<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useLibraryStore } from '@/stores/library'
import { api } from '@/api/client'
import { FIXTURE_PLAYTHROUGH_ID } from '@/fixtures/fixture'
import { formatWorldTime } from '@/play/guidance'
import VnBadge from '@/components/vn/VnBadge.vue'
import VnConfirmModal from '@/components/vn/VnConfirmModal.vue'
import type { PlaythroughRecord, StoryTemplate, WorldRecord } from '@/api/types'

const router = useRouter()
const appStore = useAppStore()
const DEFAULT_TEMPLATES: Array<{ id: string; name: string; description: string }> = [
  {
    id: 'school_romance',
    name: 'Moonlight High Romance',
    description: 'A delicate youth romcom centered around club deadlines, hidden confessions, and quiet after-school meetings.'
  },
  {
    id: 'fantasy_adventure',
    name: 'Chronicles of the Astral Gate',
    description: 'An expansive high-fantasy journey of ancient relics, reluctant companions, and brewing dimensional storms.'
  },
  {
    id: 'mystery',
    name: 'Shadows in the Fog',
    description: 'A tense investigation through rain-slicked cobblestone streets where every suspect conceals an alibi.'
  }
]

const library = useLibraryStore()
const templates = ref<Array<{ id: string; name: string; description: string }>>([...DEFAULT_TEMPLATES])
const loadingTemplates = ref(false)

onMounted(async () => {
  loadingTemplates.value = true
  await Promise.all([
    appStore.checkHealth(),
    library.load(),
    loadTemplates()
  ])
  loadingTemplates.value = false
})

async function loadTemplates(): Promise<void> {
  try {
    const list = await api.listStoryTemplates()
    if (list && list.length > 0) {
      templates.value = list
    }
  } catch {
    // If backend is unavailable, fallback to bundled template ideas
    templates.value = DEFAULT_TEMPLATES
  }
}

function openFixture(): void {
  void router.push({ name: 'play', params: { playthroughId: FIXTURE_PLAYTHROUGH_ID } })
}

function startWithTemplate(templateId: string): void {
  void router.push({ name: 'world-builder', query: { template: templateId } })
}

function worldPlaythroughs(worldId: string): PlaythroughRecord[] {
  return library.playthroughs.filter((playthrough) => playthrough.world_id === worldId)
}

const worldToDelete = ref<WorldRecord | null>(null)
const deletingWorld = ref(false)

function promptDeleteWorld(world: WorldRecord): void {
  worldToDelete.value = world
}

async function confirmDeleteWorld(): Promise<void> {
  if (!worldToDelete.value) return
  deletingWorld.value = true
  try {
    await library.deleteWorld(worldToDelete.value.id)
    worldToDelete.value = null
  } finally {
    deletingWorld.value = false
  }
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

function getTemplateIcon(id: string): string {
  if (id.includes('romance') || id.includes('school')) return '🌸'
  if (id.includes('fantasy')) return '⚔️'
  if (id.includes('mystery')) return '🔍'
  return '✨'
}
</script>

<template>
  <div class="home-container">
    <!-- Hero Header -->
    <header class="hero-header">
      <div class="header-badges">
        <VnBadge variant="brand">
          <template #icon>✨</template>
          AI-Powered Interactive Fiction
        </VnBadge>
        <div class="health-pill" aria-live="polite">
          <span class="health-dot" :class="{ connected: appStore.health }" />
          <span>{{ appStore.health ? 'Engine Online' : appStore.loading ? 'Connecting…' : 'Offline Fixture Ready' }}</span>
        </div>
      </div>

      <div class="title-group">
        <h1 class="main-title">Stories With A Living Memory</h1>
        <p class="subtitle">
          An interactive visual novel simulation where every decision shapes character hearts, narrative threads, and world continuity.
        </p>
      </div>

      <!-- Quick Start Fixture Card inspired by Romcom Creator -->
      <div class="quick-start-card">
        <div class="quick-left">
          <div class="rocket-badge">
            <span>🚀</span>
          </div>
          <div class="quick-info">
            <div class="quick-title-row">
              <span class="badge-tag">Quick Start</span>
              <h3>Moonlight Academy</h3>
            </div>
            <p>
              Experience the engine instantly in deterministic mode. 3 characters, branching history, and 10 fully playable turns without needing an LLM key.
            </p>
          </div>
        </div>
        <button type="button" class="quick-btn" @click="openFixture">
          <span>Jump In</span>
          <span>→</span>
        </button>
      </div>
    </header>

    <!-- Curated Story Templates Grid -->
    <section class="templates-section">
      <div class="section-title-row">
        <div>
          <p class="eyebrow">Templates</p>
          <h2>Choose a Story World</h2>
        </div>
        <button type="button" class="secondary" @click="router.push({ name: 'world-builder' })">
          <span>+ Custom World</span>
        </button>
      </div>

      <div class="templates-grid">
        <article
          v-for="template in templates"
          :key="template.id"
          class="template-card"
          @click="startWithTemplate(template.id)"
        >
          <div class="template-card-header">
            <div class="template-icon-circle">
              <span>{{ getTemplateIcon(template.id) }}</span>
            </div>
            <span class="template-badge">Curated</span>
          </div>
          <h3 class="template-name">{{ template.name }}</h3>
          <p class="template-desc">{{ template.description }}</p>
          <div class="template-card-footer">
            <span class="template-action-label">Start World</span>
            <span class="arrow-icon">→</span>
          </div>
        </article>
      </div>
    </section>

    <!-- Saved Stories & Playthrough Archives -->
    <section class="library-section">
      <div class="section-title-row">
        <div>
          <p class="eyebrow">Archives</p>
          <h2>Saved Playthroughs</h2>
        </div>
        <button
          type="button"
          class="secondary"
          :disabled="library.loading"
          @click="library.load()"
        >
          <span>↻ Refresh</span>
        </button>
      </div>

      <div v-if="library.loading" class="empty-state">
        <span>Loading story archives…</span>
      </div>
      <div v-else-if="library.error" class="error-box" role="alert">
        <span>⚠️ {{ library.error }}</span>
      </div>
      <div v-else-if="library.worlds.length === 0" class="empty-state">
        <p>No saved worlds yet.</p>
        <p class="muted">Pick a template above or launch the Quick Start fixture to begin your first journey.</p>
      </div>
      <div v-else class="saved-worlds-grid">
        <article
          v-for="world in library.worlds"
          :key="world.id"
          class="world-card"
        >
          <div class="world-card-top">
            <div class="world-meta">
              <VnBadge variant="brand">World</VnBadge>
              <h3 class="world-title">{{ world.name }}</h3>
            </div>
            <button
              type="button"
              class="icon-btn delete-world-btn"
              title="Delete World"
              aria-label="Delete Story World"
              @click="promptDeleteWorld(world)"
            >
              🗑️
            </button>
          </div>

          <p v-if="world.premise" class="world-premise">{{ world.premise }}</p>

          <div class="playthroughs-list">
            <div
              v-for="playthrough in worldPlaythroughs(world.id)"
              :key="playthrough.id"
              class="playthrough-item"
            >
              <div class="playthrough-info">
                <div class="playthrough-main">
                  <span class="playthrough-id">Session #{{ playthrough.id.slice(0, 6) }}</span>
                  <span class="bullet">·</span>
                  <span class="playthrough-time">{{ formatWorldTime(playthrough.world_clock_minutes) }}</span>
                </div>
                <span class="playthrough-turns">
                  Status: {{ playthrough.lifecycle }}
                </span>
              </div>
              <div class="playthrough-actions">
                <button
                  type="button"
                  class="resume-btn"
                  @click="router.push({ name: 'play', params: { playthroughId: playthrough.id } })"
                >
                  Continue
                </button>
                <button
                  type="button"
                  class="secondary icon-btn"
                  title="Export Playthrough"
                  @click="exportPlaythrough(playthrough, world)"
                >
                  📥
                </button>
              </div>
            </div>
          </div>
        </article>
      </div>
    </section>

    <!-- Confirm Delete World Modal -->
    <VnConfirmModal
      :open="Boolean(worldToDelete)"
      title="Delete Story World?"
      :message="worldToDelete ? `Are you sure you want to delete “${worldToDelete.name}” and all associated playthrough sessions? This action cannot be undone.` : ''"
      confirm-text="Delete World"
      cancel-text="Keep World"
      variant="danger"
      :busy="deletingWorld"
      @confirm="confirmDeleteWorld"
      @cancel="worldToDelete = null"
    />
  </div>
</template>

<style scoped>
.home-container {
  display: flex;
  flex-direction: column;
  gap: 3.5rem;
}

/* Hero Section */
.hero-header {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.header-badges {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.health-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.8rem;
  border-radius: 9999px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 0.78rem;
  color: var(--muted);
}

.health-dot {
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 9999px;
  background: #f59e0b;
}

.health-dot.connected {
  background: #10b981;
  box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);
}

.title-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.main-title {
  margin: 0;
  font-size: clamp(2rem, 4.5vw, 3.2rem);
  font-weight: 900;
  letter-spacing: -0.03em;
  line-height: 1.15;
  background: linear-gradient(135deg, #ffffff 40%, #a5b4fc 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.subtitle {
  margin: 0;
  font-size: clamp(1rem, 1.8vw, 1.15rem);
  color: var(--muted);
  max-width: 48rem;
  line-height: 1.6;
}

/* Quick Start Card */
.quick-start-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.5rem;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.12), rgba(236, 72, 153, 0.08));
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: var(--radius-lg);
  padding: 1.5rem 1.8rem;
  backdrop-filter: blur(16px);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.35);
  margin-top: 0.5rem;
  transition: transform 200ms ease, border-color 200ms ease;
}

.quick-start-card:hover {
  border-color: rgba(99, 102, 241, 0.5);
  transform: translateY(-2px);
}

.quick-left {
  display: flex;
  align-items: center;
  gap: 1.25rem;
}

.rocket-badge {
  width: 3.2rem;
  height: 3.2rem;
  border-radius: var(--radius-md);
  background: rgba(99, 102, 241, 0.2);
  border: 1px solid rgba(99, 102, 241, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.6rem;
  flex-shrink: 0;
  box-shadow: 0 0 16px rgba(99, 102, 241, 0.35);
}

.quick-info {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.quick-title-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.badge-tag {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 0.2rem 0.5rem;
  background: #6366f1;
  color: #fff;
  border-radius: 0.35rem;
}

.quick-info h3 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  color: #fff;
}

.quick-info p {
  margin: 0;
  font-size: 0.88rem;
  color: #cbd5e1;
  line-height: 1.45;
  max-width: 44rem;
}

.quick-btn {
  padding: 0.85rem 1.6rem;
  font-size: 0.95rem;
  border-radius: var(--radius-md);
  flex-shrink: 0;
  gap: 0.6rem;
}

@media (max-width: 768px) {
  .quick-start-card {
    flex-direction: column;
    align-items: stretch;
  }
  .quick-left {
    align-items: flex-start;
  }
  .quick-btn {
    width: 100%;
  }
}

/* Sections Common Header */
.section-title-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 1.5rem;
  gap: 1rem;
}

.section-title-row h2 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 800;
}

/* Templates Grid */
.templates-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
  gap: 1.25rem;
}

.template-card {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: 1.5rem;
  cursor: pointer;
  backdrop-filter: blur(16px);
  transition: all 220ms cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
  overflow: hidden;
}

.template-card:hover {
  transform: translateY(-4px);
  border-color: rgba(99, 102, 241, 0.4);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.4), 0 0 20px rgba(99, 102, 241, 0.15);
}

.template-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.template-icon-circle {
  width: 2.75rem;
  height: 2.75rem;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.35rem;
}

.template-badge {
  font-size: 0.72rem;
  font-weight: 600;
  color: #a5b4fc;
  background: rgba(99, 102, 241, 0.12);
  padding: 0.25rem 0.6rem;
  border-radius: 9999px;
  border: 1px solid rgba(99, 102, 241, 0.25);
}

.template-name {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  color: #fff;
}

.template-desc {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.5;
  color: var(--muted);
  flex: 1;
}

.template-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  color: #a5b4fc;
  font-size: 0.85rem;
  font-weight: 600;
}

.arrow-icon {
  transition: transform 180ms ease;
}

.template-card:hover .arrow-icon {
  transform: translateX(4px);
}

/* Saved Worlds Grid */
.saved-worlds-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(22rem, 1fr));
  gap: 1.25rem;
}

.world-card {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: 1.35rem;
  backdrop-filter: blur(16px);
}

.world-card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem;
}

.world-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.45rem;
  min-width: 0;
}

.world-title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  color: #fff;
}

.world-premise {
  margin: 0;
  font-size: 0.82rem;
  color: var(--muted);
  line-height: 1.45;
}

.playthroughs-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.playthrough-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--radius-md);
  padding: 0.65rem 0.85rem;
}

.playthrough-info {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.playthrough-main {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: #e2e8f0;
}

.bullet {
  color: var(--muted-dark);
}

.playthrough-time {
  color: #a5b4fc;
}

.playthrough-turns {
  font-size: 0.72rem;
  color: var(--muted);
  text-transform: capitalize;
}

.playthrough-actions {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.resume-btn {
  padding: 0.45rem 0.9rem;
  font-size: 0.8rem;
}

.icon-btn {
  padding: 0.45rem 0.65rem;
  font-size: 0.85rem;
}

.delete-world-btn {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.25);
  color: #fca5a5;
  box-shadow: none;
}

.delete-world-btn:hover {
  background: rgba(239, 68, 68, 0.25);
  border-color: #ef4444;
  color: #ffffff;
  box-shadow: 0 4px 14px rgba(239, 68, 68, 0.4);
  transform: translateY(-1px);
}
</style>
