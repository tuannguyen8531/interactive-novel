import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { appendFixtureTurn, createFixtureState, FIXTURE_PLAYTHROUGH_ID, restoreFixture, serializeFixture } from '@/fixtures/fixture'
import { useBranchStore } from '@/stores/branch'
import { usePlaythroughStore } from '@/stores/playthrough'
import { useTurnJobStore } from '@/stores/turnJob'

describe('frontend fixture vertical slice', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('passes the 30-turn acceptance loop and keeps the visible branch transcript', async () => {
    const playthrough = usePlaythroughStore()
    const jobs = useTurnJobStore()
    await playthrough.open(FIXTURE_PLAYTHROUGH_ID)

    for (let index = 0; index < 30; index += 1) {
      await jobs.runFixture(
        {
          playthrough_id: FIXTURE_PLAYTHROUGH_ID,
          branch_id: playthrough.activeBranch!.id,
          raw_input: `fixture action ${index + 1}`,
          base_revision: playthrough.headRevision
        },
        () => playthrough.appendFixture(`fixture action ${index + 1}`)
      )
    }

    expect(playthrough.visibleTurns).toHaveLength(30)
    expect(playthrough.activeBranch?.head_revision).toBe(30)
    expect(playthrough.latestTurn?.final_narrative).toContain('fixture action 30')
    expect(jobs.current?.status).toBe('completed')
    expect(jobs.events.some((event) => event.event_type === 'writer_token')).toBe(true)
  })

  it('forks after a turn and keeps the two continuations separate', async () => {
    const playthrough = usePlaythroughStore()
    const branches = useBranchStore()
    await playthrough.open(FIXTURE_PLAYTHROUGH_ID)
    playthrough.appendFixture('first choice')
    playthrough.appendFixture('second choice')

    const forkTurnId = playthrough.visibleTurns[0].id
    await branches.fork(forkTurnId)
    const childId = playthrough.activeBranch!.id
    expect(childId).not.toBe('fixture-root')
    expect(playthrough.visibleTurns.map((turn) => turn.raw_input)).toEqual(['first choice'])

    playthrough.appendFixture('child choice')
    await branches.switchBranch('fixture-root')
    expect(playthrough.visibleTurns.map((turn) => turn.raw_input)).toEqual(['first choice', 'second choice'])
    await branches.switchBranch(childId)
    expect(playthrough.visibleTurns.map((turn) => turn.raw_input)).toEqual(['first choice', 'child choice'])
  })

  it('exposes cancellation as a recoverable terminal state', async () => {
    const playthrough = usePlaythroughStore()
    const jobs = useTurnJobStore()
    await playthrough.open(FIXTURE_PLAYTHROUGH_ID)
    const running = jobs.runFixture(
      {
        playthrough_id: FIXTURE_PLAYTHROUGH_ID,
        branch_id: playthrough.activeBranch!.id,
        raw_input: 'cancel me',
        base_revision: 0
      },
      () => playthrough.appendFixture('cancel me')
    )
    await jobs.cancel()
    const result = await running

    expect(result.status).toBe('cancelled')
    expect(playthrough.visibleTurns).toHaveLength(0)
    expect(jobs.error).toBeNull()
  })

  it('keeps a failed fixture turn retryable instead of leaving it running', async () => {
    const playthrough = usePlaythroughStore()
    const jobs = useTurnJobStore()
    await playthrough.open(FIXTURE_PLAYTHROUGH_ID)

    const result = await jobs.runFixture(
      {
        playthrough_id: FIXTURE_PLAYTHROUGH_ID,
        branch_id: playthrough.activeBranch!.id,
        raw_input: 'fail once',
        base_revision: 0
      },
      () => {
        throw new Error('fixture failure')
      }
    )

    expect(result.status).toBe('failed')
    expect(jobs.active).toBe(false)
    expect(jobs.error).toBe('fixture failure')
  })

  it('round-trips fixture state for reload persistence', () => {
    const state = createFixtureState()
    appendFixtureTurn(state, 'persisted action', 'fixture-root')

    const restored = restoreFixture(serializeFixture(state))

    expect(restored?.turns).toHaveLength(1)
    expect(restored?.branches[0].head_revision).toBe(1)
    expect(restored?.playthrough.active_branch_id).toBe('fixture-root')
  })
})
