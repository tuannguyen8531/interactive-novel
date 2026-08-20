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
import type { CharacterView, MemoryView } from '@/api/types'

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

const routePlaythroughId = computed(() => String(route.params.playthroughId ?? ''))
const playerCharacter = computed(() => findPlayerCharacter(playthrough.playthrough, playthrough.characters))
const playerTurns = computed(() => playthrough.visibleTurns.filter((turn) => !isOpeningTurn(turn)))
const latestPlayerTurn = computed(() => playerTurns.value.at(-1) ?? null)
const activeBranchName = computed(() =>
  branches.activeBranch ? branchDisplayName(branches.activeBranch, branches.branches) : 'No timeline'
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
  const latestTurn = visibleTurns[visibleTurns.length - 1]
  return latestTurn ? turnMoveSuggestions(latestTurn) : []
})
const suggestedActions = computed(() =>
  latestTurnSuggestions.value.length > 0 ? latestTurnSuggestions.value : guidance.value.suggestedActions
)
const isFirstMove = computed(() => playerTurns.value.length === 0)
const actionPlaceholder = computed(() =>
  suggestedActions.value[0]?.text ??
    (playerCharacter.value
      ? `Describe what ${playerCharacter.value.display_name} tries to do…`
      : 'Describe what you try to do…')
)

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
    debug.refresh()
  }
)

async function openRoute(): Promise<void> {
  if (!routePlaythroughId.value) return
  loadingRoute.value = true
  await playthrough.open(routePlaythroughId.value)
  characters.clear()
  const defaultCharacter = playerCharacter.value ?? playthrough.characters[0]
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
    actor_id: playthrough.playthrough.player_character_id ?? undefined,
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

async function regenerateLastTurn(): Promise<void> {
  const turn = latestPlayerTurn.value
  if (!turn || jobs.active || playthrough.fixtureMode) return
  if (!window.confirm('Regenerate the latest move on a new branch? The existing version will remain available.')) return
  const action = turn.raw_input
  await playthrough.regenerate(turn.id)
  input.value = action
  await submit()
}

async function undoLastTurn(): Promise<void> {
  const turn = latestPlayerTurn.value
  if (!turn || jobs.active || playthrough.fixtureMode) return
  if (!window.confirm('Undo the latest move on a new branch? No story history will be deleted.')) return
  await playthrough.undo(turn.id)
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

async function chooseSuggestedAction(action: string): Promise<void> {
  input.value = action
  await nextTick()
  actionInput.value?.focus()
  actionInput.value?.setSelectionRange(action.length, action.length)
}

function profileText(key: string): string | null {
  return characterProfileText(playerCharacter.value, key)
}

function characterProfileText(character: CharacterView | null, key: string): string | null {
  const value = character?.public_profile[key]
  return typeof value === 'string' || typeof value === 'number' ? String(value) : null
}

function profileList(key: string): string[] {
  return characterProfileList(playerCharacter.value, key)
}

function characterProfileList(character: CharacterView | null, key: string): string[] {
  const value = character?.public_profile[key]
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

function selectedProfileText(key: string): string | null {
  return characterProfileText(selectedCharacter.value, key)
}

function selectedProfileList(key: string): string[] {
  return characterProfileList(selectedCharacter.value, key)
}

function selectedStateText(key: string): string | null {
  const value = selectedCharacter.value?.state?.[key]
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

function memoryLabel(memory: MemoryView): string {
  const qualifier = memory.kind === 'belief' ? memory.payload.stance : memory.payload.method
  const detail = typeof qualifier === 'string' && qualifier.trim() ? ` · ${qualifier.replaceAll('_', ' ')}` : ''
  return `${memory.kind.replaceAll('_', ' ')}${detail}`
}

function memoryConfidence(memory: MemoryView): string | null {
  return memory.confidence === null ? null : `${Math.round(memory.confidence * 100)}% confidence`
}

function playerTurnNumber(index: number): number {
  return playthrough.visibleTurns.slice(0, index + 1).filter((turn) => !isOpeningTurn(turn)).length
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
          {{ playthrough.world.tone || 'A new scene' }} · {{ formatWorldTime(playthrough.worldTime) }} ·
          {{ activeBranchName }}
        </p>
      </div>
    </section>

    <div class="play-layout">
      <main class="play-main">
        <section v-if="playerCharacter" class="panel role-panel" aria-label="Player character and scene guidance">
          <div class="role-identity">
            <div class="role-title">
              <span class="avatar player-avatar">{{ playerCharacter.display_name.slice(0, 1) }}</span>
              <div>
                <p class="eyebrow">You are playing as</p>
                <h2>{{ playerCharacter.display_name }}</h2>
              </div>
            </div>
            <p class="role-meta">
              {{ profileText('role') || 'Protagonist' }}
              <template v-if="profileText('age')"> · {{ profileText('age') }} years old</template>
            </p>
            <p v-if="profileText('background')" class="role-background">{{ profileText('background') }}</p>
            <div v-if="profileList('traits').length" class="trait-list">
              <span v-for="trait in profileList('traits')" :key="trait">{{ trait }}</span>
            </div>
          </div>
          <div class="scene-guide">
            <p class="eyebrow">{{ isFirstMove ? 'Start here' : 'Current scene' }}</p>
            <h3>{{ guidance.locationName || 'The story is waiting' }}</h3>
            <p>
              You control {{ playerCharacter.display_name }}. Write what they do, say, ask or notice—the story will respond.
            </p>
            <template v-if="isFirstMove && guidance.sceneCues.length">
              <p class="suggestion-label">What is happening in the opening scene:</p>
              <div class="scene-cue-list">
                <span v-for="cue in guidance.sceneCues" :key="cue">{{ cue }}</span>
              </div>
            </template>
          </div>
        </section>

        <section class="panel transcript-panel" aria-label="Narrative transcript">
          <div class="transcript-heading">
            <div>
              <p class="eyebrow">Transcript</p>
              <h2>Story so far</h2>
            </div>
            <span v-if="playthrough.fixtureMode" class="fixture-badge">browser fixture</span>
          </div>

          <div ref="transcriptScroll" class="transcript-scroll">
            <div v-if="playthrough.visibleTurns.length === 0" class="opening-scene">
              <p class="eyebrow">Opening scene</p>
              <p>{{ playthrough.world.premise }}</p>
              <p class="muted">Write an action below. The fixture remembers this branch locally after every turn.</p>
            </div>
            <div v-else class="transcript">
              <article v-for="(turn, index) in playthrough.visibleTurns" :key="turn.id" class="turn-entry">
                <div class="turn-label">
                  <span>{{ isOpeningTurn(turn) ? 'Opening scene' : `Move ${playerTurnNumber(index)}` }}</span>
                  <span class="turn-clock" :title="`World minute ${turn.world_time_end}`">
                    <span>{{ formatWorldTime(turn.world_time_end) }}</span>
                    <small v-if="turn.duration_minutes > 0">+{{ formatTurnDuration(turn.duration_minutes) }}</small>
                  </span>
                </div>
                <p v-if="!isOpeningTurn(turn)" class="player-action">
                  {{ playerCharacter?.display_name || 'You' }} · {{ turn.raw_input }}
                </p>
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
          </div>
        </section>

        <section class="panel action-panel">
          <div class="action-heading">
            <div>
              <p class="eyebrow">Your move</p>
              <h2>
                {{ playerCharacter ? `What does ${playerCharacter.display_name} do next?` : 'What do you do next?' }}
              </h2>
            </div>
            <div class="turn-actions">
              <button
                v-if="latestPlayerTurn && !playthrough.fixtureMode"
                class="secondary small-button"
                type="button"
                :disabled="jobs.active"
                @click="undoLastTurn"
              >
                Undo last move
              </button>
              <button
                v-if="latestPlayerTurn && !playthrough.fixtureMode"
                class="secondary small-button"
                type="button"
                :disabled="jobs.active"
                @click="regenerateLastTurn"
              >
                Regenerate
              </button>
              <button v-if="jobs.active" class="danger" type="button" @click="jobs.cancel()">Cancel</button>
            </div>
          </div>
          <p id="player-move-help" class="move-help">
            Write naturally—no command syntax is required. Describe what your character tries to do, say, ask, notice or
            think. The story decides how the world and other characters respond.
          </p>
          <div class="move-example-heading">
            <strong>Need an idea?</strong>
            <span>
              {{
                latestTurnSuggestions.length > 0
                  ? 'These ideas follow the latest scene. Choose one, then edit it however you like.'
                  : 'Choose an example, then edit it however you like.'
              }}
            </span>
          </div>
          <div class="move-example-grid" aria-label="Player move examples">
            <button
              v-for="suggestion in suggestedActions"
              :key="`${suggestion.kind}:${suggestion.text}`"
              class="move-example"
              type="button"
              :disabled="jobs.active"
              @click="chooseSuggestedAction(suggestion.text)"
            >
              <span>{{ suggestion.kind }}</span>
              <small>{{ suggestion.text }}</small>
            </button>
          </div>
          <label class="move-label" for="player-move">Write your move</label>
          <textarea
            id="player-move"
            ref="actionInput"
            v-model="input"
            :disabled="jobs.active"
            rows="4"
            maxlength="20000"
            :placeholder="actionPlaceholder"
            aria-describedby="player-move-help"
            @keydown.ctrl.enter.prevent="submit"
          />
          <div class="action-footer">
            <span class="muted">Ctrl + Enter to send · {{ input.length }}/20,000</span>
            <button type="button" :disabled="jobs.active || !input.trim()" @click="submit">Continue story</button>
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
              :title="branch.id"
              @click="branches.switchBranch(branch.id)"
            >
              <span>{{ branchDisplayName(branch, branches.branches) }}</span>
              <small>{{ branchProgressLabel(branch) }}</small>
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
                <small>
                  {{ character.id === playthrough.playthrough.player_character_id ? 'You · ' : '' }}{{ character.public_profile.role || 'present' }}
                </small>
              </span>
            </button>
          </div>
          <div v-if="selectedCharacter" class="character-detail">
            <div class="character-detail-header">
              <span class="avatar detail-avatar">{{ selectedCharacter.display_name.slice(0, 1) }}</span>
              <div>
                <span class="character-kind">
                  {{ selectedCharacter.id === playthrough.playthrough.player_character_id ? 'Player character' : 'Story character' }}
                </span>
                <h3>{{ selectedCharacter.display_name }}</h3>
                <p v-if="selectedCharacter.aliases.length" class="character-aliases">
                  Also known as {{ selectedCharacter.aliases.join(', ') }}
                </p>
              </div>
            </div>

            <div v-if="selectedProfileText('age') || selectedProfileText('role')" class="character-facts">
              <div v-if="selectedProfileText('age')">
                <span>Age</span>
                <strong>{{ selectedProfileText('age') }}</strong>
              </div>
              <div v-if="selectedProfileText('role')">
                <span>Role</span>
                <strong>{{ selectedProfileText('role') }}</strong>
              </div>
            </div>

            <div v-if="selectedStateText('location_id') || selectedStateText('physical_condition')" class="character-status">
              <span v-if="selectedStateText('location_id')">At {{ selectedStateText('location_id')?.replaceAll('_', ' ') }}</span>
              <span v-if="selectedStateText('physical_condition')">
                {{ selectedStateText('physical_condition')?.replaceAll('_', ' ') }}
              </span>
            </div>

            <section v-if="selectedProfileText('background')" class="profile-section">
              <h4>Background</h4>
              <p>{{ selectedProfileText('background') }}</p>
            </section>

            <section v-if="selectedProfileText('voice')" class="profile-section voice-section">
              <h4>Voice</h4>
              <p>“{{ selectedProfileText('voice') }}”</p>
            </section>

            <section v-if="selectedProfileList('traits').length" class="profile-section">
              <h4>Traits</h4>
              <div class="profile-chip-list">
                <span v-for="trait in selectedProfileList('traits')" :key="trait">{{ trait }}</span>
              </div>
            </section>

            <section v-if="selectedProfileList('values').length" class="profile-section">
              <h4>Values</h4>
              <div class="profile-chip-list value-chips">
                <span v-for="value in selectedProfileList('values')" :key="value">{{ value }}</span>
              </div>
            </section>

            <section class="memory-section">
              <div class="memory-heading">
                <h4>Visible memories</h4>
                <span v-if="characters.memories.length">{{ characters.memories.length }}</span>
              </div>
              <p v-if="characters.loading" class="memory-empty">Loading memories…</p>
              <p v-else-if="characters.error" class="memory-error">{{ characters.error }}</p>
              <p v-else-if="characters.memories.length === 0" class="memory-empty">
                No turn-scoped observations or beliefs have been formed yet.
              </p>
              <div v-else class="memory-list">
                <article v-for="memory in characters.memories" :key="memory.memory_id" class="memory-item">
                  <strong>{{ memoryLabel(memory) }}</strong>
                  <span>
                    Minute {{ memory.world_time }}
                    <template v-if="memoryConfidence(memory)"> · {{ memoryConfidence(memory) }}</template>
                  </span>
                </article>
              </div>
            </section>
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

.role-panel {
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
  gap: 1.25rem;
  background: linear-gradient(135deg, #fffdf8, #f6e9df);
}

.role-identity {
  padding-right: 1.25rem;
  border-right: 1px solid var(--line);
}

.role-title {
  display: flex;
  gap: 0.8rem;
  align-items: center;
}

.role-title h2,
.scene-guide h3 {
  margin: 0;
}

.player-avatar {
  width: 2.8rem;
  height: 2.8rem;
  flex: 0 0 auto;
  font-size: 1.15rem;
}

.role-meta {
  margin: 0.85rem 0 0.4rem;
  color: var(--accent-dark);
  font-weight: 700;
  overflow-wrap: break-word;
  word-break: normal;
}

.role-background,
.scene-guide p {
  margin: 0.5rem 0 0;
  color: var(--muted);
  line-height: 1.55;
}

.trait-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-top: 0.75rem;
}

.trait-list span {
  padding: 0.25rem 0.5rem;
  border-radius: 99rem;
  background: #fff9;
  color: var(--accent-dark);
  font-size: 0.75rem;
}

.suggestion-label {
  font-size: 0.82rem;
  font-weight: 700;
}

.scene-cue-list {
  display: grid;
  gap: 0.35rem;
  margin-top: 0.55rem;
}

.scene-cue-list span {
  position: relative;
  padding-left: 1rem;
  color: var(--accent-dark);
  font-size: 0.82rem;
}

.scene-cue-list span::before {
  position: absolute;
  left: 0;
  content: '•';
  color: var(--accent);
}

.transcript-heading {
  flex: 0 0 auto;
  margin-bottom: 1.2rem;
}

.transcript-panel {
  display: flex;
  height: 38rem;
  flex-direction: column;
}

.transcript-scroll {
  min-height: 0;
  padding-right: 0.45rem;
  overflow-y: auto;
  overscroll-behavior: contain;
  scroll-behavior: smooth;
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
  gap: 0.75rem;
  justify-content: space-between;
  color: var(--muted);
  font-size: 0.75rem;
}

.turn-clock {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  justify-content: flex-end;
  text-align: right;
}

.turn-clock small {
  padding: 0.08rem 0.35rem;
  border-radius: 99rem;
  background: var(--accent-soft);
  color: var(--accent-dark);
  font-size: 0.68rem;
  font-weight: 700;
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

.move-help {
  max-width: 52rem;
  margin: 0.65rem 0 1rem;
  color: var(--muted);
  line-height: 1.55;
}

.move-example-heading {
  display: flex;
  gap: 0.5rem;
  align-items: baseline;
  margin-bottom: 0.55rem;
  font-size: 0.82rem;
}

.move-example-heading span {
  color: var(--muted);
}

.move-example-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.55rem;
}

.move-example {
  display: grid;
  grid-template-columns: 3.8rem minmax(0, 1fr);
  gap: 0.55rem;
  align-items: start;
  border: 1px solid var(--line);
  background: #fffaf4;
  color: var(--ink);
  text-align: left;
}

.move-example:hover:not(:disabled) {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--ink);
  transform: none;
}

.move-example span {
  color: var(--accent-dark);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.move-example small {
  color: var(--muted);
  line-height: 1.35;
}

.move-label {
  display: block;
  margin-top: 1rem;
  font-size: 0.82rem;
  font-weight: 800;
}

.action-panel textarea {
  width: 100%;
  resize: vertical;
  margin: 0.4rem 0 0.65rem;
  padding: 0.85rem;
  border: 1px solid var(--line);
  border-radius: 0.65rem;
  background: #fff;
  color: var(--ink);
}

.turn-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  justify-content: flex-end;
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
  min-width: 0;
  gap: 0.15rem;
}

.character-item strong,
.character-item small {
  min-width: 0;
  overflow-wrap: break-word;
  word-break: normal;
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

.character-detail-header {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.detail-avatar {
  width: 2.75rem;
  height: 2.75rem;
  flex: 0 0 auto;
  font-size: 1rem;
}

.character-kind {
  color: var(--accent);
  font-size: 0.65rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.character-detail-header h3 {
  margin: 0.1rem 0 0;
  font-size: 1.15rem;
}

.character-aliases {
  margin: 0.15rem 0 0;
  color: var(--muted);
  font-size: 0.72rem;
}

.character-facts {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 0.5rem;
  margin-top: 1rem;
}

.character-facts div {
  display: grid;
  min-width: 0;
  gap: 0.15rem;
  padding: 0.65rem;
  border: 1px solid var(--line);
  border-radius: 0.65rem;
  background: #f8f4eb;
}

.character-facts span,
.profile-section h4,
.memory-heading h4 {
  margin: 0;
  color: var(--muted);
  font-size: 0.65rem;
  font-weight: 800;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.character-facts strong {
  min-width: 0;
  font-size: 0.82rem;
  line-height: 1.35;
  overflow-wrap: break-word;
  text-transform: capitalize;
  word-break: normal;
}

.character-status {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.65rem;
}

.character-status span {
  padding: 0.25rem 0.45rem;
  border-radius: 99rem;
  background: #edf5ef;
  color: var(--green);
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: capitalize;
}

.profile-section,
.memory-section {
  margin-top: 1rem;
}

.profile-section p {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.8rem;
  line-height: 1.55;
}

.voice-section p {
  padding-left: 0.65rem;
  border-left: 2px solid #d7b19c;
  color: var(--accent-dark);
  font-style: italic;
}

.profile-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.45rem;
}

.profile-chip-list span {
  padding: 0.28rem 0.48rem;
  border-radius: 99rem;
  background: var(--accent-soft);
  color: var(--accent-dark);
  font-size: 0.7rem;
}

.value-chips span {
  background: #edf5ef;
  color: var(--green);
}

.memory-section {
  padding-top: 1rem;
  border-top: 1px solid var(--line);
}

.memory-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.memory-heading > span {
  display: grid;
  min-width: 1.35rem;
  height: 1.35rem;
  place-items: center;
  border-radius: 99rem;
  background: var(--accent-soft);
  color: var(--accent-dark);
  font-size: 0.65rem;
  font-weight: 800;
}

.memory-empty,
.memory-error {
  margin: 0.5rem 0 0;
  padding: 0.65rem;
  border-radius: 0.55rem;
  background: #f8f4eb;
  color: var(--muted);
  font-size: 0.75rem;
  line-height: 1.45;
}

.memory-error {
  background: #fff0f0;
  color: #8e303b;
}

.memory-list {
  display: grid;
  gap: 0.4rem;
  margin-top: 0.55rem;
}

.memory-item {
  display: grid;
  gap: 0.15rem;
  padding: 0.6rem;
  border: 1px solid var(--line);
  border-radius: 0.55rem;
}

.memory-item strong {
  font-size: 0.75rem;
  text-transform: capitalize;
}

.memory-item span {
  color: var(--muted);
  font-size: 0.68rem;
}

@media (max-width: 840px) {
  .play-layout {
    grid-template-columns: 1fr;
  }

  .role-panel {
    grid-template-columns: 1fr;
  }

  .role-identity {
    padding-right: 0;
    padding-bottom: 1rem;
    border-right: 0;
    border-bottom: 1px solid var(--line);
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

  .action-footer button {
    width: 100%;
    margin-top: 0.75rem;
  }

  .character-panel {
    margin-top: 1rem;
  }

  .move-example-grid {
    grid-template-columns: 1fr;
  }

  .move-example-heading {
    display: grid;
  }

  .transcript-panel {
    height: 30rem;
  }
}
</style>
