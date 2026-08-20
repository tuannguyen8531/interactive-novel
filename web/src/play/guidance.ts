import type { CharacterView, PlaythroughRecord, TimelineEvent, TurnRecord, WorldRecord } from '@/api/types'

export interface PlayGuidance {
  locationName: string | null
  suggestedActions: string[]
}

const DEFAULT_ACTIONS = [
  'Look around and take in the scene.',
  'Introduce yourself to someone nearby.',
  'Ask what is happening.'
]

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

export function buildPlayGuidance(
  world: WorldRecord,
  player: CharacterView | null,
  timeline: TimelineEvent[]
): PlayGuidance {
  const openingEvent = timeline.find((event) => event.event_type === 'opening_scene')
  const seed = record(world.canon_rules.world_seed)
  const openingScene = record(openingEvent?.payload.scene_spec) ?? record(seed?.opening_scene)
  const actions = stringList(openingScene?.visible_actions)
  const locationId = stringValue(player?.state?.location_id) ?? openingEvent?.location_id ?? null
  const eventLocation = record(openingEvent?.payload.location)
  const seedLocations = Array.isArray(seed?.locations) ? seed.locations.map(record).filter(isRecord) : []
  const seedLocation = seedLocations.find((location) => stringValue(location.location_id) === locationId)
  const locationName = stringValue(eventLocation?.name) ?? stringValue(seedLocation?.name) ?? locationId

  return {
    locationName,
    suggestedActions: [...new Set(actions.length ? actions : DEFAULT_ACTIONS)].slice(0, 4)
  }
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
