import { describe, expect, it } from 'vitest'
import type { CharacterView, PlaythroughRecord, TimelineEvent, TurnRecord, WorldRecord } from '@/api/types'
import { buildPlayGuidance, findPlayerCharacter, isOpeningTurn } from './guidance'

describe('play guidance', () => {
  it('identifies the controlled character instead of assuming the first character', () => {
    const characters = [{ id: 'npc' }, { id: 'hero' }] as CharacterView[]
    const playthrough = { player_character_id: 'hero' } as PlaythroughRecord

    expect(findPlayerCharacter(playthrough, characters)?.id).toBe('hero')
  })

  it('extracts the opening location and suggested actions from canonical event data', () => {
    const world = { canon_rules: {} } as WorldRecord
    const player = { state: { location_id: 'library' } } as unknown as CharacterView
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

    expect(buildPlayGuidance(world, player, timeline)).toEqual({
      locationName: 'Moonlit Library',
      suggestedActions: ['Enter the library', 'Greet Alice']
    })
  })

  it('recognizes builder setup as an opening scene rather than a player move', () => {
    const opening = { approved_patch: { source: 'world_builder_confirmation' } } as unknown as TurnRecord
    const action = { approved_patch: { source: 'turn_pipeline' } } as unknown as TurnRecord

    expect(isOpeningTurn(opening)).toBe(true)
    expect(isOpeningTurn(action)).toBe(false)
  })
})
