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
const suppressNextFocusOpen = ref(false)
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

function handleFocus(): void {
  if (suppressNextFocusOpen.value) {
    suppressNextFocusOpen.value = false
    return
  }
  showOptions()
}

function focusInputWithoutOpening(): void {
  const target = input.value
  if (!target || document.activeElement === target) return
  suppressNextFocusOpen.value = true
  target.focus()
  suppressNextFocusOpen.value = false
}

function selectOption(option: ComboboxOption): void {
  emit('update:modelValue', option.value)
  query.value = ''
  open.value = false
  void nextTick(focusInputWithoutOpening)
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
      @focus="handleFocus"
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
          :class="{ highlighted: index === highlightedIndex, 'is-selected': option.value === modelValue }"
          @click="selectOption(option)"
        >
          <span>{{ option.label }}</span>
          <span v-if="option.value === modelValue" class="selected-check">✓</span>
        </button>
      </li>
      <li v-if="!filteredOptions.length" class="empty-options">No matching presets — keep typing to use a custom tone.</li>
    </ul>
  </div>
</template>

<style scoped>
.editable-combobox {
  position: relative;
  width: 100%;
  min-width: 0;
}

input {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  font: inherit;
  font-size: 0.92rem;
  padding: 0.65rem 2.4rem 0.65rem 0.9rem;
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-md);
  background: rgba(13, 16, 26, 0.85);
  color: #fff;
  transition: all 180ms ease;
}

input:focus {
  outline: none;
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25);
  background: rgba(18, 22, 34, 0.95);
}

input::placeholder {
  color: var(--muted-dark);
}

.combobox-toggle {
  position: absolute;
  top: 1px;
  right: 1px;
  width: 2.25rem;
  height: calc(100% - 2px);
  padding: 0;
  border: 0;
  border-left: 1px solid var(--border-subtle);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  background: transparent;
  color: var(--muted);
  box-shadow: none;
  font-size: 0.85rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 160ms ease;
}

.combobox-toggle:hover {
  transform: none;
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  box-shadow: none;
  filter: none;
}

.combobox-toggle:active {
  transform: none;
}

.combobox-options {
  position: absolute;
  z-index: 50;
  top: calc(100% + 0.4rem);
  right: 0;
  left: 0;
  max-height: 15rem;
  overflow-y: auto;
  margin: 0;
  padding: 0.35rem;
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: var(--radius-md);
  background: rgba(18, 22, 34, 0.96);
  backdrop-filter: blur(16px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.6), 0 0 16px rgba(99, 102, 241, 0.15);
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.combobox-options::-webkit-scrollbar {
  width: 4px;
}
.combobox-options::-webkit-scrollbar-track {
  background: transparent;
}
.combobox-options::-webkit-scrollbar-thumb {
  background: rgba(99, 102, 241, 0.25);
  border-radius: 9999px;
}

.combobox-options li {
  margin: 0;
  padding: 0;
  list-style: none;
}

.combobox-options button {
  width: 100%;
  padding: 0.55rem 0.75rem;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: #e2e8f0;
  font-size: 0.88rem;
  font-weight: 500;
  text-align: left;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: none;
  cursor: pointer;
  transition: all 140ms ease;
}

.combobox-options button:hover,
.combobox-options button.highlighted {
  transform: none;
  background: rgba(99, 102, 241, 0.18);
  color: #fff;
  border-color: rgba(99, 102, 241, 0.35);
  box-shadow: none;
  filter: none;
}

.combobox-options button.is-selected {
  background: rgba(99, 102, 241, 0.25);
  color: #fff;
  font-weight: 600;
  border-color: #6366f1;
}

.selected-check {
  font-size: 0.82rem;
  color: #a5b4fc;
  font-weight: 700;
}

.empty-options {
  padding: 0.65rem 0.75rem;
  color: var(--muted);
  font-size: 0.82rem;
  font-weight: 500;
  line-height: 1.4;
}
</style>
