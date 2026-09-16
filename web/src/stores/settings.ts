import { computed, ref } from 'vue'
import { api } from '@/api/client'
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

  async function savePreset(name: string): Promise<string[]> {
    return api.saveSettingsPreset(name, provider.draftPayload(mode.value, allowCloud.value, storyLanguage.value))
  }

  async function applyPreset(name: string): Promise<void> {
    const applied = await api.applySettingsPreset(name)
    provider.settings = applied
    provider.connectivity = []
    provider.error = null
    mode.value = applied.mode
    allowCloud.value = applied.allow_cloud
    storyLanguage.value = applied.story_language ?? 'en'
  }

  async function testProvider(): Promise<void> {
    await provider.test()
  }

  return {
    savePreset,
    applyPreset,
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
