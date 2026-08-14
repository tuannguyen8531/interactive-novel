<script setup lang="ts">
import { onMounted } from 'vue'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

onMounted(() => {
  void appStore.checkHealth()
})
</script>

<template>
  <section class="card">
    <p class="eyebrow">Phase 1 · Project skeleton</p>
    <h2>Interactive Novel</h2>
    <p>Backend, frontend shell and transport contracts are ready for the next phase.</p>

    <div class="health" aria-live="polite">
      <span class="health-label">Backend health</span>
      <span v-if="appStore.loading">Checking…</span>
      <span v-else-if="appStore.health" class="ok">Connected · {{ appStore.health.version }}</span>
      <span v-else class="error">{{ appStore.error ?? 'Unavailable' }}</span>
    </div>

    <button type="button" :disabled="appStore.loading" @click="appStore.checkHealth()">
      Check again
    </button>
  </section>
</template>

<style scoped>
.card {
  max-width: 42rem;
  padding: 2rem;
  border: 1px solid #d9e1ec;
  border-radius: 1rem;
  background: #fff;
  box-shadow: 0 1rem 3rem rgb(26 42 68 / 8%);
}

.eyebrow {
  margin: 0 0 0.5rem;
  color: #4f6b8a;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

h2 {
  margin: 0 0 0.75rem;
}

.health {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin: 1.5rem 0;
  padding: 0.8rem 1rem;
  border-radius: 0.6rem;
  background: #f4f7fb;
}

.health-label {
  font-weight: 700;
}

.ok {
  color: #176b45;
}

.error {
  color: #a42d3f;
}

button {
  padding: 0.6rem 1rem;
  border: 0;
  border-radius: 0.5rem;
  background: #245ea8;
  color: #fff;
  cursor: pointer;
}

button:disabled {
  cursor: wait;
  opacity: 0.65;
}
</style>
