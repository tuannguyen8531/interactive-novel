<script setup lang="ts">
defineProps<{
  steps: { id: string; label: string; description?: string }[]
  currentStep: number
}>()

const emit = defineEmits<{
  (event: 'selectStep', index: number): void
}>()
</script>

<template>
  <div class="step-progress">
    <div
      v-for="(step, index) in steps"
      :key="step.id"
      class="step-item"
      :class="{
        'is-active': index === currentStep,
        'is-completed': index < currentStep,
        'is-upcoming': index > currentStep
      }"
      @click="index < currentStep ? emit('selectStep', index) : null"
    >
      <div class="step-indicator">
        <span v-if="index < currentStep" class="check-icon">✓</span>
        <span v-else class="step-number">{{ index + 1 }}</span>
      </div>
      <div class="step-text">
        <span class="step-label">{{ step.label }}</span>
        <span v-if="step.description" class="step-desc">{{ step.description }}</span>
      </div>
      <div v-if="index < steps.length - 1" class="step-divider" />
    </div>
  </div>
</template>

<style scoped>
.step-progress {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 1rem;
  backdrop-filter: blur(12px);
}

.step-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex: 1;
  position: relative;
  transition: all 180ms ease;
}

.step-item.is-completed {
  cursor: pointer;
}

.step-item.is-completed:hover .step-label {
  color: #a5b4fc;
}

.step-indicator {
  width: 1.85rem;
  height: 1.85rem;
  border-radius: 9999px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 700;
  border: 2px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  color: #94a3b8;
  transition: all 220ms ease;
  flex-shrink: 0;
}

.is-active .step-indicator {
  border-color: #6366f1;
  background: rgba(99, 102, 241, 0.2);
  color: #f8fafc;
  box-shadow: 0 0 12px rgba(99, 102, 241, 0.45);
}

.is-completed .step-indicator {
  border-color: #10b981;
  background: rgba(16, 185, 129, 0.2);
  color: #34d399;
}

.step-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.step-label {
  font-size: 0.82rem;
  font-weight: 600;
  color: #94a3b8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color 180ms ease;
}

.is-active .step-label {
  color: #f8fafc;
  font-weight: 700;
}

.is-completed .step-label {
  color: #e2e8f0;
}

.step-desc {
  font-size: 0.7rem;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.step-divider {
  flex: 1;
  height: 2px;
  background: rgba(255, 255, 255, 0.08);
  margin: 0 0.5rem;
  min-width: 1rem;
}

.is-completed .step-divider {
  background: rgba(16, 185, 129, 0.35);
}

@media (max-width: 640px) {
  .step-desc {
    display: none;
  }
}
</style>
