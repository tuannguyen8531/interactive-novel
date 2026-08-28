import type {
  BranchRecord,
  CharacterView,
  PlaythroughRecord,
  StoryLanguage,
  TimelineEvent,
  TurnRecord,
  WorldRecord
} from '@/api/types'

export interface PlayGuidance {
  locationName: string | null
  sceneCues: string[]
  suggestedActions: PlayerMoveSuggestion[]
}

export interface PlayerMoveSuggestion {
  kind: 'Act' | 'Speak' | 'Observe' | 'Think'
  text: string
}

export function formatWorldTime(totalMinutes: number): string {
  const minutes = normalizedMinutes(totalMinutes)
  const day = Math.floor(minutes / (24 * 60)) + 1
  const minuteOfDay = minutes % (24 * 60)
  const hours = Math.floor(minuteOfDay / 60)
  const minute = minuteOfDay % 60
  return `Day ${day} · ${String(hours).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}

export function formatTurnDuration(totalMinutes: number): string {
  const minutes = normalizedMinutes(totalMinutes)
  if (minutes < 60) return `${minutes} min`

  const days = Math.floor(minutes / (24 * 60))
  const hours = Math.floor((minutes % (24 * 60)) / 60)
  const remainder = minutes % 60
  const parts: string[] = []
  if (days > 0) parts.push(`${days} ${days === 1 ? 'day' : 'days'}`)
  if (hours > 0) parts.push(`${hours} ${hours === 1 ? 'hr' : 'hrs'}`)
  if (remainder > 0) parts.push(`${remainder} min`)
  return parts.join(' ')
}

function normalizedMinutes(value: number): number {
  return Number.isFinite(value) ? Math.max(0, Math.floor(value)) : 0
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

export function turnMoveSuggestions(turn: TurnRecord): PlayerMoveSuggestion[] {
  const allowedKinds = new Set<PlayerMoveSuggestion['kind']>(['Act', 'Speak', 'Observe', 'Think'])
  const seenKinds = new Set<PlayerMoveSuggestion['kind']>()
  const suggestions: PlayerMoveSuggestion[] = []

  for (const candidate of turn.suggested_actions ?? []) {
    const kind = titleCaseKind(candidate.kind)
    const suggestionText = stringValue(candidate.text)
    if (!kind || !suggestionText || !allowedKinds.has(kind) || seenKinds.has(kind)) continue
    seenKinds.add(kind)
    suggestions.push({ kind, text: suggestionText })
  }

  return suggestions.slice(0, 4)
}

export function buildPlayGuidance(
  world: WorldRecord,
  player: CharacterView | null,
  timeline: TimelineEvent[],
  characters: CharacterView[] = []
): PlayGuidance {
  const openingEvent = timeline.find((event) => event.event_type === 'opening_scene')
  const seed = record(world.canon_rules.world_seed)
  const storyLanguage = normalizeStoryLanguage(world.canon_rules.story_language ?? seed?.story_language)
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
    suggestedActions: playerMoveSuggestions(locationName, otherCharacter?.display_name ?? null, storyLanguage)
  }
}

function playerMoveSuggestions(
  locationName: string | null,
  otherCharacterName: string | null,
  language: StoryLanguage
): PlayerMoveSuggestion[] {
  if (language === 'vi') {
    return [
      {
        kind: 'Act',
        text: otherCharacterName
          ? `Tôi bước đến chỗ ${otherCharacterName} và ngỏ lời giúp đỡ.`
          : 'Tôi bước lên phía trước và tìm hiểu chuyện gì đang xảy ra.'
      },
      {
        kind: 'Speak',
        text: otherCharacterName
          ? `“Tiếp theo chúng ta nên làm gì?” tôi hỏi ${otherCharacterName}.`
          : '“Có ai ở đây không?” tôi gọi lớn.'
      },
      {
        kind: 'Observe',
        text: locationName
          ? `Tôi dành một lúc quan sát ${locationName} để tìm điều gì đó quan trọng.`
          : 'Tôi dành một lúc quan sát xung quanh để tìm điều gì đó quan trọng.'
      },
      {
        kind: 'Think',
        text: 'Tôi dừng lại suy nghĩ về chuyện vừa xảy ra trước khi quyết định phải làm gì.'
      }
    ]
  }

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

function normalizeStoryLanguage(value: unknown): StoryLanguage {
  return value === 'vi' ? 'vi' : 'en'
}

function titleCaseKind(value: unknown): PlayerMoveSuggestion['kind'] | null {
  const kind = stringValue(value)
  if (!kind) return null
  const normalized = `${kind[0].toUpperCase()}${kind.slice(1).toLowerCase()}`
  return ['Act', 'Speak', 'Observe', 'Think'].includes(normalized)
    ? (normalized as PlayerMoveSuggestion['kind'])
    : null
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
