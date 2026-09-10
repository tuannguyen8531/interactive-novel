<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    value: number
    max?: number
    label?: string
    showValue?: boolean
  }>(),
  {
    max: 100,
    label: 'Affection',
    showValue: true
  }
)

const percent = computed(() => {
  const bounded = Math.max(0, Math.min(props.max, props.value))
  return Math.round((bounded / props.max) * 100)
})

const barColor = computed(() => {
  if (percent.value >= 80) return 'linear-gradient(90deg, #ec4899, #f43f5e)'
  if (percent.value >= 50) return 'linear-gradient(90deg, #8b5cf6, #ec4899)'
  if (percent.value >= 25) return 'linear-gradient(90deg, #6366f1, #8b5cf6)'
  return 'linear-gradient(90deg, #64748b, #6366f1)'
})
</script>

<template>
  <div class="affection-bar-wrapper">
    <div class="bar-header">
      <span class="bar-label">
        <svg class="heart-icon" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
        </svg>
        {{ label }}
      </span>
      <span v-if="showValue" class="bar-value">{{ percent }}%</span>
    </div>
    <div class="bar-track">
      <div
        class="bar-fill"
        :style="{
          width: `${percent}%`,
          background: barColor
        }"
      />
    </div>
  </div>
</template>

<style scoped>
.affection-bar-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  width: 100%;
}

.bar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.8rem;
  font-weight: 600;
}

.bar-label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  color: #cbd5e1;
}

.heart-icon {
  width: 0.85rem;
  height: 0.85rem;
  color: #ec4899;
  filter: drop-shadow(0 0 4px rgba(236, 72, 153, 0.4));
}

.bar-value {
  color: #f472b6;
  font-variant-numeric: tabular-nums;
}

.bar-track {
  width: 100%;
  height: 0.45rem;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 9999px;
  overflow: hidden;
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.4);
}

.bar-fill {
  height: 100%;
  border-radius: 9999px;
  transition: width 400ms cubic-bezier(0.16, 1, 0.3, 1);
  box-shadow: 0 0 8px rgba(236, 72, 153, 0.35);
}
</style>
