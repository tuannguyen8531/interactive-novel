<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useBranchStore } from '@/stores/branch'
import { useCharacterStore } from '@/stores/character'
import { useDebugStore } from '@/stores/debug'
import { usePlaythroughStore } from '@/stores/playthrough'
import { useTurnJobStore, type TurnRequest } from '@/stores/turnJob'
import {
  branchDisplayName,
  branchProgressLabel,
  buildPlayGuidance,
  findPlayerCharacter,
  formatTurnDuration,
  formatWorldTime,
  isOpeningTurn,
  turnMoveSuggestions
} from '@/play/guidance'
import { capitalizeStatus, displayTemplate, turnProgressPercent } from '@/play/progress'
import VnBadge from '@/components/vn/VnBadge.vue'
import VnConfirmModal from '@/components/vn/VnConfirmModal.vue'
import CharacterDetailSlider from '@/components/vn/CharacterDetailSlider.vue'
import TypewriterText from '@/components/vn/TypewriterText.vue'
import type { CharacterView } from '@/api/types'

const route = useRoute()
const router = useRouter()
const playthrough = usePlaythroughStore()
const branches = useBranchStore()
const characters = useCharacterStore()
const jobs = useTurnJobStore()
const debug = useDebugStore()

const input = ref('')
const actionInput = ref<HTMLTextAreaElement | null>(null)
const transcriptScroll = ref<HTMLElement | null>(null)
const selectedForkTurnId = ref<string | null>(null)
const openCharacterId = ref<string | null>(null)
const loadingRoute = ref(false)
const isCharacterDrawerOpen = ref(false)

const routePlaythroughId = computed(() => String(route.params.playthroughId ?? ''))
const playerCharacter = computed(() => findPlayerCharacter(playthrough.playthrough, playthrough.characters))
const playerTurns = computed(() => playthrough.visibleTurns.filter((turn) => !isOpeningTurn(turn)))
const latestPlayerTurn = computed(() => playerTurns.value.at(-1) ?? null)
const latestTurn = computed(() => playthrough.visibleTurns.at(-1) ?? null)

const activeBranchName = computed(() =>
  branches.activeBranch ? branchDisplayName(branches.activeBranch, branches.branches) : 'Main Route'
)
const canFork = computed(() => selectedForkTurnId.value !== null && !jobs.active)
const selectedCharacter = computed(() => characters.selected)

const guidance = computed(() =>
  playthrough.world
    ? buildPlayGuidance(playthrough.world, playerCharacter.value, playthrough.timeline, playthrough.characters)
    : { locationName: null, sceneCues: [], suggestedActions: [] }
)

const latestTurnSuggestions = computed(() => {
  const visibleTurns = playthrough.visibleTurns
  const last = visibleTurns[visibleTurns.length - 1]
  return last ? turnMoveSuggestions(last) : []
})

const suggestedActions = computed(() =>
  latestTurnSuggestions.value.length > 0 ? latestTurnSuggestions.value : guidance.value.suggestedActions
)

const isFirstMove = computed(() => playerTurns.value.length === 0)
const currentChapter = computed(() => Math.max(1, Math.floor(playerTurns.value.length / 5) + 1))

const actionPlaceholder = computed(() =>
  playerCharacter.value
    ? `Describe what ${playerCharacter.value.display_name} attempts to do…`
    : 'Describe what you attempt to do…'
)

const jobStatusLabel = computed(() => capitalizeStatus(jobs.progress))
const jobProgressPercent = computed(() => turnProgressPercent(jobs.events, jobs.current?.status, jobs.loading))

function canForkFromTurn(turnBranchId: string): boolean {
  return !branches.activeBranch?.parent_branch_id || branches.activeBranch.id === turnBranchId
}

onMounted(() => {
  void openRoute()
})

watch(routePlaythroughId, () => {
  void openRoute()
})

watch(
  () => playthrough.visibleTurns.length,
  async (turns, previousTurns) => {
    if (turns <= previousTurns) return
    await nextTick()
    scrollTranscriptToEnd('smooth')
  }
)

watch(
  () => jobs.terminal,
  async (terminal, wasTerminal) => {
    if (!terminal || wasTerminal || playthrough.fixtureMode) return
    await playthrough.refresh()
    if (jobs.current?.status === 'completed') {
      input.value = ''
    }
    debug.refresh()
  }
)

async function openRoute(): Promise<void> {
  if (!routePlaythroughId.value) return
  loadingRoute.value = true
  await playthrough.open(routePlaythroughId.value)
  if (!playthrough.fixtureMode && playthrough.playthrough) await jobs.resume(playthrough.playthrough.id)
  characters.clear()
  const defaultCharacter = playerCharacter.value ?? playthrough.characters.find((c) => c.role === 'player') ?? playthrough.characters[0]
  if (defaultCharacter) {
    openCharacterId.value = defaultCharacter.id
    await characters.select(defaultCharacter.id)
  }
  debug.refresh()
  loadingRoute.value = false
  await nextTick()
  scrollTranscriptToEnd('auto')
}

function scrollTranscriptToEnd(behavior: ScrollBehavior): void {
  const element = transcriptScroll.value
  if (!element) return
  element.scrollTo({ top: element.scrollHeight, behavior })
}

function request(): TurnRequest | null {
  const branch = playthrough.activeBranch
  if (!branch || !playthrough.playthrough || !input.value.trim()) return null
  return {
    playthrough_id: playthrough.playthrough.id,
    branch_id: branch.id,
    raw_input: input.value.trim(),
    base_revision: branch.head_revision,
    actor_id: playthrough.playthrough.player_character_id ?? playerCharacter.value?.id ?? undefined,
    parent_turn_id: playthrough.latestTurn?.id ?? branch.fork_turn_id
  }
}

async function submit(): Promise<void> {
  const turnRequest = request()
  if (!turnRequest) return
  const action = input.value.trim()
  try {
    if (playthrough.fixtureMode) {
      await jobs.runFixture(turnRequest, () => playthrough.appendFixture(action))
      input.value = ''
      debug.refresh()
    } else {
      await jobs.submit(turnRequest)
    }
  } catch {
    input.value = action
  }
}


const confirmActionModal = ref<{
  title: string
  message: string
  confirmText: string
  action: () => Promise<void>
} | null>(null)

function regenerateLastTurn(): void {
  const turn = latestPlayerTurn.value
  if (!turn || jobs.active || playthrough.fixtureMode) return
  confirmActionModal.value = {
    title: 'Regenerate Turn?',
    message: 'Regenerate this turn on a new continuation branch? The current timeline remains intact in history.',
    confirmText: 'Regenerate',
    action: async () => {
      const action = turn.raw_input
      await playthrough.regenerate(turn.id)
      await refreshSelectedCharacter()
      input.value = action
      await submit()
    }
  }
}

function undoLastTurn(): void {
  const turn = latestPlayerTurn.value
  if (!turn || jobs.active || playthrough.fixtureMode) return
  confirmActionModal.value = {
    title: 'Roll Back Decision?',
    message: 'Roll back to the previous decision point on a new branch? The current timeline remains intact.',
    confirmText: 'Undo Move',
    action: async () => {
      await playthrough.undo(turn.id)
      await refreshSelectedCharacter()
    }
  }
}

async function onConfirmActionModal(): Promise<void> {
  const modal = confirmActionModal.value
  confirmActionModal.value = null
  if (modal) {
    await modal.action()
  }
}

async function fork(): Promise<void> {
  if (!selectedForkTurnId.value) return
  await branches.fork(selectedForkTurnId.value)
  selectedForkTurnId.value = null
  await refreshSelectedCharacter()
  debug.refresh()
}

async function switchTimeline(branchId: string): Promise<void> {
  if (branchId === branches.activeBranchId || jobs.active) return
  await branches.switchBranch(branchId)
  await refreshSelectedCharacter()
  debug.refresh()
}

async function refreshSelectedCharacter(): Promise<void> {
  if (openCharacterId.value) await characters.select(openCharacterId.value)
}

async function chooseCharacter(characterId: string): Promise<void> {
  openCharacterId.value = characterId
  await characters.select(characterId)
}

function narrative(turn: { final_narrative: string | null }): string {
  return turn.final_narrative ?? 'The turn concluded without a recorded narration.'
}

async function selectMoveExample(action: string): Promise<void> {
  input.value = action
  await nextTick()
  actionInput.value?.focus()
}

function playerTurnNumber(index: number): number {
  return playthrough.visibleTurns.slice(0, index + 1).filter((turn) => !isOpeningTurn(turn)).length
}

function getActionIcon(kind: string): string {
  const lower = kind.toLowerCase()
  if (lower === 'act') return '⚡'
  if (lower === 'speak') return '💬'
  if (lower === 'observe') return '👁️'
  if (lower === 'think') return '💡'
  return '✨'
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

let scrollRaf: number | null = null

function onTypewriterTick(): void {
  if (scrollRaf !== null) return
  scrollRaf = requestAnimationFrame(() => {
    scrollRaf = null
    const element = transcriptScroll.value
    if (!element) return
    element.scrollTop = element.scrollHeight
  })
}

function onTypewriterFinish(): void {
  if (scrollRaf !== null) {
    cancelAnimationFrame(scrollRaf)
    scrollRaf = null
  }
  const element = transcriptScroll.value
  if (!element) return
  element.scrollTop = element.scrollHeight
}
</script>

<template>
  <div v-if="loadingRoute || (playthrough.loading && !playthrough.playthrough)" class="empty-state">
    <span>Opening story realm…</span>
  </div>
  <div v-else-if="playthrough.error" class="error-box" role="alert">
    <strong>Could not open this playthrough.</strong>
    <p>{{ playthrough.error }}</p>
    <button class="secondary" type="button" @click="router.push('/')">Return to Library</button>
  </div>

  <div v-else-if="playthrough.playthrough && playthrough.world" class="vn-play-container">
    <!-- Top Visual Novel HUD Row -->
    <header class="vn-hud-bar">
      <div class="hud-left">
        <button class="back-pill" type="button" @click="router.push('/')">
          <span>←</span>
          <span>Library</span>
        </button>

        <VnBadge variant="brand">
          <template #icon>✨</template>
          Chapter {{ currentChapter }}
        </VnBadge>

        <div class="world-meta-pill">
          <span class="world-title-tag">{{ playthrough.world.name }}</span>
          <span class="bullet">·</span>
          <span class="branch-tag">{{ activeBranchName }}</span>
        </div>
      </div>

      <div class="hud-right">
        <VnBadge variant="neutral" capitalize>
          📍 {{ guidance.locationName || 'Scene Location' }}
        </VnBadge>

        <VnBadge variant="neutral">
          ⏰ {{ formatWorldTime(playthrough.worldTime) }}
        </VnBadge>

        <VnBadge variant="accent">
          <template #icon>🎯</template>
          Turn {{ playerTurns.length }}
        </VnBadge>

        <button
          type="button"
          class="hud-toggle-btn"
          :class="{ active: isCharacterDrawerOpen }"
          title="Toggle Character Profiles"
          @click="isCharacterDrawerOpen = !isCharacterDrawerOpen"
        >
          <span>👥</span>
          <span>Character ({{ playthrough.characters.length }})</span>
        </button>
      </div>
    </header>

    <!-- Main Stage Layout -->
    <div class="vn-stage-layout">
      <!-- Left Column: Story & Actions -->
      <main class="vn-main-column">
        <!-- Unified Story Narrative Frame -->
        <section class="card vn-narrative-card" aria-label="Visual novel narrative stream">
          <div class="narrative-card-header">
            <div class="narrator-id">
              <div class="narrator-avatar">
                <span>📖</span>
              </div>
              <div>
                <span class="narrator-label">Story Realm</span>
                <p class="scene-cue-title">
                  Chapter {{ currentChapter }} · {{ playthrough.world.name }}
                </p>
              </div>
            </div>
            <div class="narrator-actions">
              <VnBadge v-if="playthrough.fixtureMode" variant="accent">
                Fixture Mode
              </VnBadge>
              <span class="turn-count-tag">
                {{ playthrough.visibleTurns.length }} {{ playthrough.visibleTurns.length === 1 ? 'Scene' : 'Scenes' }}
              </span>
            </div>
          </div>

          <!-- Integrated Story Stream: All turns flow seamlessly in sequence -->
          <div ref="transcriptScroll" class="story-stream-box">
            <div v-if="playthrough.visibleTurns.length === 0" class="opening-empty-state">
              <p class="story-premise">{{ playthrough.world.premise }}</p>
              <p class="story-start-hint">The story realm awaits your first move below…</p>
              <div v-if="guidance.sceneCues.length" class="scene-cues-bar">
                <span class="cues-title">Sensory Cues:</span>
                <span v-for="cue in guidance.sceneCues" :key="cue" class="cue-pill">
                  {{ cue }}
                </span>
              </div>
            </div>

            <div v-else class="turns-sequence">
              <article
                v-for="(turn, index) in playthrough.visibleTurns"
                :key="turn.id"
                class="story-turn-item"
                :class="{
                  'is-latest-turn': index === playthrough.visibleTurns.length - 1,
                  'is-opening-turn': isOpeningTurn(turn)
                }"
              >
                <!-- Turn Meta: Index, Timestamp, Fork Button -->
                <div class="story-turn-meta">
                  <div class="turn-meta-left">
                    <span class="turn-step-chip">
                      {{ isOpeningTurn(turn) ? 'Opening Scene' : `Move ${playerTurnNumber(index)}` }}
                    </span>
                    <span class="turn-timestamp">
                      ⏰ {{ formatWorldTime(turn.world_time_end) }}
                      <small v-if="turn.duration_minutes > 0"> (+{{ formatTurnDuration(turn.duration_minutes) }})</small>
                    </span>
                  </div>

                  <button
                    class="fork-chip-btn"
                    :class="{ selected: selectedForkTurnId === turn.id }"
                    type="button"
                    :disabled="jobs.active || !canForkFromTurn(turn.branch_id)"
                    :title="canForkFromTurn(turn.branch_id) ? 'Fork a new timeline from this turn' : 'Belongs to parent branch'"
                    @click="selectedForkTurnId = selectedForkTurnId === turn.id ? null : turn.id"
                  >
                    {{ canForkFromTurn(turn.branch_id) ? (selectedForkTurnId === turn.id ? '✓ Selected to Fork' : 'Fork Here') : 'Parent Branch' }}
                  </button>
                </div>

                <!-- Player Action (if not opening turn) -->
                <div v-if="!isOpeningTurn(turn)" class="player-action-block">
                  <div class="player-avatar-mini">
                    <span>{{ playerCharacter?.display_name ? getInitials(playerCharacter.display_name) : 'You' }}</span>
                  </div>
                  <div class="player-action-content">
                    <span class="player-name-tag">{{ playerCharacter?.display_name || 'You' }}</span>
                    <p class="player-action-text">{{ turn.raw_input }}</p>
                  </div>
                </div>

                <!-- Narrative Body -->
                <div class="narrative-prose">
                  <TypewriterText
                    v-if="index === playthrough.visibleTurns.length - 1 && !jobs.active"
                    :text="narrative(turn)"
                    :animate="true"
                    @tick="onTypewriterTick"
                    @finish="onTypewriterFinish"
                  />
                  <p v-else class="narrative-static-text">{{ narrative(turn) }}</p>
                </div>

                <!-- Scene Sensory Cues for Opening Scene -->
                <div v-if="isOpeningTurn(turn) && guidance.sceneCues.length" class="scene-cues-bar">
                  <span class="cues-title">Sensory Cues:</span>
                  <span v-for="cue in guidance.sceneCues" :key="cue" class="cue-pill">
                    {{ cue }}
                  </span>
                </div>
              </article>

              <!-- Realtime AI Processing status at end of story stream -->
              <div v-if="jobs.active" class="ai-processing-notice">
                <span class="spinner-dot" />
                <span>AI is shaping the next chapter… ({{ jobProgressPercent }}%)</span>
                <button class="cancel-link" type="button" @click="jobs.cancel()">Cancel</button>
              </div>
            </div>
          </div>
        </section>

        <!-- Quick Choices (Lựa chọn nhanh) -->
        <section v-if="suggestedActions.length > 0" class="card quick-moves-card">
          <div class="card-mini-header">
            <VnBadge variant="brand">Quick Moves</VnBadge>
            <span class="mini-hint">Select a suggested move to inspect, adapt, and send</span>
          </div>

          <div class="quick-moves-grid">
            <button
              v-for="action in suggestedActions"
              :key="`${action.kind}:${action.text}`"
              type="button"
              class="quick-move-button"
              :disabled="jobs.active"
              :aria-label="action.text"
              @click="selectMoveExample(action.text)"
            >
              <div class="move-icon-badge">
                <span>{{ getActionIcon(action.kind) }}</span>
              </div>
              <div class="move-content">
                <span class="move-kind">{{ action.kind }}</span>
                <span class="move-text">{{ action.text }}</span>
              </div>

              <!-- Custom Floating Tooltip on Hover -->
              <div class="move-custom-tooltip" role="tooltip">
                <div class="tooltip-header">
                  <span class="tooltip-kind">{{ action.kind }}</span>
                  <span class="tooltip-hint">Click to load</span>
                </div>
                <p class="tooltip-text">{{ action.text }}</p>
              </div>
            </button>
          </div>
        </section>

        <!-- Custom Player Action Input -->
        <section class="card custom-action-card">
          <div class="card-mini-header">
            <VnBadge variant="accent">Custom Action</VnBadge>
            <span class="mini-hint">Type any action, dialogue, observation, or secret thought</span>
            <div v-if="jobs.active" class="action-progress-pill" aria-live="polite">
              <svg class="progress-ring-svg" viewBox="0 0 20 20" width="14" height="14" aria-hidden="true">
                <circle
                  class="progress-ring-bg"
                  cx="10"
                  cy="10"
                  r="7.5"
                  fill="none"
                  stroke-width="2.5"
                />
                <circle
                  class="progress-ring-bar"
                  cx="10"
                  cy="10"
                  r="7.5"
                  fill="none"
                  stroke-width="2.5"
                  stroke-linecap="round"
                  :stroke-dasharray="47.12"
                  :stroke-dashoffset="47.12 * (1 - jobProgressPercent / 100)"
                />
              </svg>
              <span class="progress-ring-text">{{ jobProgressPercent }}%</span>
            </div>
          </div>

          <div class="input-area-wrapper">
            <textarea
              id="player-move"
              ref="actionInput"
              v-model="input"
              :disabled="jobs.active"
              rows="3"
              maxlength="20000"
              :placeholder="actionPlaceholder"
              @keydown.ctrl.enter.prevent="submit"
            />
          </div>

          <div class="action-card-footer">
            <span class="shortcut-hint">Press <strong>Ctrl + Enter</strong> to commit</span>
            <div class="footer-buttons">
              <button
                v-if="latestPlayerTurn && !playthrough.fixtureMode"
                type="button"
                class="secondary small-btn"
                :disabled="jobs.active"
                @click="undoLastTurn"
              >
                ↺ Undo Move
              </button>
              <button
                v-if="latestPlayerTurn && !playthrough.fixtureMode"
                type="button"
                class="secondary small-btn"
                :disabled="jobs.active"
                @click="regenerateLastTurn"
              >
                ↻ Regenerate
              </button>
              <button
                type="button"
                class="send-btn small-btn"
                :disabled="jobs.active || !input.trim()"
                @click="submit"
              >
                <span>➤</span>
                <span>Send</span>
              </button>
            </div>
          </div>

          <div v-if="jobs.error" class="error-box" role="alert">
            <span>⚠️ {{ jobs.error }}</span>
            <button class="secondary small-btn" type="button" @click="jobs.retry()">Retry</button>
          </div>
        </section>
      </main>

      <!-- Right Column: Multiverse & Cast Sidebar -->
      <aside class="vn-sidebar-column">
        <!-- Branch Timelines Panel (Multiverse) -->
        <section class="card timelines-panel">
          <div class="panel-header-row">
            <div>
              <p class="eyebrow">Multiverse</p>
              <h3>Timeline Branches</h3>
            </div>
            <button
              class="secondary small-btn"
              type="button"
              :disabled="!canFork"
              @click="fork"
            >
              Fork Branch
            </button>
          </div>
          <p class="muted small-hint">
            {{ canFork ? 'Click Fork Branch to branch out from your selected turn.' : 'Select a turn in the History Log to fork.' }}
          </p>
          <div class="timelines-list">
            <button
              v-for="branch in branches.branches"
              :key="branch.id"
              class="timeline-item"
              :class="{ active: branch.id === branches.activeBranchId }"
              type="button"
              :disabled="jobs.active"
              @click="switchTimeline(branch.id)"
            >
              <span class="timeline-name">{{ branchDisplayName(branch, branches.branches) }}</span>
              <span class="timeline-badge">{{ branchProgressLabel(branch) }}</span>
            </button>
          </div>
        </section>

        <!-- Character & Relationship Slider -->
        <section v-if="isCharacterDrawerOpen" class="card characters-panel">
          <div class="panel-header-row">
            <div>
              <h3>Character</h3>
            </div>
          </div>

          <CharacterDetailSlider
            :characters="playthrough.characters"
            :selected-id="openCharacterId"
            @select="chooseCharacter"
          />
        </section>
      </aside>
    </div>

    <!-- Confirm Undo / Regenerate Modal -->
    <VnConfirmModal
      :open="Boolean(confirmActionModal)"
      :title="confirmActionModal?.title ?? 'Confirm Action'"
      :message="confirmActionModal?.message ?? ''"
      :confirm-text="confirmActionModal?.confirmText ?? 'Confirm'"
      cancel-text="Cancel"
      variant="warning"
      @confirm="onConfirmActionModal"
      @cancel="confirmActionModal = null"
    />
  </div>
</template>

<style scoped>
.vn-play-container {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

/* Top Visual Novel HUD Bar */
.vn-hud-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1.25rem;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  backdrop-filter: blur(16px);
  gap: 1rem;
  flex-wrap: wrap;
}

.hud-left,
.hud-right {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.back-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.75rem;
  font-size: 0.8rem;
  border-radius: 9999px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #cbd5e1;
  box-shadow: none;
}

.back-pill:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  transform: translateY(-1px);
}

.world-meta-pill {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  color: #e2e8f0;
  font-weight: 600;
}

.bullet {
  color: var(--muted-dark);
}

.branch-tag {
  color: #a5b4fc;
  font-size: 0.8rem;
}

.hud-toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.85rem;
  font-size: 0.8rem;
  border-radius: 9999px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #cbd5e1;
  box-shadow: none;
}

.hud-toggle-btn.active {
  background: rgba(99, 102, 241, 0.2);
  border-color: #6366f1;
  color: #fff;
}

/* Stage Layout */
.vn-stage-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 22rem;
  gap: 1.5rem;
}

.vn-main-column {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.vn-sidebar-column {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  align-self: start;
}

/* Unified Story Narrative Frame */
.vn-narrative-card {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  background: linear-gradient(135deg, rgba(18, 22, 34, 0.92), rgba(26, 31, 48, 0.88));
  border: 1px solid rgba(99, 102, 241, 0.25);
  border-radius: var(--radius-lg);
  padding: 1.5rem;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4), 0 0 20px rgba(99, 102, 241, 0.08);
}

.narrative-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 0.85rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.narrator-id {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.narrator-avatar {
  width: 2.4rem;
  height: 2.4rem;
  border-radius: var(--radius-md);
  background: rgba(99, 102, 241, 0.2);
  border: 1px solid rgba(99, 102, 241, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
}

.narrator-label {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #a5b4fc;
}

.scene-cue-title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 700;
  color: #fff;
}

.narrator-actions {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.turn-count-tag {
  font-size: 0.75rem;
  color: #a5b4fc;
  font-weight: 600;
  padding: 0.2rem 0.6rem;
  background: rgba(99, 102, 241, 0.1);
  border-radius: 9999px;
  border: 1px solid rgba(99, 102, 241, 0.2);
}

/* Integrated Story Stream Box */
.story-stream-box {
  max-height: 36rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  padding-right: 0.5rem;
  scroll-behavior: smooth;
}

.story-stream-box::-webkit-scrollbar {
  width: 6px;
}
.story-stream-box::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.02);
  border-radius: 9999px;
}
.story-stream-box::-webkit-scrollbar-thumb {
  background: rgba(99, 102, 241, 0.25);
  border-radius: 9999px;
}
.story-stream-box::-webkit-scrollbar-thumb:hover {
  background: rgba(99, 102, 241, 0.45);
}

.opening-empty-state {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1.5rem;
  background: rgba(255, 255, 255, 0.02);
  border: 1px dashed rgba(255, 255, 255, 0.1);
  border-radius: var(--radius-md);
}

.story-premise {
  margin: 0;
  font-size: 0.95rem;
  line-height: 1.6;
  color: #e2e8f0;
}

.story-start-hint {
  margin: 0;
  font-size: 0.82rem;
  color: var(--muted);
  font-style: italic;
}

.turns-sequence {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.story-turn-item {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  padding: 1.15rem;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--radius-md);
  transition: all 180ms ease;
}

.story-turn-item.is-latest-turn {
  background: rgba(99, 102, 241, 0.05);
  border-color: rgba(99, 102, 241, 0.25);
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.25);
}

.story-turn-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.turn-meta-left {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.turn-step-chip {
  font-size: 0.72rem;
  font-weight: 700;
  color: #a5b4fc;
  padding: 0.15rem 0.5rem;
  background: rgba(99, 102, 241, 0.12);
  border-radius: 0.35rem;
}

.turn-timestamp {
  font-size: 0.74rem;
  color: var(--muted);
}

.player-action-block {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.65rem 0.85rem;
  background: rgba(236, 72, 153, 0.06);
  border: 1px solid rgba(236, 72, 153, 0.18);
  border-radius: 0.6rem;
}

.player-avatar-mini {
  width: 1.8rem;
  height: 1.8rem;
  border-radius: 9999px;
  background: linear-gradient(135deg, #ec4899, #f43f5e);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}

.player-action-content {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.player-name-tag {
  font-size: 0.7rem;
  font-weight: 700;
  color: #f472b6;
  text-transform: capitalize;
}

.player-action-text {
  margin: 0;
  font-size: 0.88rem;
  line-height: 1.45;
  color: #fce7f3;
}

.narrative-prose {
  font-size: 0.94rem;
  line-height: 1.7;
  color: #e2e8f0;
}

.narrative-static-text {
  margin: 0;
  white-space: pre-wrap;
}

.ai-processing-notice {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.65rem 1rem;
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: var(--radius-md);
  font-size: 0.85rem;
  color: #c7d2fe;
}

.spinner-dot {
  width: 0.65rem;
  height: 0.65rem;
  border-radius: 9999px;
  background: #818cf8;
  animation: pulse-dot 1.2s infinite ease-in-out;
}

.cancel-link {
  margin-left: auto;
  padding: 0.2rem 0.5rem;
  font-size: 0.75rem;
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid rgba(239, 68, 68, 0.35);
  color: #fca5a5;
  box-shadow: none;
}

.scene-cues-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.cues-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--muted);
}

.cue-pill {
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  border-radius: 0.35rem;
  background: rgba(255, 255, 255, 0.04);
  color: #cbd5e1;
}

/* Quick Choices Cards (Romcom Creator inspired) */
.quick-moves-card {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.25rem;
  background: var(--bg-surface);
}

.card-mini-header {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-wrap: wrap;
  width: 100%;
}

.action-progress-pill {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.2rem 0.55rem;
  border-radius: 9999px;
  background: rgba(236, 72, 153, 0.12);
  border: 1px solid rgba(236, 72, 153, 0.3);
  color: #f472b6;
  font-size: 0.74rem;
  font-weight: 600;
  line-height: 1;
  animation: progress-pill-pulse 2s infinite ease-in-out;
}

.progress-ring-svg {
  transform: rotate(-90deg);
  display: block;
  flex-shrink: 0;
}

.progress-ring-bg {
  stroke: rgba(255, 255, 255, 0.15);
}

.progress-ring-bar {
  stroke: #f472b6;
  transition: stroke-dashoffset 250ms ease;
}

.progress-ring-text {
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.02em;
}

@keyframes progress-pill-pulse {
  0%, 100% {
    box-shadow: 0 0 6px rgba(236, 72, 153, 0.15);
  }
  50% {
    box-shadow: 0 0 12px rgba(236, 72, 153, 0.35);
  }
}

.mini-hint {
  font-size: 0.8rem;
  color: var(--muted);
}

.quick-moves-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

@media (max-width: 640px) {
  .quick-moves-grid {
    grid-template-columns: 1fr;
  }
}

.quick-move-button {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.85rem 1rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-md);
  text-align: left;
  box-shadow: none;
  transition: all 200ms ease;
  cursor: pointer;
  width: 100%;
  position: relative;
  min-height: 4.6rem;
}

.quick-move-button:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.14);
  border-color: rgba(99, 102, 241, 0.45);
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
  z-index: 50;
}

.move-icon-badge {
  width: 2rem;
  height: 2rem;
  border-radius: 0.5rem;
  background: rgba(255, 255, 255, 0.06);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  flex-shrink: 0;
  margin-top: 0.1rem;
}

.move-content {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  flex: 1;
  min-width: 0;
}

.move-kind {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #a5b4fc;
}

.move-text {
  font-size: 0.84rem;
  color: #e2e8f0;
  line-height: 1.4;
  display: -webkit-box;
  line-clamp: 2;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  transition: color 180ms ease;
}

.quick-move-button:hover:not(:disabled) .move-text {
  color: #fff;
}

/* Custom Floating Tooltip */
.move-custom-tooltip {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  width: 100%;
  padding: 0.65rem 0.85rem;
  background: rgba(13, 16, 26, 0.96);
  border: 1px solid rgba(99, 102, 241, 0.4);
  border-radius: 0.65rem;
  backdrop-filter: blur(16px);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.6), 0 0 16px rgba(99, 102, 241, 0.16);
  opacity: 0;
  visibility: hidden;
  transform: translateY(4px);
  transition: opacity 160ms cubic-bezier(0.16, 1, 0.3, 1),
              transform 160ms cubic-bezier(0.16, 1, 0.3, 1),
              visibility 160ms;
  pointer-events: none;
  z-index: 100;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.move-custom-tooltip::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 1.5rem;
  border-width: 5px;
  border-style: solid;
  border-color: rgba(99, 102, 241, 0.5) transparent transparent transparent;
}

.quick-move-button:hover:not(:disabled) .move-custom-tooltip {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}

.tooltip-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding-bottom: 0.25rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.tooltip-kind {
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #a5b4fc;
}

.tooltip-hint {
  font-size: 0.68rem;
  color: var(--muted);
  font-weight: 500;
}

.tooltip-text {
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.45;
  color: #f8fafc;
  word-break: break-word;
  white-space: normal;
}

/* Custom Action Card */
.custom-action-card {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.25rem;
  background: var(--bg-surface);
}

.input-area-wrapper {
  display: flex;
  width: 100%;
}

.input-area-wrapper textarea {
  width: 100%;
  resize: vertical;
  min-height: 4.5rem;
  line-height: 1.5;
}

.send-btn {
  background: linear-gradient(135deg, var(--brand), #4f46e5);
  border: 1px solid var(--brand-light);
  color: #fff;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.send-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #6366f1, #4338ca);
  box-shadow: 0 6px 16px rgba(99, 102, 241, 0.45);
}

.send-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  box-shadow: none;
}

.action-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.78rem;
  color: var(--muted);
  flex-wrap: wrap;
  gap: 0.5rem;
}

.shortcut-hint strong {
  color: #cbd5e1;
}

.footer-buttons {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.small-btn {
  padding: 0.35rem 0.75rem;
  font-size: 0.78rem;
}

.fork-chip-btn {
  padding: 0.2rem 0.55rem;
  font-size: 0.72rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #cbd5e1;
  box-shadow: none;
}

.fork-chip-btn.selected {
  background: #6366f1;
  color: #fff;
  border-color: #818cf8;
}

/* Sidebar Panels */
.panel-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.85rem;
}

.panel-header-row h3 {
  margin: 0;
  font-size: 1.05rem;
}

.small-hint {
  font-size: 0.75rem;
  margin: 0 0 0.75rem;
}

.timelines-list {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.timeline-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.55rem 0.75rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--radius-md);
  color: #cbd5e1;
  box-shadow: none;
  text-align: left;
}

.timeline-item:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  transform: none;
}

.timeline-item.active {
  background: rgba(99, 102, 241, 0.15);
  border-color: #6366f1;
  color: #fff;
}

.timeline-name {
  font-size: 0.82rem;
  font-weight: 600;
}

.timeline-badge {
  font-size: 0.72rem;
  color: #a5b4fc;
}

@keyframes pulse-dot {
  0%, 100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.4);
    opacity: 0.5;
  }
}

@media (max-width: 1024px) {
  .vn-stage-layout {
    grid-template-columns: 1fr;
  }
  .vn-sidebar-column {
    position: static;
  }
}
</style>
