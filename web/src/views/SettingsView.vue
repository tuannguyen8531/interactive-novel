<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useSettingsStore } from '@/stores/settings'

const settings = useSettingsStore()
const saved = ref(false)

onMounted(() => {
  void settings.load()
})

async function save(): Promise<void> {
  saved.value = false
  await settings.save()
  saved.value = true
}
</script>

<template>
  <section class="page-heading">
    <div>
      <p class="eyebrow">Settings / Providers</p>
      <h1>Choose how the story runs</h1>
      <p class="lede">Provider credentials stay outside the client response. This screen only shows safe routing metadata.</p>
    </div>
  </section>

  <section v-if="settings.loading && !settings.providerSettings" class="empty-state">Loading provider settings…</section>
  <section v-else class="settings-grid">
    <form class="card settings-card" @submit.prevent="save">
      <p class="eyebrow">Execution</p>
      <h2>Runtime policy</h2>
      <label>
        Mode
        <select v-model="settings.mode">
          <option value="quality">Quality</option>
          <option value="fast">Fast</option>
        </select>
      </label>
      <label class="checkbox-row">
        <input v-model="settings.allowCloud" type="checkbox" />
        <span>Allow cloud provider routing</span>
      </label>
      <p class="muted small-copy">Cloud routing remains opt-in. The local fixture does not make provider calls.</p>
      <button type="submit" :disabled="settings.loading || !settings.providerSettings">Save settings</button>
      <span v-if="saved" class="saved-label">Saved</span>
    </form>

    <section class="card settings-card">
      <p class="eyebrow">Targets</p>
      <h2>Configured models</h2>
      <div v-if="!settings.providerSettings" class="notice-box">No provider settings have been stored yet.</div>
      <div v-else class="target-list">
        <div v-for="target in Object.values(settings.providerSettings.targets)" :key="target.name" class="target-row">
          <div>
            <strong>{{ target.name }}</strong>
            <span>{{ target.provider }} · {{ target.model }}</span>
          </div>
          <small>{{ target.base_url || 'default endpoint' }}</small>
        </div>
      </div>
      <button class="secondary" type="button" :disabled="settings.testing" @click="settings.testProvider()">
        {{ settings.testing ? 'Testing…' : 'Test connection' }}
      </button>
      <div v-if="settings.connectivity.length" class="connectivity-list">
        <p v-for="result in settings.connectivity" :key="`${result.provider}-${result.model}`" :class="result.reachable ? 'ok' : 'bad'">
          {{ result.provider }} / {{ result.model }} — {{ result.reachable ? 'reachable' : result.message || 'unavailable' }}
        </p>
      </div>
    </section>
  </section>
  <div v-if="settings.error" class="error-box" role="alert">{{ settings.error }}</div>
</template>

<style scoped>
.lede {
  max-width: 43rem;
  margin-bottom: 0;
  color: var(--muted);
  line-height: 1.6;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.settings-card {
  position: relative;
}

.settings-card h2 {
  margin-bottom: 1.5rem;
}

label {
  display: grid;
  gap: 0.4rem;
  margin-bottom: 1rem;
  color: var(--muted);
  font-size: 0.85rem;
  font-weight: 700;
}

select {
  padding: 0.7rem;
  border: 1px solid var(--line);
  border-radius: 0.55rem;
  background: #fff;
  color: var(--ink);
}

.checkbox-row {
  display: flex;
  gap: 0.55rem;
  align-items: center;
}

.checkbox-row input {
  accent-color: var(--accent);
}

.small-copy {
  line-height: 1.5;
}

.saved-label {
  margin-left: 0.75rem;
  color: var(--green);
  font-size: 0.85rem;
}

.target-list {
  display: grid;
  gap: 0.65rem;
  margin-bottom: 1.2rem;
}

.target-row {
  display: flex;
  gap: 1rem;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem;
  border-radius: 0.55rem;
  background: #f4efe6;
}

.target-row div,
.target-row span {
  display: grid;
  gap: 0.2rem;
}

.target-row span,
.target-row small {
  color: var(--muted);
  font-size: 0.78rem;
}

.connectivity-list {
  margin-top: 1rem;
}

.connectivity-list p {
  margin-bottom: 0.3rem;
  font-size: 0.85rem;
}

.ok {
  color: var(--green);
}

.bad {
  color: #a33f48;
}

@media (max-width: 700px) {
  .settings-grid {
    display: block;
  }

  .settings-card + .settings-card {
    margin-top: 1rem;
  }
}
</style>
