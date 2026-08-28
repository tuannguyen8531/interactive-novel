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
const ollamaTarget = computed(() =>
  Object.values(settings.providerSettings?.targets ?? {}).find((target) => target.provider === 'ollama')
)
const ollamaAccountText = computed(() => {
  if (settings.ollamaAccountLoading) return 'Checking…'
  if (settings.ollamaAccount?.username) return settings.ollamaAccount.username
  if (settings.ollamaAccount?.detail === 'Not signed in') return 'Not signed in to Ollama Cloud.'
  return 'Unavailable'
})

onMounted(async () => {
  await settings.load()
  await refreshOllamaAccount()
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
  if (newProvider.value === 'ollama') void refreshOllamaAccount()
}

function removeTarget(targetName: string): void {
  settings.removeTarget(targetName)
  saved.value = false
}

function renameTarget(targetName: string, event: Event): void {
  const input = event.target as HTMLInputElement
  const error = settings.renameTarget(targetName, input.value)
  input.setCustomValidity(error ?? '')
  if (error) {
    input.reportValidity()
    input.value = targetName
    return
  }
  saved.value = false
}

function clearTargetNameError(event: Event): void {
  const input = event.target as HTMLInputElement
  input.setCustomValidity('')
}

function changeProvider(targetName: string, provider: ProviderTarget['provider']): void {
  settings.changeProvider(targetName, provider)
  saved.value = false
  if (provider === 'ollama') void refreshOllamaAccount()
}

async function refreshOllamaAccount(): Promise<void> {
  if (!ollamaTarget.value) return
  await settings.loadOllamaAccount(ollamaTarget.value.base_url)
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

function fallbackSummary(role: string): string {
  const selected = settings.providerSettings?.role_routes[role]?.fallback_targets ?? []
  if (!selected.length) return 'No fallback'
  if (selected.length <= 2) return selected.join(', ')
  return `${selected.length} targets selected`
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
    <form class="card settings-card full-row" @submit.prevent="save">
      <p class="eyebrow">Execution</p>
      <h2>Runtime policy</h2>
      <p class="muted small-copy runtime-description">
        Set the defaults used when a new story world is generated. Existing worlds keep their own language.
      </p>
      <div class="runtime-options">
        <label class="runtime-field">
          <span class="field-label">Mode</span>
          <select v-model="settings.mode">
            <option value="quality">Quality</option>
            <option value="fast">Fast</option>
          </select>
          <span class="muted small-copy">Quality uses the full multi-step story pipeline.</span>
        </label>
        <label class="runtime-field">
          <span class="field-label">Story language</span>
          <select v-model="settings.storyLanguage">
            <option value="en">English</option>
            <option value="vi">Vietnamese</option>
          </select>
          <span class="muted small-copy">Default language for newly generated stories.</span>
        </label>
        <label class="runtime-toggle">
          <input v-model="settings.allowCloud" type="checkbox" />
          <span class="runtime-toggle-copy">
            <strong>Allow cloud provider routing</strong>
            <span class="muted small-copy">Cloud targets remain disabled until this option is explicitly enabled.</span>
          </span>
        </label>
      </div>
      <div class="runtime-actions">
        <button type="submit" :disabled="settings.loading || !settings.providerSettings">Save all settings</button>
        <span v-if="saved" class="saved-label">Saved</span>
      </div>
    </form>

    <section class="card settings-card full-row">
      <p class="eyebrow">Targets</p>
      <h2>Provider models</h2>
      <div v-if="!settings.providerSettings" class="notice-box">No provider settings have been stored yet.</div>
      <template v-else>
        <div class="add-target-panel">
          <div>
            <strong>Add a provider target</strong>
            <p class="muted small-copy">Choose a provider, then assign the new target to roles below.</p>
          </div>
          <div class="add-target-controls">
            <label>
              Provider
              <select v-model="newProvider" aria-label="Provider for new target">
                <option value="ollama">Ollama</option>
                <option value="gemini">Gemini</option>
                <option value="openrouter">OpenRouter</option>
              </select>
            </label>
            <button type="button" @click="addTarget">+ Add target</button>
          </div>
        </div>
        <div class="target-list">
          <div v-for="(target, targetName) in settings.providerSettings.targets" :key="targetName" class="target-editor">
          <div class="target-heading">
            <label class="target-name-label">
              Target name
              <input
                :value="targetName"
                maxlength="160"
                autocomplete="off"
                @input="clearTargetNameError"
                @change="renameTarget(targetName, $event)"
              />
            </label>
            <button
              class="remove-target-button"
              type="button"
              :disabled="targetNames.length <= 1"
              :aria-label="`Remove target ${targetName}`"
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
          <div v-if="target.provider === 'ollama'" class="field-grid">
            <div class="field-block">
              <span class="field-label">Cloud account</span>
              <div class="account-control">
                <input :value="ollamaAccountText" disabled aria-label="Ollama Cloud account" />
                <button class="secondary" type="button" :disabled="settings.ollamaAccountLoading" @click="refreshOllamaAccount">
                  {{ settings.ollamaAccountLoading ? 'Checking…' : 'Refresh' }}
                </button>
              </div>
              <p v-if="settings.ollamaAccount?.detail && settings.ollamaAccount.detail !== 'Not signed in'" class="muted account-detail">
                {{ settings.ollamaAccount.detail }}
              </p>
            </div>
            <label>
              Timeout (seconds)
              <input v-model.number="target.timeout_seconds" type="number" min="1" max="600" @input="saved = false" />
            </label>
          </div>
          <div v-else class="field-grid">
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
            <template v-if="target.provider === 'ollama'">Ollama Cloud sign-in is managed by the local Ollama application.</template>
            <template v-else>Secret values belong in <code>.env</code>; only the variable name is saved here.</template>
          </p>
          </div>
        </div>
      </template>
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
          <div class="fallback-field">
            <span class="field-label">Fallbacks</span>
            <details class="fallback-dropdown">
              <summary>{{ fallbackSummary(role.id) }}</summary>
              <div class="fallback-menu">
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
                <span v-if="targetNames.length <= 1" class="muted fallback-empty">No fallback target available</span>
              </div>
            </details>
          </div>
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
  grid-template-columns: 1fr;
  gap: 1rem;
}

.full-row {
  grid-column: 1 / -1;
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
  color: var(--green);
  font-size: 0.85rem;
}

.runtime-description {
  max-width: 48rem;
  margin: -0.75rem 0 1.25rem;
}

.runtime-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  align-items: stretch;
}

.runtime-field,
.runtime-toggle {
  min-width: 0;
  margin: 0;
  padding: 1rem;
  border: 1px solid var(--line);
  border-radius: 0.65rem;
  background: #fff;
}

.runtime-field {
  align-content: start;
}

.runtime-field .small-copy,
.runtime-toggle .small-copy {
  display: block;
  font-weight: 400;
}

.runtime-toggle {
  display: flex;
  gap: 0.75rem;
  align-items: start;
}

.runtime-toggle input {
  width: auto;
  margin-top: 0.2rem;
  accent-color: var(--accent);
}

.runtime-toggle-copy {
  display: grid;
  gap: 0.35rem;
  min-width: 0;
  color: var(--ink);
}

.runtime-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  justify-content: flex-end;
  margin-top: 1.25rem;
}

.add-target-panel {
  display: flex;
  gap: 1rem;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
  padding: 0.9rem 1rem;
  border: 1px dashed var(--line);
  border-radius: 0.7rem;
  background: #fffdf8;
}

.add-target-panel p,
.add-target-controls label {
  margin-bottom: 0;
}

.add-target-controls {
  display: flex;
  gap: 0.65rem;
  align-items: end;
}

.target-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(30rem, 100%), 1fr));
  gap: 0.65rem;
  margin-bottom: 1.2rem;
}

.target-editor {
  padding: 0.75rem;
  border: 1px solid var(--line);
  border-radius: 0.55rem;
  background: #f4efe6;
}

.target-heading {
  display: flex;
  gap: 0.75rem;
  align-items: end;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.target-name-label {
  min-width: 0;
  flex: 1;
  margin-bottom: 0;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.field-block {
  min-width: 0;
}

.field-label {
  display: block;
  margin-bottom: 0.4rem;
  color: var(--muted);
  font-size: 0.85rem;
  font-weight: 700;
}

.account-control {
  display: flex;
  gap: 0.5rem;
}

.account-control input:disabled {
  background: #eee9df;
  color: var(--ink);
  opacity: 1;
}

.account-detail {
  margin: 0.35rem 0 0;
  font-size: 0.75rem;
  line-height: 1.4;
}

.secret-note {
  margin: -0.25rem 0 0;
  font-size: 0.75rem;
}

.remove-target-button {
  min-height: 2.65rem;
  flex: 0 0 auto;
  padding: 0.65rem 0.8rem;
  border: 1px solid #d8a8ad;
  background: transparent;
  color: #a33f48;
}

.remove-target-button:hover:not(:disabled) {
  border-color: #a33f48;
  background: #f8e8e9;
  color: #a33f48;
}

.remove-target-button:disabled {
  border-color: var(--line);
  background: transparent;
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

.fallback-field {
  min-width: 0;
}

.fallback-dropdown {
  position: relative;
}

.fallback-dropdown summary {
  overflow: hidden;
  padding: 0.7rem 2.1rem 0.7rem 0.7rem;
  border: 1px solid var(--line);
  border-radius: 0.55rem;
  background: #fff;
  color: var(--ink);
  cursor: pointer;
  list-style: none;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fallback-dropdown summary::-webkit-details-marker {
  display: none;
}

.fallback-dropdown summary::after {
  position: absolute;
  top: 0.75rem;
  right: 0.75rem;
  content: '▾';
  color: var(--muted);
}

.fallback-dropdown[open] summary::after {
  transform: rotate(180deg);
}

.fallback-menu {
  position: absolute;
  z-index: 10;
  top: calc(100% + 0.35rem);
  right: 0;
  left: 0;
  display: grid;
  gap: 0.2rem;
  max-height: 14rem;
  overflow-y: auto;
  padding: 0.45rem;
  border: 1px solid var(--line);
  border-radius: 0.55rem;
  background: #fff;
  box-shadow: var(--shadow);
}

.fallback-option {
  display: flex;
  gap: 0.35rem;
  align-items: center;
  margin: 0;
  padding: 0.45rem 0.5rem;
  border-radius: 0.35rem;
  font-weight: 500;
  cursor: pointer;
}

.fallback-option:hover {
  background: #f1ece2;
}

.fallback-option input {
  width: auto;
}

.fallback-empty {
  padding: 0.45rem 0.5rem;
  font-size: 0.8rem;
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

  .runtime-options,
  .field-grid,
  .route-row {
    grid-template-columns: 1fr;
  }

  .add-target-panel,
  .add-target-controls {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
