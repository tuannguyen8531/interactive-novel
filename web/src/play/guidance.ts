import type { BranchRecord, CharacterView, PlaythroughRecord, TimelineEvent, TurnRecord, WorldRecord } from '@/api/types'

export interface PlayGuidance {
  locationName: string | null
  sceneCues: string[]
  suggestedActions: PlayerMoveSuggestion[]
}

export interface PlayerMoveSuggestion {
  kind: 'Act' | 'Speak' | 'Observe' | 'Think'
  text: string
}

export function findPlayerCharacter(
  playthrough: PlaythroughRecord | null,
  characters: CharacterView[]
): CharacterView | null {
  const playerId = playthrough?.player_character_id
  return playerId ? characters.find((character) => character.id === playerId) ?? null : null
}

export function isOpeningTurn(turn: TurnRecord): boolean {
  return turn.approved_patch?.source === 'world_builder_confirmation'
}

export function branchDisplayName(branch: BranchRecord, branches: BranchRecord[]): string {
  if (branch.parent_branch_id === null) return 'Main timeline'
  const forkIndex = branches.filter((candidate) => candidate.parent_branch_id !== null).findIndex((candidate) => candidate.id === branch.id)
  return forkIndex < 0 ? 'Fork' : `Fork ${forkIndex + 1}`
}

export function branchProgressLabel(branch: BranchRecord): string {
  const openingRevision = branch.parent_branch_id === null && branch.head_revision > 0 ? 1 : 0
  const moveCount = Math.max(0, branch.head_revision - openingRevision)
  if (moveCount === 0) return 'No moves yet'
  return `${moveCount} ${moveCount === 1 ? 'move' : 'moves'}`
}

export function buildPlayGuidance(
  world: WorldRecord,
  player: CharacterView | null,
  timeline: TimelineEvent[],
  characters: CharacterView[] = []
): PlayGuidance {
  const openingEvent = timeline.find((event) => event.event_type === 'opening_scene')
  const seed = record(world.canon_rules.world_seed)
  const openingScene = record(openingEvent?.payload.scene_spec) ?? record(seed?.opening_scene)
  const sceneCues = stringList(openingScene?.visible_actions)
  const locationId = stringValue(player?.state?.location_id) ?? openingEvent?.location_id ?? null
  const eventLocation = record(openingEvent?.payload.location)
  const seedLocations = Array.isArray(seed?.locations) ? seed.locations.map(record).filter(isRecord) : []
  const seedLocation = seedLocations.find((location) => stringValue(location.location_id) === locationId)
  const locationName = stringValue(eventLocation?.name) ?? stringValue(seedLocation?.name) ?? locationId
  const sceneParticipantIds = new Set([
    ...(openingEvent?.actor_ids ?? []),
    ...(openingEvent?.target_ids ?? []),
    ...(openingEvent?.witness_ids ?? []),
    ...Object.keys(record(openingScene?.participants) ?? {})
  ])
  const otherCharacter =
    characters.find((character) => character.id !== player?.id && sceneParticipantIds.has(character.id)) ??
    characters.find((character) => character.id !== player?.id) ??
    null

  return {
    locationName,
    sceneCues: [...new Set(sceneCues)].slice(0, 4),
    suggestedActions: playerMoveSuggestions(locationName, otherCharacter?.display_name ?? null)
  }
}

function playerMoveSuggestions(locationName: string | null, otherCharacterName: string | null): PlayerMoveSuggestion[] {
  return [
    {
      kind: 'Act',
      text: otherCharacterName
        ? `I walk over to ${otherCharacterName} and offer to help.`
        : 'I step forward and investigate what is happening.'
    },
    {
      kind: 'Speak',
      text: otherCharacterName
        ? `“What should we do next?” I ask ${otherCharacterName}.`
        : '“Is anyone here?” I call out.'
    },
    {
      kind: 'Observe',
      text: locationName
        ? `I take a moment to look around ${locationName} for anything important.`
        : 'I take a moment to look around for anything important.'
    },
    {
      kind: 'Think',
      text: 'I pause and think about what just happened before deciding what to do.'
    }
  ]
}

function record(value: unknown): Record<string, unknown> | null {
  return isRecord(value) ? value : null
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function stringValue(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.map(stringValue).filter((item): item is string => item !== null)
}
