<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

export interface ComboboxOption {
  value: string
  label: string
}

const props = defineProps<{
  modelValue: string
  options: ComboboxOption[]
  label: string
  placeholder?: string
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
}>()

const root = ref<HTMLElement | null>(null)
const input = ref<HTMLInputElement | null>(null)
const open = ref(false)
const query = ref('')
const highlightedIndex = ref(-1)
const listboxId = `editable-combobox-${Math.random().toString(36).slice(2)}`

const filteredOptions = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase()
  if (!needle) return props.options
  return props.options.filter((option) =>
    `${option.label} ${option.value}`.toLocaleLowerCase().includes(needle)
  )
})

function showOptions(filter = ''): void {
  query.value = filter
  highlightedIndex.value = -1
  open.value = true
}

function toggleOptions(): void {
  if (open.value) {
    open.value = false
    return
  }
  showOptions()
  void nextTick(() => input.value?.focus())
}

function updateValue(event: Event): void {
  const value = (event.target as HTMLInputElement).value
  emit('update:modelValue', value)
  showOptions(value)
}

function selectOption(option: ComboboxOption): void {
  emit('update:modelValue', option.value)
  query.value = ''
  open.value = false
  void nextTick(() => input.value?.focus())
}

function moveHighlight(offset: number): void {
  if (!open.value) showOptions()
  const count = filteredOptions.value.length
  if (!count) return
  if (highlightedIndex.value < 0) {
    highlightedIndex.value = offset > 0 ? 0 : count - 1
    return
  }
  highlightedIndex.value = (highlightedIndex.value + offset + count) % count
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    moveHighlight(1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    moveHighlight(-1)
  } else if (event.key === 'Enter' && open.value) {
    const option = filteredOptions.value[highlightedIndex.value]
    if (option) {
      event.preventDefault()
      selectOption(option)
    }
  } else if (event.key === 'Escape') {
    open.value = false
  }
}

function closeWhenOutside(event: PointerEvent): void {
  if (root.value && !root.value.contains(event.target as Node)) open.value = false
}

onMounted(() => document.addEventListener('pointerdown', closeWhenOutside))
onBeforeUnmount(() => document.removeEventListener('pointerdown', closeWhenOutside))
</script>

<template>
  <div ref="root" class="editable-combobox">
    <input
      ref="input"
      type="text"
      autocomplete="off"
      :value="modelValue"
      :placeholder="placeholder"
      role="combobox"
      aria-autocomplete="list"
      :aria-label="label"
      :aria-controls="listboxId"
      :aria-expanded="open"
      @focus="showOptions()"
      @input="updateValue"
      @keydown="handleKeydown"
    />
    <button
      class="combobox-toggle"
      type="button"
      :aria-label="`Show ${label.toLocaleLowerCase()} options`"
      :aria-expanded="open"
      @click="toggleOptions"
    >
      ▾
    </button>
    <ul v-if="open" :id="listboxId" class="combobox-options" role="listbox">
      <li v-for="(option, index) in filteredOptions" :key="option.value" role="presentation">
        <button
          type="button"
          role="option"
          :aria-selected="option.value === modelValue"
          :class="{ highlighted: index === highlightedIndex }"
          @click="selectOption(option)"
        >
          {{ option.label }}
        </button>
      </li>
      <li v-if="!filteredOptions.length" class="empty-options">No matching presets — keep typing to use a custom tone.</li>
    </ul>
  </div>
</template>

<style scoped>
.editable-combobox {
  position: relative;
  min-width: 0;
}

input {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  padding: 0.7rem 2.4rem 0.7rem 0.7rem;
  border: 1px solid var(--line);
  border-radius: 0.55rem;
  background: #fff;
  color: var(--ink);
}

.combobox-toggle {
  position: absolute;
  top: 1px;
  right: 1px;
  width: 2.25rem;
  height: calc(100% - 2px);
  padding: 0;
  border: 0;
  border-left: 1px solid var(--line);
  border-radius: 0 0.5rem 0.5rem 0;
  background: transparent;
  color: var(--muted);
}

.combobox-toggle:hover {
  transform: none;
  background: var(--accent-soft);
}

.combobox-options {
  position: absolute;
  z-index: 20;
  top: calc(100% + 0.35rem);
  right: 0;
  left: 0;
  max-height: 14rem;
  overflow-y: auto;
  margin: 0;
  padding: 0.3rem;
  border: 1px solid var(--line);
  border-radius: 0.55rem;
  background: #fff;
  box-shadow: 0 0.75rem 1.8rem rgb(31 35 48 / 14%);
  list-style: none;
}

.combobox-options button {
  width: 100%;
  padding: 0.55rem 0.65rem;
  border: 0;
  border-radius: 0.4rem;
  background: transparent;
  color: var(--ink);
  text-align: left;
}

.combobox-options button:hover,
.combobox-options button.highlighted {
  transform: none;
  background: var(--accent-soft);
}

.empty-options {
  padding: 0.55rem 0.65rem;
  color: var(--muted);
  font-size: 0.78rem;
  font-weight: 500;
  line-height: 1.4;
}
</style>
