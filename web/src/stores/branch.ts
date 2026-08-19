import { computed } from 'vue'
import { defineStore } from 'pinia'
import { usePlaythroughStore } from './playthrough'

export const useBranchStore = defineStore('branch', () => {
  const playthrough = usePlaythroughStore()
  const branches = computed(() => playthrough.branches)
  const activeBranch = computed(() => playthrough.activeBranch)
  const activeBranchId = computed(() => playthrough.selectedBranchId)
  const loading = computed(() => playthrough.loading)
  const error = computed(() => playthrough.error)

  async function switchBranch(branchId: string): Promise<void> {
    await playthrough.switchBranch(branchId)
  }

  async function fork(forkTurnId: string): Promise<void> {
    await playthrough.fork(forkTurnId)
  }

  return { branches, activeBranch, activeBranchId, loading, error, switchBranch, fork }
})
