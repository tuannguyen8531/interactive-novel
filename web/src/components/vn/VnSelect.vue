<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

export interface VnSelectOption {
  value: string | number
  label?: string
  tag?: string
  hint?: string
  disabled?: boolean
}

const props = withDefaults(
  defineProps<{
    modelValue?: string | number | (string | number)[] | null
    options: (string | number | VnSelectOption)[]
    placeholder?: string
    disabled?: boolean
    multiple?: boolean
    ariaLabel?: string
    id?: string
    summaryFormat?: ((selected: VnSelectOption[]) => string) | null
  }>(),
  {
    modelValue: null,
    placeholder: 'Select an option',
    disabled: false,
    multiple: false,
    ariaLabel: undefined,
    id: undefined,
    summaryFormat: null,
  }
)

const emit = defineEmits<{
  (event: 'update:modelValue', value: any): void
  (event: 'change', value: any): void
  (event: 'toggleOption', option: VnSelectOption, isSelected: boolean): void
}>()

const root = ref<HTMLElement | null>(null)
const trigger = ref<HTMLButtonElement | null>(null)
const open = ref(false)
const highlightedIndex = ref(-1)

const normalizedOptions = computed<VnSelectOption[]>(() => {
  return props.options.map((opt) => {
    if (typeof opt === 'string' || typeof opt === 'number') {
      return { value: opt, label: String(opt) }
    }
    return {
      value: opt.value,
      label: opt.label !== undefined ? opt.label : String(opt.value),
      tag: opt.tag,
      hint: opt.hint,
      disabled: opt.disabled,
    }
  })
})

function isSelected(val: string | number): boolean {
  if (props.multiple) {
    return Array.isArray(props.modelValue) && props.modelValue.includes(val)
  }
  return props.modelValue === val
}

const selectedOption = computed(() => {
  if (props.multiple) return null
  return normalizedOptions.value.find((opt) => opt.value === props.modelValue) || null
})

const selectedOptionsList = computed(() => {
  if (!props.multiple || !Array.isArray(props.modelValue)) return []
  const currentValues = props.modelValue
  return normalizedOptions.value.filter((opt) => currentValues.includes(opt.value))
})

const displayText = computed(() => {
  if (props.multiple) {
    const selected = selectedOptionsList.value
    if (props.summaryFormat) {
      return props.summaryFormat(selected)
    }
    if (selected.length === 0) {
      return props.placeholder || 'None selected'
    }
    if (selected.length === 1) {
      return selected[0].label || String(selected[0].value)
    }
    return `${selected.length} selected`
  }

  if (selectedOption.value) {
    return selectedOption.value.label || String(selectedOption.value.value)
  }
  return props.placeholder || 'Select an option'
})

const displayTag = computed(() => {
  if (!props.multiple && selectedOption.value?.tag) {
    return selectedOption.value.tag
  }
  return null
})

function toggleMenu(): void {
  if (props.disabled) return
  open.value = !open.value
  if (open.value) {
    const idx = normalizedOptions.value.findIndex((opt) => isSelected(opt.value))
    highlightedIndex.value = idx >= 0 ? idx : 0
  }
}

function handleSelect(option: VnSelectOption): void {
  if (option.disabled || props.disabled) return

  if (props.multiple) {
    const current = Array.isArray(props.modelValue) ? [...props.modelValue] : []
    const idx = current.indexOf(option.value)
    let willBeSelected = false
    if (idx >= 0) {
      current.splice(idx, 1)
      willBeSelected = false
    } else {
      current.push(option.value)
      willBeSelected = true
    }
    emit('update:modelValue', current)
    emit('change', current)
    emit('toggleOption', option, willBeSelected)
  } else {
    emit('update:modelValue', option.value)
    emit('change', option.value)
    open.value = false
    void nextTick(() => {
      trigger.value?.focus()
    })
  }
}

function handleKeydown(event: KeyboardEvent): void {
  if (props.disabled) return

  if (event.key === 'ArrowDown') {
    event.preventDefault()
    if (!open.value) {
      open.value = true
      highlightedIndex.value = 0
    } else {
      highlightedIndex.value = (highlightedIndex.value + 1) % normalizedOptions.value.length
    }
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    if (!open.value) {
      open.value = true
      highlightedIndex.value = normalizedOptions.value.length - 1
    } else {
      highlightedIndex.value =
        (highlightedIndex.value - 1 + normalizedOptions.value.length) %
        normalizedOptions.value.length
    }
  } else if (event.key === 'Enter' || event.key === ' ') {
    if (!open.value) {
      event.preventDefault()
      toggleMenu()
    } else if (highlightedIndex.value >= 0 && highlightedIndex.value < normalizedOptions.value.length) {
      event.preventDefault()
      handleSelect(normalizedOptions.value[highlightedIndex.value]!)
    }
  } else if (event.key === 'Escape') {
    if (open.value) {
      event.preventDefault()
      open.value = false
    }
  }
}

function closeWhenOutside(event: PointerEvent): void {
  if (root.value && !root.value.contains(event.target as Node)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('pointerdown', closeWhenOutside))
onBeforeUnmount(() => document.removeEventListener('pointerdown', closeWhenOutside))
</script>

<template>
  <div
    ref="root"
    class="vn-select"
    :class="{
      'is-open': open,
      'is-disabled': disabled,
      'has-selected': Boolean(selectedOption || selectedOptionsList.length),
    }"
    :id="id"
  >
    <button
      ref="trigger"
      type="button"
      class="vn-select-trigger"
      :disabled="disabled"
      :aria-label="ariaLabel"
      :aria-expanded="open"
      aria-haspopup="listbox"
      @click="toggleMenu"
      @keydown="handleKeydown"
    >
      <div class="vn-select-content">
        <slot
          name="selected"
          :selected="selectedOption"
          :selected-list="selectedOptionsList"
          :display-text="displayText"
        >
          <span
            class="vn-select-text"
            :class="{ 'is-placeholder': !selectedOption && !selectedOptionsList.length }"
          >
            {{ displayText }}
          </span>
          <span v-if="displayTag" class="vn-select-tag">({{ displayTag }})</span>
        </slot>
      </div>
      <span class="vn-select-arrow" aria-hidden="true">▾</span>
    </button>

    <div
      v-if="open"
      class="vn-select-menu"
      role="listbox"
      :aria-multiselectable="multiple"
    >
      <template v-if="normalizedOptions.length > 0">
        <div
          v-for="(option, index) in normalizedOptions"
          :key="option.value"
          role="option"
          class="vn-select-option"
          :class="{
            'is-selected': isSelected(option.value),
            'is-highlighted': index === highlightedIndex,
            'is-disabled': option.disabled,
          }"
          :aria-selected="isSelected(option.value)"
          @click="handleSelect(option)"
        >
          <slot name="option" :option="option" :is-selected="isSelected(option.value)">
            <div class="vn-select-option-left">
              <input
                v-if="multiple"
                type="checkbox"
                class="vn-select-checkbox"
                :checked="isSelected(option.value)"
                :disabled="option.disabled"
                tabindex="-1"
                @click.stop
                @change="handleSelect(option)"
              />
              <span class="vn-select-option-label">{{ option.label }}</span>
              <span v-if="option.tag" class="vn-select-tag">({{ option.tag }})</span>
            </div>
            <span
              v-if="!multiple && isSelected(option.value)"
              class="vn-select-check"
              aria-hidden="true"
            >✓</span>
            <span v-if="option.hint" class="vn-select-hint">{{ option.hint }}</span>
          </slot>
        </div>
      </template>
      <div v-else class="vn-select-empty">
        No options available
      </div>
    </div>
  </div>
</template>

<style scoped>
.vn-select {
  position: relative;
  width: 100%;
}

.vn-select.is-open {
  z-index: 80;
}

.vn-select-trigger {
  all: unset;
  box-sizing: border-box;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.65rem 0.85rem;
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-md);
  background: rgba(13, 16, 26, 0.85);
  color: #fff;
  cursor: pointer;
  font: inherit;
  font-size: 0.88rem;
  text-align: left;
  transition: all 160ms ease;
  user-select: none;
  box-shadow: none;
}

.vn-select-trigger:hover:not(:disabled) {
  border-color: var(--brand);
}

.vn-select-trigger:focus-visible,
.vn-select.is-open .vn-select-trigger {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25);
  background: rgba(18, 22, 34, 0.95);
  outline: none;
}

.vn-select-trigger:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.vn-select-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.vn-select-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
  color: #fff;
}

.vn-select-text.is-placeholder {
  color: var(--muted);
  font-weight: normal;
}

.vn-select-tag {
  color: var(--muted);
  font-size: 0.74rem;
  font-weight: normal;
  flex-shrink: 0;
}

.vn-select-arrow {
  color: var(--muted);
  font-size: 0.8rem;
  transition: transform 160ms ease;
  flex-shrink: 0;
}

.vn-select.is-open .vn-select-arrow {
  transform: rotate(180deg);
}

.vn-select-menu {
  position: absolute;
  z-index: 100;
  top: calc(100% + 0.35rem);
  right: 0;
  left: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  max-height: 14rem;
  overflow-y: auto;
  padding: 0.45rem;
  border: 1px solid rgba(99, 102, 241, 0.35);
  border-radius: var(--radius-md);
  background: rgba(18, 22, 34, 0.96);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.65), 0 0 16px rgba(99, 102, 241, 0.15);
  backdrop-filter: blur(16px);
}

.vn-select-menu::-webkit-scrollbar {
  width: 4px;
}
.vn-select-menu::-webkit-scrollbar-track {
  background: transparent;
}
.vn-select-menu::-webkit-scrollbar-thumb {
  background: rgba(99, 102, 241, 0.25);
  border-radius: 9999px;
}

.vn-select-option {
  all: unset;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.45rem 0.65rem;
  border-radius: var(--radius-sm);
  color: #e2e8f0;
  font-size: 0.84rem;
  cursor: pointer;
  background: transparent;
  width: 100%;
  text-align: left;
  transition: background 140ms ease, color 140ms ease;
  user-select: none;
}

.vn-select-option:hover:not(.is-disabled),
.vn-select-option.is-highlighted:not(.is-disabled) {
  background: rgba(99, 102, 241, 0.18);
  color: #fff;
}

.vn-select-option.is-selected {
  background: rgba(99, 102, 241, 0.25);
  color: #fff;
  font-weight: 600;
}

.vn-select-option.is-disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.vn-select-option-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.vn-select-option-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.vn-select-checkbox {
  width: auto;
  margin: 0;
  accent-color: #6366f1;
  cursor: pointer;
}

.vn-select-check {
  color: #a5b4fc;
  font-weight: 700;
  font-size: 0.82rem;
  flex-shrink: 0;
}

.vn-select-hint {
  color: var(--muted);
  font-size: 0.74rem;
  flex-shrink: 0;
}

.vn-select-empty {
  padding: 0.65rem 0.75rem;
  color: var(--muted);
  font-size: 0.82rem;
  text-align: center;
}
</style>
