<script setup lang="ts">
defineProps<{
  variant?: 'brand' | 'accent' | 'neutral' | 'success' | 'warning'
  clickable?: boolean
  capitalize?: boolean
}>()
</script>

<template>
  <span
    class="vn-badge"
    :class="[
      `variant-${variant || 'neutral'}`,
      { 'is-clickable': clickable, 'is-capitalize': capitalize }
    ]"
  >
    <span v-if="$slots.icon" class="badge-icon">
      <slot name="icon" />
    </span>
    <span class="badge-content">
      <slot />
    </span>
  </span>
</template>

<style scoped>
.vn-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.3rem 0.7rem;
  border-radius: 9999px;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  backdrop-filter: blur(8px);
  transition: all 180ms ease;
  user-select: none;
  border: 1px solid transparent;
  width: fit-content;
  max-width: 100%;
  align-self: flex-start;
  white-space: nowrap;
}

.is-capitalize,
.is-capitalize .badge-content {
  text-transform: capitalize;
}

.variant-brand {
  background: rgba(99, 102, 241, 0.14);
  border-color: rgba(99, 102, 241, 0.35);
  color: #a5b4fc;
}

.variant-accent {
  background: rgba(236, 72, 153, 0.14);
  border-color: rgba(236, 72, 153, 0.35);
  color: #f472b6;
}

.variant-neutral {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
  color: #cbd5e1;
}

.variant-success {
  background: rgba(16, 185, 129, 0.14);
  border-color: rgba(16, 185, 129, 0.35);
  color: #34d399;
}

.variant-warning {
  background: rgba(245, 158, 11, 0.14);
  border-color: rgba(245, 158, 11, 0.35);
  color: #fbbf24;
}

.is-clickable {
  cursor: pointer;
}

.is-clickable:hover {
  transform: translateY(-1px);
  filter: brightness(1.2);
}

.badge-icon {
  display: inline-flex;
  align-items: center;
  font-size: 0.85em;
}

.badge-content {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}
</style>
