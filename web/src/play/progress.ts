import type { JobEvent } from '@/api/types'

const TURN_PHASES = [
  'normalize_input',
  'build_initial_context',
  'plan',
  'simulate',
  'extract_claims',
  'retrieve_targeted_evidence',
  'validate_context',
  'guard_state',
  'repair',
  'write',
  'critique',
  'revise',
  'build_canonical_records',
  'commit',
  'enqueue_derived_jobs'
] as const

export function displayTemplate(value: string | null | undefined): string {
  return (value?.trim() || 'Story').replaceAll('_', ' ').replaceAll('-', ' ').replace(/\s+/g, ' ').toUpperCase()
}

export function capitalizeStatus(value: string): string {
  const normalized = value.trim()
  return normalized ? normalized.charAt(0).toUpperCase() + normalized.slice(1) : ''
}

export function turnProgressPercent(events: JobEvent[], status: string | undefined, loading: boolean): number {
  if (status === 'completed') return 100

  let completedPhases = 0
  for (const event of events) {
    const phaseIndex = TURN_PHASES.indexOf(event.phase as (typeof TURN_PHASES)[number])
    if (phaseIndex < 0) continue
    completedPhases = Math.max(completedPhases, phaseIndex + (event.event_type.endsWith('_completed') ? 1 : 0))
  }

  const measured = Math.round((completedPhases / TURN_PHASES.length) * 100)
  return loading || status ? Math.max(3, measured) : measured
}
