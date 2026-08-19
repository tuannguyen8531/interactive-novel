<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useBranchStore } from '@/stores/branch'
import { useCharacterStore } from '@/stores/character'
import { useDebugStore } from '@/stores/debug'
import { usePlaythroughStore } from '@/stores/playthrough'
import { useTurnJobStore, type TurnRequest } from '@/stores/turnJob'

const route = useRoute()
const router = useRouter()
const playthrough = usePlaythroughStore()
const branches = useBranchStore()
const characters = useCharacterStore()
const jobs = useTurnJobStore()
const debug = useDebugStore()
const input = ref('')
const selectedForkTurnId = ref<string | null>(null)
const openCharacterId = ref<string | null>(null)
const loadingRoute = ref(false)

const routePlaythroughId = computed(() => String(route.params.playthroughId ?? ''))
const turnCount = computed(() => playthrough.visibleTurns.length)
const canFork = computed(() => selectedForkTurnId.value !== null && !jobs.active)
const selectedCharacter = computed(() => characters.selected)

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
  () => jobs.terminal,
  async (terminal, wasTerminal) => {
    if (!terminal || wasTerminal || playthrough.fixtureMode) return
    await playthrough.refresh()
    debug.refresh()
  }
)

async function openRoute(): Promise<void> {
  if (!routePlaythroughId.value) return
  loadingRoute.value = true
  await playthrough.open(routePlaythroughId.value)
  characters.clear()
  if (playthrough.characters[0]) {
    openCharacterId.value = playthrough.characters[0].id
    await characters.select(playthrough.characters[0].id)
  }
  debug.refresh()
  loadingRoute.value = false
}

function request(): TurnRequest | null {
  const branch = playthrough.activeBranch
  if (!branch || !playthrough.playthrough || !input.value.trim()) return null
  return {
    playthrough_id: playthrough.playthrough.id,
    branch_id: branch.id,
    raw_input: input.value.trim(),
    base_revision: branch.head_revision,
    parent_turn_id: playthrough.latestTurn?.id ?? branch.fork_turn_id
  }
}

async function submit(): Promise<void> {
  const turnRequest = request()
  if (!turnRequest) return
  const action = input.value.trim()
  input.value = ''
  try {
    if (playthrough.fixtureMode) {
      await jobs.runFixture(turnRequest, () => playthrough.appendFixture(action))
      debug.refresh()
    } else {
      await jobs.submit(turnRequest)
    }
  } catch {
    input.value = action
  }
}

async function fork(): Promise<void> {
  if (!selectedForkTurnId.value) return
  await branches.fork(selectedForkTurnId.value)
  selectedForkTurnId.value = null
  debug.refresh()
}

async function chooseCharacter(characterId: string): Promise<void> {
  openCharacterId.value = characterId
  await characters.select(characterId)
}

function narrative(turn: { final_narrative: string | null }): string {
  return turn.final_narrative ?? 'The turn finished without a final narrative.'
}
</script>

<template>
  <div v-if="loadingRoute || playthrough.loading" class="empty-state">Opening playthrough…</div>
  <div v-else-if="playthrough.error" class="error-box" role="alert">
    <strong>Could not open this playthrough.</strong>
    <p>{{ playthrough.error }}</p>
    <button class="secondary" type="button" @click="router.push('/')">Return to library</button>
  </div>
  <template v-else-if="playthrough.playthrough && playthrough.world">
    <section class="scene-header">
      <div>
        <button class="back-link" type="button" @click="router.push('/')">← Library</button>
        <p class="eyebrow">{{ playthrough.world.genre || 'Story' }}</p>
        <h1>{{ playthrough.world.name }}</h1>
        <p class="scene-meta">
          {{ playthrough.world.tone || 'A new scene' }} · {{ playthrough.worldTime }} minutes ·
          {{ branches.activeBranch?.id }}
        </p>
      </div>
      <div class="turn-counter" aria-label="turn count">
        <strong>{{ turnCount }}</strong>
        <span>turns</span>
      </div>
    </section>

    <div class="play-layout">
      <main class="play-main">
        <section class="panel transcript-panel" aria-label="Narrative transcript">
          <div class="transcript-heading">
            <div>
              <p class="eyebrow">Transcript</p>
              <h2>What happens next?</h2>
            </div>
            <span v-if="playthrough.fixtureMode" class="fixture-badge">browser fixture</span>
          </div>

          <div v-if="playthrough.visibleTurns.length === 0" class="opening-scene">
            <p class="eyebrow">Opening scene</p>
            <p>{{ playthrough.world.premise }}</p>
            <p class="muted">Write an action below. The fixture remembers this branch locally after every turn.</p>
          </div>
          <div v-else class="transcript">
            <article v-for="(turn, index) in playthrough.visibleTurns" :key="turn.id" class="turn-entry">
              <div class="turn-label">
                <span>Turn {{ index + 1 }}</span>
                <time :datetime="turn.created_at">{{ turn.world_time_end }} min</time>
              </div>
              <p class="player-action">You · {{ turn.raw_input }}</p>
              <p class="narrative">{{ narrative(turn) }}</p>
              <button
                class="fork-chip"
                :class="{ selected: selectedForkTurnId === turn.id }"
                type="button"
                :disabled="jobs.active || !canForkFromTurn(turn.branch_id)"
                @click="selectedForkTurnId = selectedForkTurnId === turn.id ? null : turn.id"
              >
                {{ canForkFromTurn(turn.branch_id) ? (selectedForkTurnId === turn.id ? 'Selected for fork' : 'Fork here') : 'Inherited' }}
              </button>
            </article>
          </div>
        </section>

        <section class="panel action-panel">
          <div class="action-heading">
            <div>
              <p class="eyebrow">Free action</p>
              <h2>Your move</h2>
            </div>
            <button v-if="jobs.active" class="danger" type="button" @click="jobs.cancel()">Cancel</button>
          </div>
          <textarea
            v-model="input"
            :disabled="jobs.active"
            rows="3"
            maxlength="20000"
            placeholder="Describe what you do, say or notice…"
            @keydown.ctrl.enter.prevent="submit"
          />
          <div class="action-footer">
            <span class="muted">Ctrl + Enter to send · {{ input.length }}/20,000</span>
            <button type="button" :disabled="jobs.active || !input.trim()" @click="submit">Send action</button>
          </div>
          <div v-if="jobs.loading || jobs.current" class="job-status" aria-live="polite">
            <div class="job-status-line">
              <span class="status-dot" :class="{ running: jobs.active, done: jobs.terminal }" />
              <strong>{{ jobs.progress }}</strong>
              <button v-if="jobs.error" class="secondary small-button" type="button" @click="jobs.retry()">Retry</button>
            </div>
            <div v-if="jobs.events.length" class="job-events">
              <span v-for="event in jobs.events.slice(-4)" :key="event.id">{{ event.event_type.replaceAll('_', ' ') }}</span>
            </div>
          </div>
          <div v-if="jobs.error" class="error-box" role="alert">
            {{ jobs.error }}
            <button class="secondary small-button" type="button" @click="jobs.retry()">Retry action</button>
          </div>
        </section>
      </main>

      <aside class="play-sidebar">
        <section class="panel branch-panel">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">Timeline</p>
              <h2>Branches</h2>
            </div>
            <button class="secondary small-button" type="button" :disabled="!canFork" @click="fork">Fork</button>
          </div>
          <p class="muted small-copy">Select a turn in the transcript, then fork a new continuation.</p>
          <div class="branch-list">
            <button
              v-for="branch in branches.branches"
              :key="branch.id"
              class="branch-item"
              :class="{ active: branch.id === branches.activeBranchId }"
              type="button"
              @click="branches.switchBranch(branch.id)"
            >
              <span>{{ branch.id.replace('fixture-', '') }}</span>
              <small>rev {{ branch.head_revision }}</small>
            </button>
          </div>
        </section>

        <section class="panel character-panel">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">Presence</p>
              <h2>Characters</h2>
            </div>
          </div>
          <div class="character-list">
            <button
              v-for="character in characters.characters"
              :key="character.id"
              class="character-item"
              :class="{ active: character.id === openCharacterId }"
              type="button"
              @click="chooseCharacter(character.id)"
            >
              <span class="avatar">{{ character.display_name.slice(0, 1) }}</span>
              <span>
                <strong>{{ character.display_name }}</strong>
                <small>{{ character.public_profile.role || 'present' }}</small>
              </span>
            </button>
          </div>
          <div v-if="selectedCharacter" class="character-detail">
            <h3>{{ selectedCharacter.display_name }}</h3>
            <p v-for="(value, key) in selectedCharacter.public_profile" :key="key" class="detail-row">
              <strong>{{ key }}</strong> {{ value }}
            </p>
            <p v-if="characters.loading" class="muted">Loading scoped memory…</p>
            <p v-else-if="characters.memories.length === 0" class="muted">No visible memories yet.</p>
          </div>
        </section>
      </aside>
    </div>
  </template>
</template>

<style scoped>
.scene-header,
.transcript-heading,
.action-heading,
.panel-heading,
.action-footer,
.job-status-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.scene-header {
  margin-bottom: 1.35rem;
}

.back-link {
  margin-bottom: 1rem;
  padding: 0;
  background: transparent;
  color: var(--muted);
}

.back-link:hover:not(:disabled) {
  background: transparent;
  color: var(--accent);
  transform: none;
}

.scene-header h1 {
  margin-bottom: 0.35rem;
}

.scene-meta {
  margin-bottom: 0;
  color: var(--muted);
}

.turn-counter {
  display: grid;
  min-width: 5.5rem;
  padding: 0.75rem;
  border: 1px solid var(--line);
  border-radius: 0.8rem;
  background: var(--paper);
  text-align: center;
}

.turn-counter strong {
  font-size: 1.6rem;
}

.turn-counter span {
  color: var(--muted);
  font-size: 0.75rem;
}

.play-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(17rem, 22rem);
  gap: 1rem;
  align-items: start;
}

.play-main,
.play-sidebar {
  display: grid;
  gap: 1rem;
}

.transcript-heading {
  margin-bottom: 1.2rem;
}

.transcript-heading h2,
.action-heading h2,
.panel-heading h2 {
  margin-bottom: 0;
}

.fixture-badge {
  border-radius: 99rem;
  padding: 0.35rem 0.6rem;
  background: var(--accent-soft);
  color: var(--accent-dark);
  font-size: 0.75rem;
  font-weight: 700;
}

.opening-scene {
  padding: 1.25rem;
  border-radius: 0.8rem;
  background: #f6f0e4;
  line-height: 1.7;
}

.opening-scene p:last-child {
  margin-bottom: 0;
}

.turn-entry {
  position: relative;
  padding: 1.15rem 0 1.5rem;
  border-top: 1px solid var(--line);
}

.turn-entry:first-child {
  padding-top: 0;
  border-top: 0;
}

.turn-label {
  display: flex;
  justify-content: space-between;
  color: var(--muted);
  font-size: 0.75rem;
}

.player-action {
  margin: 0.7rem 0;
  color: var(--accent-dark);
  font-weight: 700;
}

.narrative {
  margin-bottom: 0.65rem;
  line-height: 1.75;
  white-space: pre-line;
}

.fork-chip {
  padding: 0.35rem 0.6rem;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--muted);
  font-size: 0.75rem;
}

.fork-chip:hover:not(:disabled),
.fork-chip.selected {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent-dark);
  transform: none;
}

.action-panel textarea {
  width: 100%;
  resize: vertical;
  margin: 1rem 0 0.65rem;
  padding: 0.85rem;
  border: 1px solid var(--line);
  border-radius: 0.65rem;
  background: #fff;
  color: var(--ink);
}

.action-panel textarea:focus {
  outline: 2px solid var(--accent-soft);
  border-color: var(--accent);
}

.action-footer {
  gap: 1rem;
}

.small-copy,
.small-button,
.job-events {
  font-size: 0.78rem;
}

.job-status {
  margin-top: 1rem;
  padding-top: 0.8rem;
  border-top: 1px solid var(--line);
}

.status-dot {
  width: 0.65rem;
  height: 0.65rem;
  margin-right: 0.5rem;
  border-radius: 50%;
  background: var(--green);
}

.status-dot.running {
  background: #bd8341;
  box-shadow: 0 0 0 0.25rem #bd834125;
}

.status-dot.done {
  background: var(--green);
}

.job-status-line strong {
  flex: 1;
}

.job-events {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 0.65rem;
  color: var(--muted);
}

.job-events span {
  padding: 0.25rem 0.45rem;
  border-radius: 0.35rem;
  background: #f1ece2;
}

.branch-panel,
.character-panel {
  box-shadow: none;
}

.panel-heading {
  align-items: flex-start;
}

.branch-list,
.character-list {
  display: grid;
  gap: 0.5rem;
  margin-top: 1rem;
}

.branch-item,
.character-item {
  display: flex;
  justify-content: space-between;
  width: 100%;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink);
  text-align: left;
}

.branch-item:hover:not(:disabled),
.character-item:hover:not(:disabled),
.branch-item.active,
.character-item.active {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent-dark);
  transform: none;
}

.branch-item small,
.character-item small {
  color: var(--muted);
}

.character-item {
  justify-content: flex-start;
  gap: 0.65rem;
}

.character-item span:last-child {
  display: grid;
  gap: 0.15rem;
}

.avatar {
  display: grid;
  width: 2rem;
  height: 2rem;
  place-items: center;
  border-radius: 50%;
  background: #dec6b9;
  color: var(--accent-dark);
  font-weight: 800;
}

.character-detail {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--line);
}

.character-detail h3 {
  margin-bottom: 0.6rem;
}

.detail-row {
  margin-bottom: 0.35rem;
  color: var(--muted);
  font-size: 0.82rem;
}

.detail-row strong {
  color: var(--ink);
}

@media (max-width: 840px) {
  .play-layout {
    grid-template-columns: 1fr;
  }

  .play-sidebar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 580px) {
  .scene-header,
  .action-footer,
  .play-sidebar {
    display: block;
  }

  .turn-counter {
    width: 5.5rem;
    margin-top: 1rem;
  }

  .action-footer button {
    width: 100%;
    margin-top: 0.75rem;
  }

  .character-panel {
    margin-top: 1rem;
  }
}
</style>
