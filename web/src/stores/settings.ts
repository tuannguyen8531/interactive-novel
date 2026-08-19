import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { useProviderStore } from './provider'

export const useSettingsStore = defineStore('settings', () => {
  const provider = useProviderStore()
  const mode = ref<'quality' | 'fast'>('quality')
  const allowCloud = ref(false)
  const error = computed(() => provider.error)
  const loading = computed(() => provider.loading)

  async function load(): Promise<void> {
    await provider.load()
    if (provider.settings) {
      mode.value = provider.settings.mode
      allowCloud.value = provider.settings.allow_cloud
    }
  }

  async function save(): Promise<void> {
    await provider.save(mode.value, allowCloud.value)
  }

  async function testProvider(): Promise<void> {
    await provider.test()
  }

  return {
    mode,
    allowCloud,
    providerSettings: computed(() => provider.settings),
    connectivity: computed(() => provider.connectivity),
    loading,
    testing: computed(() => provider.testing),
    error,
    load,
    save,
    testProvider,
    addTarget: provider.addTarget,
    removeTarget: provider.removeTarget,
    changeProvider: provider.changeProvider,
    setPrimaryTarget: provider.setPrimaryTarget,
    toggleFallback: provider.toggleFallback
  }
})
