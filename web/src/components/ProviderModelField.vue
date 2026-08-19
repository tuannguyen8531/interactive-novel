<script setup lang="ts">
import { computed } from 'vue'
import { useProviderModels } from '@/composables/models'
import type { ProviderTarget } from '@/api/types'

const props = defineProps<{
  target: ProviderTarget
  modelValue: string
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
}>()

const { models, loading, loadError, refresh } = useProviderModels(() => props.target)
const knownModel = computed(() => models.value.includes(props.modelValue))

function selectModel(event: Event): void {
  const value = (event.target as HTMLSelectElement).value
  if (value) emit('update:modelValue', value)
}

function inputModel(event: Event): void {
  emit('update:modelValue', (event.target as HTMLInputElement).value)
}
</script>

<template>
  <div class="model-field">
    <select
      :value="knownModel ? modelValue : ''"
      :disabled="loading || !models.length"
      aria-label="Available models"
      @change="selectModel"
    >
      <option value="">
        {{ loading ? 'Loading models…' : models.length ? '(custom / not listed)' : 'No models available' }}
      </option>
      <option v-for="model in models" :key="model" :value="model">{{ model }}</option>
    </select>
    <input
      type="text"
      :value="modelValue"
      :placeholder="knownModel ? 'Selected from list — type to override' : 'Type model ID, or pick from the list'"
      required
      autocomplete="off"
      @input="inputModel"
    />
    <button class="secondary" type="button" :disabled="loading" @click="refresh">
      {{ loading ? 'Refreshing…' : 'Refresh' }}
    </button>
  </div>
  <p v-if="loadError" class="model-error">{{ loadError }}</p>
</template>

<style scoped>
.model-field {
  display: grid;
  grid-template-columns: minmax(10rem, 0.8fr) minmax(12rem, 1fr) auto;
  gap: 0.5rem;
  align-items: center;
}

select,
input {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  padding: 0.7rem;
  border: 1px solid var(--line);
  border-radius: 0.55rem;
  background: #fff;
  color: var(--ink);
}

.model-error {
  margin: 0.3rem 0 0;
  color: #a33f48;
  font-size: 0.8rem;
}

@media (max-width: 700px) {
  .model-field {
    grid-template-columns: 1fr;
  }
}
</style>
