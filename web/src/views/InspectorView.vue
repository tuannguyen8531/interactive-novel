<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDebugStore } from '@/stores/debug'

const router = useRouter()
const debug = useDebugStore()

onMounted(() => {
  void debug.refresh()
})
</script>

<template>
  <section v-if="!debug.enabled" class="notice-box">
    Developer Inspector is disabled outside development mode.
    <button class="secondary" type="button" @click="router.push('/')">Return home</button>
  </section>
  <template v-else>
    <section class="page-heading">
      <div>
        <p class="eyebrow">Developer Inspector</p>
        <h1>Scoped runtime view</h1>
        <p class="lede">This metadata is intentionally kept out of the player-facing transcript.</p>
      </div>
      <button class="secondary" type="button" @click="debug.refresh()">Refresh</button>
    </section>
    <section v-if="!debug.available" class="empty-state">Open a playthrough before inspecting it.</section>
    <pre v-else class="inspector-panel">{{ JSON.stringify(debug.inspector, null, 2) }}</pre>
  </template>
</template>

<style scoped>
.lede {
  margin-bottom: 0;
  color: var(--muted);
}

.inspector-panel {
  overflow: auto;
  margin: 0;
  padding: 1.2rem;
  border: 1px solid #363d4c;
  border-radius: 0.8rem;
  background: #202633;
  color: #e9dcc5;
  line-height: 1.55;
}
</style>
