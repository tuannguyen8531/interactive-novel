<script setup lang="ts">
defineProps<{
  value: number
  label?: string
}>()
</script>

<template>
  <div class="heartbeat-badge" :title="label || 'Player Stamina / Heartbeat'">
    <span class="heart-pulse">
      <svg class="heart-icon" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
      </svg>
    </span>
    <span class="heartbeat-value">{{ value }}</span>
  </div>
</template>

<style scoped>
.heartbeat-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.3rem 0.75rem;
  background: rgba(236, 72, 153, 0.12);
  border: 1px solid rgba(236, 72, 153, 0.35);
  border-radius: 9999px;
  backdrop-filter: blur(8px);
  color: #f472b6;
  font-size: 0.8rem;
  font-weight: 700;
  box-shadow: 0 0 12px rgba(236, 72, 153, 0.15);
}

.heart-pulse {
  display: inline-flex;
  align-items: center;
  animation: pulse 1.8s infinite ease-in-out;
}

.heart-icon {
  width: 0.95rem;
  height: 0.95rem;
  color: #f43f5e;
  filter: drop-shadow(0 0 5px rgba(244, 63, 94, 0.6));
}

.heartbeat-value {
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.03em;
}

@keyframes pulse {
  0% {
    transform: scale(1);
  }
  14% {
    transform: scale(1.22);
  }
  28% {
    transform: scale(1);
  }
  42% {
    transform: scale(1.15);
  }
  70% {
    transform: scale(1);
  }
}
</style>
