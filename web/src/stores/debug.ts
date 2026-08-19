import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { usePlaythroughStore } from './playthrough'
import { useTurnJobStore } from './turnJob'

export const useDebugStore = defineStore('debug', () => {
  const playthrough = usePlaythroughStore()
  const enabled = import.meta.env.DEV
  const inspector = ref<Record<string, unknown> | null>(null)
  const jobs = useTurnJobStore()
  const available = computed(() => enabled && playthrough.playthrough !== null)

  function refresh(): void {
    if (!enabled || !playthrough.playthrough || !playthrough.activeBranch) {
      inspector.value = null
      return
    }
    inspector.value = {
      scope: {
        playthrough_id: playthrough.playthrough.id,
        branch_id: playthrough.activeBranch.id,
        head_revision: playthrough.activeBranch.head_revision,
        world_time_minutes: playthrough.worldTime
      },
      canonical: {
        latest_turn_id: playthrough.latestTurn?.id ?? null,
        visible_turn_count: playthrough.visibleTurns.length,
        event_count: playthrough.timeline.length
      },
      active_events: jobs.events.map((event) => ({ id: event.id, type: event.event_type, phase: event.phase })),
      characters: playthrough.characters.map((character) => ({ id: character.id, name: character.display_name })),
      branches: playthrough.branches.map((branch) => ({
        id: branch.id,
        parent_branch_id: branch.parent_branch_id,
        head_revision: branch.head_revision
      })),
      fixture: playthrough.fixtureMode,
      note: 'Inspector is developer-only and contains public projection metadata.'
    }
  }

  return { enabled, available, inspector, refresh }
})
