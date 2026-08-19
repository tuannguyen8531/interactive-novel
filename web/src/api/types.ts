export interface HealthResponse {
  status: 'ok'
  service: string
  version: string
}

export interface WorldRecord {
  id: string
  name: string
  premise: string
  genre: string
  tone: string
  canon_rules: Record<string, unknown>
  content_policy: Record<string, unknown>
  schema_version: number
  created_at: string
  updated_at: string
}

export interface PlaythroughRecord {
  id: string
  world_id: string
  player_character_id: string | null
  root_branch_id: string | null
  active_branch_id: string | null
  provider_config_snapshot: Record<string, unknown>
  world_clock_minutes: number
  rng_seed: string
  rng_state: Record<string, unknown>
  lifecycle: string
  schema_version: number
  created_at: string
  updated_at: string
}

export interface BranchRecord {
  id: string
  playthrough_id: string
  parent_branch_id: string | null
  fork_turn_id: string | null
  head_turn_id: string | null
  depth: number
  head_revision: number
  lifecycle: string
  created_at: string
  updated_at: string
}

export interface TurnRecord {
  id: string
  playthrough_id: string
  branch_id: string
  parent_turn_id: string | null
  raw_input: string
  normalized_input: string | null
  base_revision: number
  status: string
  final_narrative: string | null
  approved_patch: Record<string, unknown> | null
  world_time_start: number
  duration_minutes: number
  world_time_end: number
  turn_run_id: string
  schema_version: number
  created_at: string
  updated_at: string
}

export interface CharacterView {
  id: string
  world_id: string
  playthrough_id: string | null
  display_name: string
  aliases: string[]
  public_profile: Record<string, unknown>
  state?: Record<string, unknown> | null
  last_active_turn_id?: string | null
  schema_version: number
}

export interface MemoryView {
  memory_id: string
  kind: string
  owner_id: string
  branch_id: string
  turn_id: string
  world_time: number
  payload: Record<string, unknown>
  confidence: number | null
  source_id: string | null
}

export interface RelationshipView {
  relationship_id: string
  playthrough_id: string
  branch_id: string
  source_id: string
  target_id: string
  values: Record<string, number>
  schema_version: number
}

export interface TimelineEvent {
  event_id: string
  playthrough_id: string
  branch_id: string
  turn_id: string
  event_type: string
  world_time: number
  location_id: string | null
  actor_ids: string[]
  target_ids: string[]
  witness_ids: string[]
  payload: Record<string, unknown>
  salience: number
  emotional_intensity: number
}

export interface DerivedJobRecord {
  id: string
  idempotency_key: string
  job_type: string
  playthrough_id: string
  branch_id: string
  source_turn_id: string
  source_revision: number
  status: string
  error: string | null
  payload: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface PlaythroughExport {
  format_version: string
  exported_at: string
  world: WorldRecord
  playthrough: PlaythroughRecord
  branches: BranchRecord[]
  turns: TurnRecord[]
  characters: CharacterView[]
  events: TimelineEvent[]
  relationships: RelationshipView[]
  derived_jobs: DerivedJobRecord[]
  metadata: Record<string, unknown>
}

export type JobStatus =
  | 'queued'
  | 'running'
  | 'cancelling'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'interrupted'

export interface TurnJobView {
  idempotency_key: string
  turn_run_id: string
  playthrough_id: string
  branch_id: string
  status: JobStatus | string
  result: unknown
  error: Record<string, unknown> | null
  cancellation_requested: boolean
  job_id: string | null
  created_at: string
  updated_at: string
}

export interface JobEvent {
  id: string
  job_id: string
  turn_run_id: string
  event_type: string
  phase: string
  payload: Record<string, unknown>
  payload_version: string
  created_at: string
  terminal: boolean
}

export interface ProviderTarget {
  name: string
  provider: string
  model: string
  base_url: string | null
  api_key_env: string | null
  timeout_seconds: number
  max_retries: number
  backoff_base_seconds: number
  header_names: string[]
}

export interface ProviderRoute {
  primary_target: string
  fallback_targets: string[]
}

export interface ProviderSettings {
  schema_version: number
  mode: 'quality' | 'fast'
  allow_cloud: boolean
  targets: Record<string, ProviderTarget>
  role_routes: Record<string, ProviderRoute>
}

export interface ConnectivityResult {
  provider: string
  model: string
  reachable: boolean
  latency_ms: number
  status_code: number | null
  message: string | null
  request_id: string | null
}

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    details?: Record<string, unknown>
  }
}

export interface SseEvent {
  id: string | null
  event: string
  data: string
}
