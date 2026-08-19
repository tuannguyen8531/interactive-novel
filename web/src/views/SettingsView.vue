<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import type { ProviderTarget } from '@/api/types'
import ProviderModelField from '@/components/ProviderModelField.vue'

const settings = useSettingsStore()
const saved = ref(false)
const newProvider = ref<ProviderTarget['provider']>('ollama')

const roles = [
  { id: 'planner', label: 'Planner' },
  { id: 'simulator', label: 'Simulator' },
  { id: 'context_validator', label: 'Context validator' },
  { id: 'writer', label: 'Writer' },
  { id: 'critic', label: 'Critic' },
  { id: 'world_builder', label: 'World builder' },
  { id: 'embedding', label: 'Embedding' }
]

const targetNames = computed(() => Object.keys(settings.providerSettings?.targets ?? {}))

onMounted(() => {
  void settings.load()
})

async function save(): Promise<void> {
  saved.value = false
  try {
    await settings.save()
    saved.value = true
  } catch {
    saved.value = false
  }
}

async function testConnection(): Promise<void> {
  await save()
  if (settings.error) return
  try {
    await settings.testProvider()
  } catch {
    // The store exposes the API error below the form.
  }
}

function addTarget(): void {
  settings.addTarget(newProvider.value)
  saved.value = false
}

function removeTarget(targetName: string): void {
  settings.removeTarget(targetName)
  saved.value = false
}

function changeProvider(targetName: string, provider: ProviderTarget['provider']): void {
  settings.changeProvider(targetName, provider)
  saved.value = false
}

function changePrimary(role: string, targetName: string): void {
  settings.setPrimaryTarget(role, targetName)
  saved.value = false
}

function changeFallback(role: string, targetName: string, event: Event): void {
  settings.toggleFallback(role, targetName, (event.target as HTMLInputElement).checked)
  saved.value = false
}

function availableFallbacks(role: string): string[] {
  const primary = settings.providerSettings?.role_routes[role]?.primary_target
  return targetNames.value.filter((name) => name !== primary)
}
</script>

<template>
  <section class="page-heading">
    <div>
      <p class="eyebrow">Settings / Providers</p>
      <h1>Choose how the story runs</h1>
      <p class="lede">Configure local or cloud models without storing credentials in browser-visible settings.</p>
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
      <p class="muted small-copy">Cloud targets remain disabled until this option is explicitly enabled.</p>
      <button type="submit" :disabled="settings.loading || !settings.providerSettings">Save all settings</button>
      <span v-if="saved" class="saved-label">Saved</span>
    </form>

    <section class="card settings-card">
      <p class="eyebrow">Targets</p>
      <h2>Provider models</h2>
      <div v-if="!settings.providerSettings" class="notice-box">No provider settings have been stored yet.</div>
      <div v-else class="target-list">
        <div v-for="(target, targetName) in settings.providerSettings.targets" :key="targetName" class="target-editor">
          <div class="target-heading">
            <strong>{{ targetName }}</strong>
            <button
              class="text-button danger"
              type="button"
              :disabled="targetNames.length <= 1"
              @click="removeTarget(targetName)"
            >
              Remove
            </button>
          </div>
          <label>
            Provider
            <select v-model="target.provider" @change="changeProvider(targetName, target.provider)">
              <option value="ollama">Ollama</option>
              <option value="gemini">Gemini</option>
              <option value="openrouter">OpenRouter</option>
            </select>
          </label>
          <label>
            Model
            <ProviderModelField v-model="target.model" :target="target" @update:model-value="saved = false" />
          </label>
          <label>
            Base URL
            <input
              v-model="target.base_url"
              autocomplete="url"
              :placeholder="target.provider === 'ollama' ? 'http://localhost:11434/api' : 'Provider default'"
              @input="saved = false"
            />
          </label>
          <div class="field-grid">
            <label>
              API key environment variable
              <input
                v-model="target.api_key_env"
                autocomplete="off"
                placeholder="Not required"
                @input="saved = false"
              />
            </label>
            <label>
              Timeout (seconds)
              <input v-model.number="target.timeout_seconds" type="number" min="1" max="600" @input="saved = false" />
            </label>
          </div>
          <p class="muted secret-note">
            Secret values belong in <code>.env</code>; only the variable name is saved here.
          </p>
        </div>
        <div class="add-target-row">
          <select v-model="newProvider" aria-label="Provider for new target">
            <option value="ollama">Ollama</option>
            <option value="gemini">Gemini</option>
            <option value="openrouter">OpenRouter</option>
          </select>
          <button class="secondary" type="button" @click="addTarget">Add target</button>
        </div>
      </div>
      <button class="secondary" type="button" :disabled="settings.testing || settings.loading" @click="testConnection">
        {{ settings.testing ? 'Testing…' : 'Save & test connections' }}
      </button>
      <div v-if="settings.connectivity.length" class="connectivity-list">
        <p v-for="result in settings.connectivity" :key="`${result.provider}-${result.model}`" :class="result.reachable ? 'ok' : 'bad'">
          {{ result.provider }} / {{ result.model }} — {{ result.reachable ? 'reachable' : result.message || 'unavailable' }}
        </p>
      </div>
    </section>

    <section v-if="settings.providerSettings" class="card settings-card routing-card">
      <p class="eyebrow">Routing</p>
      <h2>Role assignments</h2>
      <p class="muted small-copy">Each AI role has one primary target and optional ordered fallbacks.</p>
      <div class="route-list">
        <div v-for="role in roles" :key="role.id" class="route-row">
          <div>
            <strong>{{ role.label }}</strong>
            <small>{{ role.id }}</small>
          </div>
          <label>
            Primary
            <select
              v-model="settings.providerSettings.role_routes[role.id].primary_target"
              @change="changePrimary(role.id, settings.providerSettings.role_routes[role.id].primary_target)"
            >
              <option v-for="targetName in targetNames" :key="targetName" :value="targetName">{{ targetName }}</option>
            </select>
          </label>
          <fieldset>
            <legend>Fallbacks</legend>
            <label
              v-for="targetName in availableFallbacks(role.id)"
              :key="targetName"
              class="fallback-option"
            >
              <input
                type="checkbox"
                :checked="settings.providerSettings.role_routes[role.id].fallback_targets.includes(targetName)"
                @change="changeFallback(role.id, targetName, $event)"
              />
              {{ targetName }}
            </label>
            <span
              v-if="targetNames.length <= 1"
              class="muted"
            >None available</span>
          </fieldset>
        </div>
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

input {
  box-sizing: border-box;
  width: 100%;
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
  width: auto;
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

.target-editor {
  padding: 0.75rem;
  border: 1px solid var(--line);
  border-radius: 0.55rem;
  background: #f4efe6;
}

.target-heading,
.add-target-row {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  justify-content: space-between;
}

.target-heading {
  margin-bottom: 0.75rem;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.secret-note {
  margin: -0.25rem 0 0;
  font-size: 0.75rem;
}

.text-button {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--accent);
}

.text-button.danger {
  color: #a33f48;
}

.routing-card {
  grid-column: 1 / -1;
}

.route-list {
  display: grid;
  gap: 0.65rem;
}

.route-row {
  display: grid;
  grid-template-columns: minmax(10rem, 0.7fr) minmax(12rem, 1fr) minmax(14rem, 1.5fr);
  gap: 1rem;
  align-items: start;
  padding: 0.8rem;
  border: 1px solid var(--line);
  border-radius: 0.55rem;
}

.route-row > div,
.route-row small {
  display: grid;
  gap: 0.15rem;
}

.route-row small {
  color: var(--muted);
}

fieldset {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}

legend {
  width: 100%;
  margin-bottom: 0.4rem;
  color: var(--muted);
  font-size: 0.85rem;
  font-weight: 700;
}

.fallback-option {
  display: flex;
  gap: 0.35rem;
  align-items: center;
  margin: 0;
  font-weight: 500;
}

.fallback-option input {
  width: auto;
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

  .field-grid,
  .route-row {
    grid-template-columns: 1fr;
  }
}
</style>
