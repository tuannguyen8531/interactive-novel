import type {
  BranchRecord,
  CharacterView,
  PlaythroughRecord,
  TurnRecord,
  WorldRecord
} from '@/api/types'

export const FIXTURE_PLAYTHROUGH_ID = 'fixture-playthrough'
export const FIXTURE_WORLD_ID = 'fixture-world'
export const FIXTURE_ROOT_BRANCH_ID = 'fixture-root'

export interface FixtureState {
  world: WorldRecord
  playthrough: PlaythroughRecord
  branches: BranchRecord[]
  turns: TurnRecord[]
  characters: CharacterView[]
}

const now = '2026-08-19T00:00:00+00:00'

function makeWorld(): WorldRecord {
  return {
    id: FIXTURE_WORLD_ID,
    name: 'Moonlight Academy',
    premise: 'A quiet school hides a changing constellation of friendships, promises and first courage.',
    genre: 'school_romance',
    tone: 'warm, reflective',
    canon_rules: { setting: 'Hoshikawa Academy', season: 'early autumn' },
    content_policy: { rating: 'teen_14_plus', violence_ceiling: 'non_graphic' },
    schema_version: 1,
    created_at: now,
    updated_at: now
  }
}

function makePlaythrough(): PlaythroughRecord {
  return {
    id: FIXTURE_PLAYTHROUGH_ID,
    world_id: FIXTURE_WORLD_ID,
    player_character_id: 'fixture-player',
    root_branch_id: FIXTURE_ROOT_BRANCH_ID,
    active_branch_id: FIXTURE_ROOT_BRANCH_ID,
    provider_config_snapshot: { mode: 'fixture', source: 'browser-fixture' },
    world_clock_minutes: 8 * 60,
    rng_seed: 'fixture-seed',
    rng_state: {},
    lifecycle: 'active',
    schema_version: 1,
    created_at: now,
    updated_at: now
  }
}

function makeBranch(id: string, parentBranchId: string | null, forkTurnId: string | null, depth: number): BranchRecord {
  return {
    id,
    playthrough_id: FIXTURE_PLAYTHROUGH_ID,
    parent_branch_id: parentBranchId,
    fork_turn_id: forkTurnId,
    head_turn_id: forkTurnId,
    depth,
    head_revision: 0,
    lifecycle: 'active',
    created_at: now,
    updated_at: now
  }
}

export function createFixtureState(): FixtureState {
  return {
    world: makeWorld(),
    playthrough: makePlaythrough(),
    branches: [makeBranch(FIXTURE_ROOT_BRANCH_ID, null, null, 0)],
    turns: [],
    characters: [
      {
        id: 'fixture-player',
        world_id: FIXTURE_WORLD_ID,
        playthrough_id: FIXTURE_PLAYTHROUGH_ID,
        display_name: 'You',
        aliases: [],
        public_profile: { role: 'student', note: 'The player character' },
        schema_version: 1
      },
      {
        id: 'fixture-yuki',
        world_id: FIXTURE_WORLD_ID,
        playthrough_id: FIXTURE_PLAYTHROUGH_ID,
        display_name: 'Yuki Arai',
        aliases: ['Yuki'],
        public_profile: { role: 'class representative', trait: 'careful but kind' },
        schema_version: 1
      },
      {
        id: 'fixture-ren',
        world_id: FIXTURE_WORLD_ID,
        playthrough_id: FIXTURE_PLAYTHROUGH_ID,
        display_name: 'Ren Kisaragi',
        aliases: ['Ren'],
        public_profile: { role: 'track club captain', trait: 'direct and observant' },
        schema_version: 1
      }
    ]
  }
}

export function fixtureNarrative(input: string, turnNumber: number): string {
  const normalized = input.trim()
  const beats = [
    'The late bell fades, leaving a small pocket of quiet in the corridor.',
    'Yuki glances toward the windows as if weighing whether to say more.',
    'Ren taps a rhythm against the desk; the mood shifts, but no one steps away.',
    'A handwritten notice flutters loose from the club board and lands between you.',
    'The afternoon light turns the classroom floor silver for one breath.',
    'Someone remembers the promise made at the vending machines yesterday.',
    'The next choice feels less like a test and more like an invitation.',
    'A distant announcement gives the scene a gentle time limit.',
    'The three of you leave a little more honestly than you arrived.',
    'Moonlight catches on the academy gate as the day settles into memory.'
  ]
  return `${beats[(turnNumber - 1) % beats.length]}\n\nYour action — “${normalized}” — becomes part of the shared afternoon.`
}

export function appendFixtureTurn(state: FixtureState, input: string, branchId: string): TurnRecord {
  const branch = state.branches.find((item) => item.id === branchId)
  if (!branch) throw new Error(`Fixture branch ${branchId} does not exist.`)
  const localTurns = state.turns.filter((turn) => turn.branch_id === branchId)
  const parentTurnId = branch.head_turn_id
  const turnNumber = state.turns.length + 1
  const turn: TurnRecord = {
    id: `fixture-turn-${turnNumber}`,
    playthrough_id: FIXTURE_PLAYTHROUGH_ID,
    branch_id: branchId,
    parent_turn_id: parentTurnId,
    raw_input: input,
    normalized_input: input.trim(),
    base_revision: localTurns.length,
    status: 'completed',
    final_narrative: fixtureNarrative(input, turnNumber),
    approved_patch: { source: 'browser-fixture', turn: turnNumber },
    world_time_start: state.playthrough.world_clock_minutes,
    duration_minutes: 5,
    world_time_end: state.playthrough.world_clock_minutes + 5,
    turn_run_id: `fixture-run-${turnNumber}`,
    schema_version: 1,
    created_at: now,
    updated_at: now
  }
  state.turns.push(turn)
  branch.head_turn_id = turn.id
  branch.head_revision = localTurns.length + 1
  state.playthrough.world_clock_minutes = turn.world_time_end
  state.playthrough.active_branch_id = branchId
  state.playthrough.updated_at = now
  return turn
}

export function forkFixtureBranch(state: FixtureState, parentBranchId: string, forkTurnId: string): BranchRecord {
  const parent = state.branches.find((item) => item.id === parentBranchId)
  if (!parent || !state.turns.some((turn) => turn.id === forkTurnId && turn.branch_id === parentBranchId)) {
    throw new Error('Choose a turn that belongs to the current fixture branch before forking.')
  }
  const child = makeBranch(
    `fixture-branch-${state.branches.length}`,
    parentBranchId,
    forkTurnId,
    parent.depth + 1
  )
  state.branches.push(child)
  return child
}

export function serializeFixture(state: FixtureState): string {
  return JSON.stringify(state)
}

export function restoreFixture(value: string): FixtureState | null {
  try {
    const parsed = JSON.parse(value) as FixtureState
    if (parsed.playthrough?.id !== FIXTURE_PLAYTHROUGH_ID || !Array.isArray(parsed.branches)) return null
    return parsed
  } catch {
    return null
  }
}
