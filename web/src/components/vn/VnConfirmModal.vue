<script setup lang="ts">
import { onBeforeUnmount, onMounted, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title?: string
    message?: string
    confirmText?: string
    cancelText?: string
    variant?: 'danger' | 'brand' | 'warning'
    busy?: boolean
  }>(),
  {
    title: 'Confirm Action',
    message: 'Are you sure you want to proceed?',
    confirmText: 'Confirm',
    cancelText: 'Cancel',
    variant: 'danger',
    busy: false,
  }
)

const emit = defineEmits<{
  (event: 'confirm'): void
  (event: 'cancel'): void
  (event: 'update:open', value: boolean): void
}>()

function handleCancel(): void {
  if (props.busy) return
  emit('cancel')
  emit('update:open', false)
}

function handleConfirm(): void {
  if (props.busy) return
  emit('confirm')
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && props.open && !props.busy) {
    handleCancel()
  }
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
  }
)

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="vn-modal">
      <div
        v-if="open"
        class="vn-modal-overlay"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="title"
        @click.self="handleCancel"
      >
        <div class="vn-modal-card" :class="`is-${variant}`">
          <!-- Header with icon and title -->
          <div class="vn-modal-header">
            <div class="vn-modal-icon-badge">
              <slot name="icon">
                <span v-if="variant === 'danger'">🗑️</span>
                <span v-else-if="variant === 'warning'">⚠️</span>
                <span v-else>✨</span>
              </slot>
            </div>
            <div class="vn-modal-titles">
              <slot name="title">
                <h3 class="vn-modal-title">{{ title }}</h3>
              </slot>
            </div>
            <button
              type="button"
              class="vn-modal-close-btn"
              :disabled="busy"
              aria-label="Close dialog"
              @click="handleCancel"
            >
              ✕
            </button>
          </div>

          <div class="vn-modal-body">
            <slot>
              <p class="vn-modal-message">{{ message }}</p>
            </slot>
          </div>

          <div class="vn-modal-actions">
            <slot name="actions">
              <button
                type="button"
                class="secondary vn-modal-btn cancel-btn"
                :disabled="busy"
                @click="handleCancel"
              >
                {{ cancelText }}
              </button>
              <button
                type="button"
                class="vn-modal-btn confirm-btn"
                :class="`variant-${variant}`"
                :disabled="busy"
                @click="handleConfirm"
              >
                <span v-if="busy" class="spin-dot" />
                <span class="btn-label">{{ busy ? 'Processing…' : confirmText }}</span>
              </button>
            </slot>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.vn-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  background: rgba(5, 7, 13, 0.78);
  backdrop-filter: blur(10px);
}

.vn-modal-card {
  position: relative;
  width: 100%;
  max-width: 28rem;
  border-radius: var(--radius-lg);
  background: linear-gradient(145deg, rgba(20, 24, 38, 0.98), rgba(13, 16, 26, 0.96));
  border: 1px solid var(--border-medium);
  box-shadow: 0 25px 60px rgba(0, 0, 0, 0.85), 0 0 20px rgba(99, 102, 241, 0.1);
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.vn-modal-card.is-danger {
  border-color: rgba(239, 68, 68, 0.4);
  box-shadow: 0 25px 60px rgba(0, 0, 0, 0.85), 0 0 30px rgba(239, 68, 68, 0.15);
}

.vn-modal-card.is-warning {
  border-color: rgba(245, 158, 11, 0.4);
  box-shadow: 0 25px 60px rgba(0, 0, 0, 0.85), 0 0 30px rgba(245, 158, 11, 0.15);
}

.vn-modal-card.is-brand {
  border-color: rgba(99, 102, 241, 0.4);
  box-shadow: 0 25px 60px rgba(0, 0, 0, 0.85), 0 0 30px rgba(99, 102, 241, 0.15);
}

.vn-modal-header {
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
}

.vn-modal-icon-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.75rem;
  height: 2.75rem;
  border-radius: var(--radius-md);
  font-size: 1.35rem;
  flex-shrink: 0;
}

.is-danger .vn-modal-icon-badge {
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.is-warning .vn-modal-icon-badge {
  background: rgba(245, 158, 11, 0.15);
  border: 1px solid rgba(245, 158, 11, 0.35);
}

.is-brand .vn-modal-icon-badge {
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(99, 102, 241, 0.3);
}

.vn-modal-titles {
  flex: 1;
  min-width: 0;
  padding-top: 0.2rem;
}

.vn-modal-title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  color: #fff;
  line-height: 1.3;
}

.vn-modal-close-btn {
  all: unset;
  cursor: pointer;
  color: var(--muted);
  font-size: 1.1rem;
  padding: 0.3rem 0.5rem;
  border-radius: var(--radius-sm);
  transition: all 140ms ease;
  line-height: 1;
}

.vn-modal-close-btn:hover:not(:disabled) {
  color: #fff;
  background: rgba(255, 255, 255, 0.08);
}

.vn-modal-body {
  color: #cbd5e1;
  font-size: 0.92rem;
  line-height: 1.55;
}

.vn-modal-message {
  margin: 0;
}

.vn-modal-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 0.25rem;
}

.vn-modal-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  padding: 0.65rem 1.25rem;
  font-size: 0.88rem;
  font-weight: 600;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 160ms ease;
  box-shadow: none;
  -webkit-text-fill-color: initial !important;
  color: #fff !important;
}

.btn-label {
  -webkit-text-fill-color: initial !important;
  color: inherit !important;
  display: inline-block;
}

.confirm-btn.variant-danger {
  background: linear-gradient(135deg, #ef4444, #b91c1c);
  border: 1px solid #ef4444;
  color: #fff !important;
  -webkit-text-fill-color: #fff !important;
  box-shadow: 0 4px 14px rgba(239, 68, 68, 0.4);
}

.confirm-btn.variant-danger:hover:not(:disabled) {
  background: linear-gradient(135deg, #dc2626, #991b1b);
  box-shadow: 0 6px 20px rgba(239, 68, 68, 0.55);
  transform: translateY(-1px);
}

.confirm-btn.variant-warning {
  background: linear-gradient(135deg, #f59e0b, #d97706);
  border: 1px solid #f59e0b;
  color: #fff !important;
  -webkit-text-fill-color: #fff !important;
  box-shadow: 0 4px 14px rgba(245, 158, 11, 0.4);
}

.confirm-btn.variant-warning:hover:not(:disabled) {
  background: linear-gradient(135deg, #d97706, #b45309);
  box-shadow: 0 6px 20px rgba(245, 158, 11, 0.55);
  transform: translateY(-1px);
}

.confirm-btn.variant-brand {
  background: linear-gradient(135deg, var(--brand), #4338ca);
  border: 1px solid var(--brand);
  color: #fff !important;
  -webkit-text-fill-color: #fff !important;
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4);
}

.confirm-btn.variant-brand:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.55);
}

.spin-dot {
  width: 0.85rem;
  height: 0.85rem;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
  display: inline-block;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Modal Transition Animations */
.vn-modal-enter-active,
.vn-modal-leave-active {
  transition: opacity 200ms ease;
}

.vn-modal-enter-from,
.vn-modal-leave-to {
  opacity: 0;
}

.vn-modal-enter-active .vn-modal-card {
  transition: transform 200ms cubic-bezier(0.16, 1, 0.3, 1), opacity 200ms ease;
}

.vn-modal-leave-active .vn-modal-card {
  transition: transform 160ms ease, opacity 160ms ease;
}

.vn-modal-enter-from .vn-modal-card {
  opacity: 0;
  transform: scale(0.92) translateY(8px);
}

.vn-modal-leave-to .vn-modal-card {
  opacity: 0;
  transform: scale(0.95);
}
</style>
