export type ContentRating = 'teen_14_plus' | 'mature_16_plus' | 'adult_18_plus'
export type ViolenceCeiling = 'none' | 'restrained' | 'detailed'
export type BinaryGender = 'male' | 'female'

export interface StoryTemplateDefaults {
  tone: string
  rating: ContentRating
  violence_ceiling: ViolenceCeiling
}

export interface NarrativeProfile {
  primary_focus: string
  romance_priority: string
  relationship_pacing: string
}

export interface HealthResponse {
  status: 'ok'
  service: string
  version: string
}

export interface StoryTemplate {
  id: string
  name: string
  description: string
  genre: string
  prompt_instructions: string
  defaults: StoryTemplateDefaults
  narrative_profile: NarrativeProfile
  opening_guidance: string[]
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

export interface WorldContentBoundaries {
  rating: ContentRating | string
  topic_boundaries: Record<string, 'allow' | 'opt_in' | 'excluded' | string>
  violence_ceiling: ViolenceCeiling | string
  adult_explicit_opt_in: boolean
}

export interface WorldCharacterSeed {
  character_id: string
  name: string
  aliases: string[]
  age: number
  gender: BinaryGender
  role: string
  background: string
  voice: string
  traits: string[]
  values: string[]
  goal_ids: string[]
  private_claim_ids: string[]
}

export interface WorldClaimProposal {
  proposal_id: string
  subject_id: string
  predicate: string
  object_id: string | null
  typed_value: unknown
  polarity: string
  qualifiers: Record<string, unknown>
  valid_time: { start: number; end: number | null }
  branch_scope: string
}

export interface WorldBeliefProposal {
  belief_id: string
  believer_id: string
  claim_id: string
  stance: 'supports' | 'rejects' | 'uncertain' | string
  confidence: number
  evidence_ids: string[]
  counter_evidence_ids: string[]
  branch_scope: string
  world_time: number
  source_reliability: number
}

export interface WorldSceneSpec {
  scene_id: string
  source_role: string
  source_run_id: string
  guard_approved: boolean
  world_time: number
  tags: string[]
  participants: Record<string, number>
  consent: Record<string, string>
  violence_detail?: ViolenceCeiling | string
  approved_beats: string[]
  visible_actions: string[]
  allowed_dialogue_intents: string[]
  pov: string
  tone: string
  continuity_details: string[]
  allowed_claims: Array<{ claim_id?: string; fingerprint?: string }>
  forbidden_claims: Array<{ claim_id?: string; fingerprint?: string }>
  length_target: number
}

export interface WorldSeed {
  schema_version: 'world-seed' | string
  role: 'world_builder' | string
  run_id: string
  prompt_version: string
  physical_call_id: string | null
  config_snapshot_id?: string | null
  template_id?: string
  title: string
  premise: string
  genre: string
  tone: string
  content_boundaries: WorldContentBoundaries
  locations: Array<{ location_id: string; name: string; description: string }>
  player_character: WorldCharacterSeed
  npc_profiles: WorldCharacterSeed[]
  initial_claims: WorldClaimProposal[]
  initial_relationships: Array<{ source_id: string; target_id: string; values: Record<string, number> }>
  initial_beliefs: WorldBeliefProposal[]
  goals: Array<{ goal_id: string; owner_id: string; description: string; priority: number }>
  tensions: Array<{
    tension_id: string
    observer_id: string
    rival_id: string
    focus_id: string
    appraisal: string
  }>
  threads: Array<{ thread_id: string; premise: string; participant_ids: string[]; stakes: string }>
  opening_scene: WorldSceneSpec
}

export interface WorldConfirmation {
  world: WorldRecord
  playthrough: PlaythroughRecord
  branch: BranchRecord
  opening_scene: WorldSceneSpec
  opening_turn: TurnRecord
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
  suggested_actions?: Array<{
    kind: string
    text: string
  }>
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
  provider: 'ollama' | 'gemini' | 'openrouter'
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

export interface ProviderModelsResponse {
  provider: ProviderTarget['provider']
  models: string[]
}

export interface OllamaAccount {
  signed_in: boolean
  username: string | null
  detail: string | null
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

export interface BackupRecord {
  name: string
  size_bytes: number
  modified_at: string
  integrity: { path: string; ok: boolean; message: string }
}

export interface BackupReport {
  source_path: string
  destination_path: string
  size_bytes: number
  sha256: string
  integrity: { path: string; ok: boolean; message: string }
}

export interface InspectorPayload {
  [key: string]: unknown
  scope: Record<string, unknown>
  state: Record<string, unknown> | null
  characters: CharacterView[]
  memory: Record<string, MemoryView[]>
  relationships: RelationshipView[]
  retrieval_traces: Array<Record<string, unknown>>
  invariants: Record<string, unknown>
  llm_traces: Array<Record<string, unknown>>
  telemetry: Record<string, unknown>
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
