import { describe, expect, it } from 'vitest'
import type { JobEvent } from '@/api/types'
import { capitalizeStatus, displayTemplate, turnProgressPercent } from '@/play/progress'

function event(phase: string, eventType: string): JobEvent {
  return {
    id: `${phase}-${eventType}`,
    job_id: 'job-1',
    turn_run_id: 'run-1',
    event_type: eventType,
    phase,
    payload: {},
    payload_version: '1',
    created_at: '2026-01-01T00:00:00Z',
    terminal: false
  }
}

describe('play presentation helpers', () => {
  it('presents underscored template names in uppercase words', () => {
    expect(displayTemplate('fantasy_adventure')).toBe('FANTASY ADVENTURE')
  })

  it('capitalizes only the beginning of a status label', () => {
    expect(capitalizeStatus('writer is preparing the next scene.')).toBe('Writer is preparing the next scene.')
  })

  it('advances as pipeline phases complete and finishes at 100 percent', () => {
    expect(turnProgressPercent([], 'running', true)).toBe(3)
    expect(turnProgressPercent([event('plan', 'planner_completed')], 'running', true)).toBe(20)
    expect(turnProgressPercent([event('write', 'writer_completed')], 'running', true)).toBe(67)
    expect(turnProgressPercent([], 'completed', false)).toBe(100)
  })
})
