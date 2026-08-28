import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { useProviderStore } from './provider'
import type { StoryLanguage } from '@/api/types'

export const useSettingsStore = defineStore('settings', () => {
  const provider = useProviderStore()
  const mode = ref<'quality' | 'fast'>('quality')
  const allowCloud = ref(false)
  const storyLanguage = ref<StoryLanguage>('en')
  const error = computed(() => provider.error)
  const loading = computed(() => provider.loading)

  async function load(): Promise<void> {
    await provider.load()
    if (provider.settings) {
      mode.value = provider.settings.mode
      allowCloud.value = provider.settings.allow_cloud
      storyLanguage.value = provider.settings.story_language ?? 'en'
    }
  }

  async function save(): Promise<void> {
    await provider.save(mode.value, allowCloud.value, storyLanguage.value)
  }

  async function testProvider(): Promise<void> {
    await provider.test()
  }

  return {
    mode,
    allowCloud,
    storyLanguage,
    providerSettings: computed(() => provider.settings),
    connectivity: computed(() => provider.connectivity),
    ollamaAccount: computed(() => provider.ollamaAccount),
    ollamaAccountLoading: computed(() => provider.ollamaAccountLoading),
    loading,
    testing: computed(() => provider.testing),
    error,
    load,
    save,
    testProvider,
    loadOllamaAccount: provider.loadOllamaAccount,
    addTarget: provider.addTarget,
    removeTarget: provider.removeTarget,
    renameTarget: provider.renameTarget,
    changeProvider: provider.changeProvider,
    setPrimaryTarget: provider.setPrimaryTarget,
    toggleFallback: provider.toggleFallback
  }
})
