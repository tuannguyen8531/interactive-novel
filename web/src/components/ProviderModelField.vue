<script setup lang="ts">
import { computed } from 'vue'
import { useProviderModels } from '@/composables/models'
import type { ProviderTarget } from '@/api/types'
import VnSelect from '@/components/vn/VnSelect.vue'

const props = defineProps<{
  target: ProviderTarget
  modelValue: string
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
}>()

const { models, loading, loadError, refresh } = useProviderModels(() => props.target)
const knownModel = computed(() => models.value.includes(props.modelValue))

const modelOptions = computed(() => {
  const list = models.value.map((m) => ({ value: m, label: m }))
  return [
    {
      value: '',
      label: loading.value
        ? 'Loading models…'
        : models.value.length
          ? '(custom / not listed)'
          : 'No models available',
    },
    ...list,
  ]
})

function selectModel(val: unknown): void {
  if (val) emit('update:modelValue', String(val))
}

function inputModel(event: Event): void {
  emit('update:modelValue', (event.target as HTMLInputElement).value)
}
</script>

<template>
  <div class="model-field">
    <VnSelect
      :model-value="knownModel ? modelValue : ''"
      :disabled="loading || !models.length"
      aria-label="Available models"
      :options="modelOptions"
      :placeholder="loading ? 'Loading models…' : models.length ? '(custom / not listed)' : 'No models available'"
      @change="selectModel"
    />
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

input {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  font: inherit;
  font-size: 0.9rem;
  padding: 0.65rem 0.85rem;
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-md);
  background: rgba(13, 16, 26, 0.85);
  color: #fff;
  transition: all 180ms ease;
}

select:focus,
input:focus {
  outline: none;
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25);
  background: rgba(18, 22, 34, 0.95);
}

input::placeholder {
  color: var(--muted-dark);
}

.model-field button {
  padding: 0.65rem 0.95rem;
  font-size: 0.82rem;
  white-space: nowrap;
}

.model-error {
  margin: 0.3rem 0 0;
  color: #f87171;
  font-size: 0.8rem;
}

@media (max-width: 700px) {
  .model-field {
    grid-template-columns: 1fr;
  }
}
</style>
