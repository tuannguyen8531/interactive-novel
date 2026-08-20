import { describe, expect, it } from 'vitest'
import type { BranchRecord, CharacterView, PlaythroughRecord, TimelineEvent, TurnRecord, WorldRecord } from '@/api/types'
import { branchDisplayName, branchProgressLabel, buildPlayGuidance, findPlayerCharacter, isOpeningTurn } from './guidance'

describe('play guidance', () => {
  it('identifies the controlled character instead of assuming the first character', () => {
    const characters = [{ id: 'npc' }, { id: 'hero' }] as CharacterView[]
    const playthrough = { player_character_id: 'hero' } as PlaythroughRecord

    expect(findPlayerCharacter(playthrough, characters)?.id).toBe('hero')
  })

  it('extracts the opening location and suggested actions from canonical event data', () => {
    const world = { canon_rules: {} } as WorldRecord
    const player = { id: 'hero', state: { location_id: 'library' } } as unknown as CharacterView
    const timeline = [
      {
        event_type: 'opening_scene',
        location_id: 'library',
        payload: {
          location: { location_id: 'library', name: 'Moonlit Library' },
          scene_spec: { visible_actions: ['Enter the library', 'Greet Alice'] }
        }
      } as unknown as TimelineEvent
    ]

    const characters = [
      { id: 'hero', display_name: 'Mina' },
      { id: 'alice', display_name: 'Alice' }
    ] as CharacterView[]
    timeline[0].actor_ids = ['hero', 'alice']

    expect(buildPlayGuidance(world, player, timeline, characters)).toEqual({
      locationName: 'Moonlit Library',
      sceneCues: ['Enter the library', 'Greet Alice'],
      suggestedActions: [
        { kind: 'Act', text: 'I walk over to Alice and offer to help.' },
        { kind: 'Speak', text: '“What should we do next?” I ask Alice.' },
        { kind: 'Observe', text: 'I take a moment to look around Moonlit Library for anything important.' },
        { kind: 'Think', text: 'I pause and think about what just happened before deciding what to do.' }
      ]
    })
  })

  it('returns editable move examples even when the scene has no NPC or location', () => {
    const world = { canon_rules: {} } as WorldRecord

    const result = buildPlayGuidance(world, null, [])

    expect(result.sceneCues).toEqual([])
    expect(result.suggestedActions.map((suggestion) => suggestion.kind)).toEqual(['Act', 'Speak', 'Observe', 'Think'])
    expect(result.suggestedActions[0].text).toContain('investigate')
  })

  it('recognizes builder setup as an opening scene rather than a player move', () => {
    const opening = { approved_patch: { source: 'world_builder_confirmation' } } as unknown as TurnRecord
    const action = { approved_patch: { source: 'turn_pipeline' } } as unknown as TurnRecord

    expect(isOpeningTurn(opening)).toBe(true)
    expect(isOpeningTurn(action)).toBe(false)
  })

  it('turns technical branch IDs and revisions into player-facing labels', () => {
    const main = { id: 'uuid-root', parent_branch_id: null, head_revision: 4 } as BranchRecord
    const firstFork = { id: 'uuid-a', parent_branch_id: main.id, head_revision: 0 } as BranchRecord
    const secondFork = { id: 'uuid-b', parent_branch_id: main.id, head_revision: 2 } as BranchRecord
    const branches = [main, firstFork, secondFork]

    expect(branchDisplayName(main, branches)).toBe('Main timeline')
    expect(branchDisplayName(firstFork, branches)).toBe('Fork 1')
    expect(branchDisplayName(secondFork, branches)).toBe('Fork 2')
    expect(branchProgressLabel(main)).toBe('3 moves')
    expect(branchProgressLabel(firstFork)).toBe('No moves yet')
    expect(branchProgressLabel(secondFork)).toBe('2 moves')
  })
})
