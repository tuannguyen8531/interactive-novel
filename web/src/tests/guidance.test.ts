import { describe, expect, it } from 'vitest'
import type { BranchRecord, CharacterView, PlaythroughRecord, TimelineEvent, TurnRecord, WorldRecord } from '@/api/types'
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

describe('play guidance', () => {
  it('formats the in-world clock as a readable day and time', () => {
    expect(formatWorldTime(0)).toBe('Day 1 · 00:00')
    expect(formatWorldTime(480)).toBe('Day 1 · 08:00')
    expect(formatWorldTime(930)).toBe('Day 1 · 15:30')
    expect(formatWorldTime(1530)).toBe('Day 2 · 01:30')
    expect(formatWorldTime(1505)).toBe('Day 2 · 01:05')
    expect(formatWorldTime(Number.NaN)).toBe('Day 1 · 00:00')
  })

  it('formats turn duration without exposing raw accumulated minutes', () => {
    expect(formatTurnDuration(5)).toBe('5 min')
    expect(formatTurnDuration(75)).toBe('1 hr 15 min')
    expect(formatTurnDuration(1500)).toBe('1 day 1 hr')
  })

  it('identifies the controlled character instead of assuming the first character', () => {
    const characters = [{ id: 'npc', role: 'npc' }, { id: 'hero', role: 'player' }] as CharacterView[]
    const playthrough = { player_character_id: 'hero' } as PlaythroughRecord

    expect(findPlayerCharacter(playthrough, characters)?.id).toBe('hero')
  })

  it('falls back to role=player when player_character_id is missing', () => {
    const characters = [{ id: 'npc', role: 'npc' }, { id: 'hero', role: 'player' }] as CharacterView[]
    const playthrough = { player_character_id: null } as unknown as PlaythroughRecord

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

  it('localizes opening move examples from the canonical world language', () => {
    const world = { canon_rules: { story_language: 'vi' } } as unknown as WorldRecord
    const player = { id: 'hero', state: { location_id: 'thu_vien' } } as unknown as CharacterView
    const timeline = [
      {
        event_type: 'opening_scene',
        location_id: 'thu_vien',
        actor_ids: ['hero', 'minh'],
        payload: { location: { name: 'Thư viện' }, scene_spec: { visible_actions: [] } }
      } as unknown as TimelineEvent
    ]
    const characters = [
      { id: 'hero', display_name: 'Lan' },
      { id: 'minh', display_name: 'Minh' }
    ] as CharacterView[]

    expect(buildPlayGuidance(world, player, timeline, characters).suggestedActions).toEqual([
      { kind: 'Act', text: 'Tôi bước đến chỗ Minh và ngỏ lời giúp đỡ.' },
      { kind: 'Speak', text: '“Tiếp theo chúng ta nên làm gì?” tôi hỏi Minh.' },
      { kind: 'Observe', text: 'Tôi dành một lúc quan sát Thư viện để tìm điều gì đó quan trọng.' },
      { kind: 'Think', text: 'Tôi dừng lại suy nghĩ về chuyện vừa xảy ra trước khi quyết định phải làm gì.' }
    ])
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

describe('turnMoveSuggestions', () => {
  it('normalizes valid LLM suggestions and ignores duplicate or malformed entries', () => {
    const turn = {
      suggested_actions: [
        { kind: 'act', text: '  I open the old cabinet.  ' },
        { kind: 'SPEAK', text: '“Did you hear that?” I ask Hana.' },
        { kind: 'act', text: 'Duplicate act' },
        { kind: 'predict', text: 'I decide what Hana does.' },
        { kind: 'think', text: '' }
      ]
    } as TurnRecord

    expect(turnMoveSuggestions(turn)).toEqual([
      { kind: 'Act', text: 'I open the old cabinet.' },
      { kind: 'Speak', text: '“Did you hear that?” I ask Hana.' }
    ])
  })
})
