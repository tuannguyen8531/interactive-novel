import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type {
  BranchRecord,
  CharacterView,
  PlaythroughExport,
  PlaythroughRecord,
  TimelineEvent,
  TurnRecord,
  WorldRecord
} from '@/api/types'
import {
  appendFixtureTurn,
  createFixtureState,
  FIXTURE_PLAYTHROUGH_ID,
  forkFixtureBranch,
  restoreFixture,
  serializeFixture,
  type FixtureState
} from '@/fixtures/fixture'

const FIXTURE_STORAGE_KEY = 'interactive-novel.fixture.v1'

function toError(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause)
}

export const usePlaythroughStore = defineStore('playthrough', () => {
  const world = ref<WorldRecord | null>(null)
  const playthrough = ref<PlaythroughRecord | null>(null)
  const branches = ref<BranchRecord[]>([])
  const turns = ref<TurnRecord[]>([])
  const characters = ref<CharacterView[]>([])
  const timeline = ref<TimelineEvent[]>([])
  const selectedBranchId = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const fixtureMode = ref(false)

  const activeBranch = computed(() => {
    const branchId = selectedBranchId.value ?? playthrough.value?.active_branch_id
    return branches.value.find((branch) => branch.id === branchId) ?? null
  })

  const visibleTurns = computed(() => {
    const branchId = activeBranch.value?.id
    if (!branchId) return []
    return visibleTurnsForBranch(branchId, branches.value, turns.value)
  })

  const latestTurn = computed(() => visibleTurns.value.at(-1) ?? null)
  const headRevision = computed(() => activeBranch.value?.head_revision ?? visibleTurns.value.length)
  const worldTime = computed(() => playthrough.value?.world_clock_minutes ?? 0)

  function reset(): void {
    world.value = null
    playthrough.value = null
    branches.value = []
    turns.value = []
    characters.value = []
    timeline.value = []
    selectedBranchId.value = null
    fixtureMode.value = false
    error.value = null
  }

  async function open(playthroughId: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      if (playthroughId === FIXTURE_PLAYTHROUGH_ID) {
        loadFixture()
      } else {
        fixtureMode.value = false
        const exported = await api.exportPlaythrough(playthroughId)
        applyExport(exported)
      }
    } catch (cause) {
      error.value = toError(cause)
    } finally {
      loading.value = false
    }
  }

  async function refresh(): Promise<void> {
    if (!playthrough.value) return
    if (fixtureMode.value) {
      persistFixture()
      return
    }
    await open(playthrough.value.id)
  }

  async function loadLibraryPlaythrough(playthroughId: string): Promise<void> {
    await open(playthroughId)
  }

  function loadFixture(): void {
    fixtureMode.value = true
    const saved = typeof window === 'undefined' ? null : window.localStorage.getItem(FIXTURE_STORAGE_KEY)
    const state = saved ? restoreFixture(saved) ?? createFixtureState() : createFixtureState()
    applyFixtureState(state)
  }

  function resetFixture(): void {
    if (typeof window !== 'undefined') window.localStorage.removeItem(FIXTURE_STORAGE_KEY)
    loadFixture()
  }

  function applyFixtureState(state: FixtureState): void {
    world.value = state.world
    playthrough.value = state.playthrough
    branches.value = state.branches
    turns.value = state.turns
    characters.value = state.characters
    timeline.value = []
    selectedBranchId.value = state.playthrough.active_branch_id ?? state.playthrough.root_branch_id
    fixtureMode.value = true
  }

  function persistFixture(): void {
    if (!fixtureMode.value || !world.value || !playthrough.value || typeof window === 'undefined') return
    window.localStorage.setItem(
      FIXTURE_STORAGE_KEY,
      serializeFixture({
        world: world.value,
        playthrough: playthrough.value,
        branches: branches.value,
        turns: turns.value,
        characters: characters.value
      })
    )
  }

  function applyExport(exported: PlaythroughExport): void {
    world.value = exported.world
    playthrough.value = exported.playthrough
    branches.value = exported.branches
    turns.value = exported.turns
    characters.value = exported.characters
    timeline.value = exported.events
    selectedBranchId.value = exported.playthrough.active_branch_id ?? exported.playthrough.root_branch_id
  }

  async function switchBranch(branchId: string): Promise<void> {
    if (!playthrough.value) return
    error.value = null
    try {
      if (fixtureMode.value) {
        if (!branches.value.some((branch) => branch.id === branchId)) throw new Error('Branch does not exist.')
        selectedBranchId.value = branchId
        playthrough.value.active_branch_id = branchId
        playthrough.value.world_clock_minutes = visibleTurnsForBranch(branchId, branches.value, turns.value).at(-1)?.world_time_end ?? 8 * 60
        persistFixture()
      } else {
        await api.switchBranch(branchId, playthrough.value.id)
        await refresh()
      }
    } catch (cause) {
      error.value = toError(cause)
      throw cause
    }
  }

  async function fork(forkTurnId: string): Promise<BranchRecord | null> {
    if (!playthrough.value || !activeBranch.value) return null
    error.value = null
    try {
      let branch: BranchRecord
      if (fixtureMode.value) {
        const state = currentFixtureState()
        branch = forkFixtureBranch(state, activeBranch.value.id, forkTurnId)
        applyFixtureState(state)
        selectedBranchId.value = branch.id
        persistFixture()
      } else {
        branch = await api.forkBranch({ parent_branch_id: activeBranch.value.id, fork_turn_id: forkTurnId })
        await refresh()
        selectedBranchId.value = branch.id
      }
      return branch
    } catch (cause) {
      error.value = toError(cause)
      throw cause
    }
  }

  async function regenerate(turnId: string): Promise<BranchRecord | null> {
    if (!playthrough.value || !activeBranch.value || fixtureMode.value) return null
    error.value = null
    try {
      const branch = await api.regenerateBranch(activeBranch.value.id, turnId)
      await api.switchBranch(branch.id, playthrough.value.id)
      await refresh()
      return branch
    } catch (cause) {
      error.value = toError(cause)
      throw cause
    }
  }

  async function undo(headTurnId: string): Promise<BranchRecord | null> {
    if (!playthrough.value || !activeBranch.value || fixtureMode.value) return null
    error.value = null
    try {
      const branch = await api.undoBranch(activeBranch.value.id, headTurnId)
      await refresh()
      return branch
    } catch (cause) {
      error.value = toError(cause)
      throw cause
    }
  }

  function appendFixture(input: string): TurnRecord {
    if (!fixtureMode.value || !activeBranch.value) throw new Error('Fixture playthrough is not open.')
    const state = currentFixtureState()
    const turn = appendFixtureTurn(state, input, activeBranch.value.id)
    applyFixtureState(state)
    persistFixture()
    return turn
  }

  function currentFixtureState(): FixtureState {
    if (!world.value || !playthrough.value) throw new Error('Fixture playthrough is not open.')
    return { world: world.value, playthrough: playthrough.value, branches: branches.value, turns: turns.value, characters: characters.value }
  }

  return {
    world,
    playthrough,
    branches,
    turns,
    characters,
    timeline,
    selectedBranchId,
    loading,
    error,
    fixtureMode,
    activeBranch,
    visibleTurns,
    latestTurn,
    headRevision,
    worldTime,
    reset,
    open,
    refresh,
    loadLibraryPlaythrough,
    loadFixture,
    resetFixture,
    switchBranch,
    fork,
    regenerate,
    undo,
    appendFixture
  }
})

function visibleTurnsForBranch(branchId: string, branches: BranchRecord[], turns: TurnRecord[]): TurnRecord[] {
  const branch = branches.find((candidate) => candidate.id === branchId)
  if (!branch) return []
  const parentTurns = branch.parent_branch_id ? visibleTurnsForBranch(branch.parent_branch_id, branches, turns) : []
  const forkIndex = branch.fork_turn_id ? parentTurns.findIndex((turn) => turn.id === branch.fork_turn_id) : -1
  const inherited = forkIndex >= 0 ? parentTurns.slice(0, forkIndex + 1) : parentTurns
  const local = turns
    .filter((turn) => turn.branch_id === branchId)
    .sort((left, right) => left.base_revision - right.base_revision || left.created_at.localeCompare(right.created_at))
  return [...inherited, ...local]
}
