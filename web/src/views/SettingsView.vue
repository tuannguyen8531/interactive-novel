<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '@/api/client'
import { useSettingsStore } from '@/stores/settings'
import type { BackupRecord, ProviderTarget } from '@/api/types'
import ProviderModelField from '@/components/ProviderModelField.vue'
import VnBadge from '@/components/vn/VnBadge.vue'
import VnSelect from '@/components/vn/VnSelect.vue'
import VnConfirmModal from '@/components/vn/VnConfirmModal.vue'

const settings = useSettingsStore()
const saved = ref(false)
const saving = ref(false)
const newProvider = ref<ProviderTarget['provider']>('ollama')

const backups = ref<BackupRecord[]>([])
const integrity = ref<{ ok: boolean; message: string } | null>(null)
const dataBusy = ref(false)
const dataMessage = ref<string | null>(null)
const dataError = ref<string | null>(null)
const backupToRestore = ref<BackupRecord | null>(null)

const providerOptions = [
  { value: 'ollama', label: '🦙 Ollama (Local Engine)', tag: 'Local' },
  { value: 'gemini', label: '✦ Google Gemini', tag: 'Cloud' },
  { value: 'openrouter', label: '🌐 OpenRouter', tag: 'Cloud' },
]

const targetProviderOptions = [
  { value: 'ollama', label: '🦙 Ollama' },
  { value: 'gemini', label: '✦ Google Gemini' },
  { value: 'openrouter', label: '🌐 OpenRouter' },
]

const roles = [
  { id: 'writer', label: 'Writer' },
  { id: 'planner', label: 'Planner' },
  { id: 'simulator', label: 'Simulator' },
  { id: 'validator', label: 'Validator' },
  { id: 'critic', label: 'Critic' },
  { id: 'world_builder', label: 'World builder' },
  { id: 'embedding', label: 'Embedding' }
]

const roleDescriptions: Record<string, { icon: string; name: string; desc: string }> = {
  writer: {
    icon: '📝',
    name: 'Story Writer',
    desc: 'Composes narrative prose, vivid atmosphere, and expressive dialogue beats.'
  },
  planner: {
    icon: '🧠',
    name: 'Story Director',
    desc: 'Directs scene progression, plot developments, and dramatic pacing.'
  },
  simulator: {
    icon: '🎭',
    name: 'Character Personality',
    desc: 'Brings characters to life with expressive reactions, feelings, and evolving bonds.'
  },
  validator: {
    icon: '🛡️',
    name: 'Story Continuity',
    desc: 'Ensures scene logic, timeline consistency, and character facts remain coherent.'
  },
  critic: {
    icon: '🔍',
    name: 'Prose Polish',
    desc: 'Refines writing style, dialogue rhythm, and natural tone.'
  },
  world_builder: {
    icon: '🌍',
    name: 'World Lore & Setting',
    desc: 'Creates world backgrounds, locations, cast dossiers, and initial scenarios.'
  },
  embedding: {
    icon: '🧬',
    name: 'Long-Term Memory',
    desc: 'Remembers past decisions, lore details, and prior encounters across scenes.'
  }
}

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
  await Promise.all([
    settings.load(),
    refreshOllamaAccount(),
    refreshData()
  ])
})

async function refreshData(): Promise<void> {
  dataBusy.value = true
  dataError.value = null
  try {
    const [records, report] = await Promise.all([api.listBackups(), api.databaseIntegrity()])
    backups.value = records
    integrity.value = report
  } catch (cause) {
    dataError.value = errorText(cause)
  } finally {
    dataBusy.value = false
  }
}

async function createBackup(): Promise<void> {
  dataBusy.value = true
  dataError.value = null
  try {
    const report = await api.createBackup()
    dataMessage.value = `Backup created (${formatBytes(report.size_bytes)}).`
    await refreshData()
  } catch (cause) {
    dataError.value = errorText(cause)
  } finally {
    dataBusy.value = false
  }
}

function promptRestoreBackup(record: BackupRecord): void {
  backupToRestore.value = record
}

async function confirmRestoreBackup(): Promise<void> {
  if (!backupToRestore.value) return
  dataBusy.value = true
  dataError.value = null
  try {
    await api.restoreBackup(backupToRestore.value.name)
    dataMessage.value = 'Backup restored. Reloading the application…'
    window.location.assign('/')
  } catch (cause) {
    dataError.value = errorText(cause)
    dataBusy.value = false
  }
}

async function importBundle(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  dataBusy.value = true
  dataError.value = null
  try {
    const imported = await api.importExportBundle(await file.arrayBuffer())
    dataMessage.value = `Imported “${imported.world.name}”.`
  } catch (cause) {
    dataError.value = errorText(cause)
  } finally {
    input.value = ''
    dataBusy.value = false
  }
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

function errorText(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause)
}

async function save(): Promise<void> {
  saved.value = false
  saving.value = true
  try {
    await settings.save()
    saved.value = true
    setTimeout(() => {
      saved.value = false
    }, 2500)
  } catch {
    saved.value = false
  } finally {
    saving.value = false
  }
}

async function testConnection(): Promise<void> {
  try {
    // Silently save any pending draft edits so the backend tests the current form inputs
    await settings.save()
    if (settings.error) return
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

function changeProvider(targetName: string, provider: unknown): void {
  if (!provider) return
  settings.changeProvider(targetName, provider as ProviderTarget['provider'])
  saved.value = false
  if (provider === 'ollama') void refreshOllamaAccount()
}

async function refreshOllamaAccount(): Promise<void> {
  if (!ollamaTarget.value) return
  await settings.loadOllamaAccount(ollamaTarget.value.base_url)
}

function changePrimary(role: string, targetName: unknown): void {
  if (!targetName) return
  settings.setPrimaryTarget(role, String(targetName))
  saved.value = false
}

function availableFallbacks(role: string): string[] {
  const primary = settings.providerSettings?.role_routes[role]?.primary_target
  return targetNames.value.filter((name) => name !== primary)
}

function fallbackSummary(role: string): string {
  const selected = settings.providerSettings?.role_routes[role]?.fallback_targets ?? []
  if (!selected.length) return 'None (primary engine only)'
  if (selected.length <= 2) return selected.join(', ')
  return `${selected.length} backup engines configured`
}

function getProviderIcon(provider: ProviderTarget['provider']): string {
  if (provider === 'ollama') return '🦙'
  if (provider === 'gemini') return '✦'
  if (provider === 'openrouter') return '🌐'
  return '🤖'
}

function formatProviderName(provider: ProviderTarget['provider']): string {
  if (provider === 'ollama') return 'Ollama'
  if (provider === 'gemini') return 'Gemini'
  if (provider === 'openrouter') return 'OpenRouter'
  return provider
}
</script>

<template>
  <div class="providers-page">
    <!-- Top Bar & Global Actions -->
    <header class="page-heading">
      <div class="heading-content">
        <p class="eyebrow">Settings</p>
        <h1>Story Preferences & Engines</h1>
        <p class="lede">Configure story generation engines, narrative detail, backups, and story imports.</p>
      </div>
      <div class="top-actions-bar">
        <button
          type="button"
          class="secondary test-btn"
          :disabled="settings.testing || settings.loading || saving"
          @click="testConnection"
        >
          <span v-if="settings.testing" class="spin-dot" />
          <span v-else>⚡</span>
          <span>{{ settings.testing ? 'Testing…' : 'Test Connections' }}</span>
        </button>
        <button
          type="button"
          class="save-btn"
          :class="{ 'is-saved': saved }"
          :disabled="settings.loading || saving || !settings.providerSettings"
          @click="save"
        >
          <span v-if="saving" class="spin-dot" />
          <span v-else-if="saved">✓</span>
          <span v-else>💾</span>
          <span>{{ saving ? 'Saving…' : saved ? 'Saved!' : 'Save All Settings' }}</span>
        </button>
      </div>
    </header>

    <!-- Error & Notification Banners -->
    <div v-if="settings.error" class="error-box" role="alert">
      <span>⚠️ {{ settings.error }}</span>
    </div>
    <div v-if="dataMessage" class="notice-box" role="status" aria-live="polite">
      <span>{{ dataMessage }}</span>
      <button type="button" class="notice-close" aria-label="Dismiss notice" @click="dataMessage = null">✕</button>
    </div>
    <div v-if="dataError" class="error-box" role="alert">
      <span>⚠️ {{ dataError }}</span>
      <button type="button" class="notice-close" aria-label="Dismiss error" @click="dataError = null">✕</button>
    </div>

    <!-- Loading Placeholder -->
    <div v-if="settings.loading && !settings.providerSettings" class="card loading-card">
      <span class="spin-dot" />
      <span>Loading configuration…</span>
    </div>

    <div v-else-if="settings.providerSettings" class="settings-content-flow">
      <!-- SECTION 1: Narrative & Privacy Policy -->
      <section class="card settings-card policy-section">
        <div class="card-header-row">
          <div>
            <p class="eyebrow">Generation</p>
            <h3>Narrative & Privacy Preferences</h3>
            <p class="muted small-copy">Story detail level, narrative language, and offline privacy settings.</p>
          </div>
        </div>

        <div class="runtime-grid">
          <!-- Story Generation Mode -->
          <div class="policy-card">
            <div class="policy-card-header">
              <span class="policy-icon">⚡</span>
              <div>
                <h4 class="policy-card-title">Story Detail & Pacing</h4>
                <p class="policy-card-desc">Balance between rich narrative depth and generation speed</p>
              </div>
            </div>
            <div class="segmented-control">
              <button
                type="button"
                class="seg-item"
                :class="{ active: settings.mode === 'quality' }"
                @click="settings.mode = 'quality'; saved = false"
              >
                <span class="seg-badge">✨</span>
                <div class="seg-text">
                  <strong>Quality</strong>
                  <small>Rich prose & deep scene details</small>
                </div>
              </button>
              <button
                type="button"
                class="seg-item"
                :class="{ active: settings.mode === 'fast' }"
                @click="settings.mode = 'fast'; saved = false"
              >
                <span class="seg-badge">🚀</span>
                <div class="seg-text">
                  <strong>Fast</strong>
                  <small>Quick & streamlined scenes</small>
                </div>
              </button>
            </div>
          </div>

          <!-- Story Language -->
          <div class="policy-card">
            <div class="policy-card-header">
              <span class="policy-icon">🌐</span>
              <div>
                <h4 class="policy-card-title">Default Story Language</h4>
                <p class="policy-card-desc">Narrative language for newly forged story worlds</p>
              </div>
            </div>
            <div class="segmented-control">
              <button
                type="button"
                class="seg-item"
                :class="{ active: settings.storyLanguage === 'en' }"
                @click="settings.storyLanguage = 'en'; saved = false"
              >
                <span class="seg-badge">🇺🇸</span>
                <div class="seg-text">
                  <strong>English</strong>
                  <small>Default narrative</small>
                </div>
              </button>
              <button
                type="button"
                class="seg-item"
                :class="{ active: settings.storyLanguage === 'vi' }"
                @click="settings.storyLanguage = 'vi'; saved = false"
              >
                <span class="seg-badge">🇻🇳</span>
                <div class="seg-text">
                  <strong>Tiếng Việt</strong>
                  <small>Văn phong thuần Việt</small>
                </div>
              </button>
            </div>
          </div>

          <!-- Cloud Assistance Privacy Switch -->
          <div class="policy-card full-span">
            <div class="cloud-switch-row">
              <div class="cloud-switch-info">
                <div class="cloud-title-wrap">
                  <span class="policy-icon">☁️</span>
                  <h4>Cloud Engine Assistance</h4>
                  <VnBadge :variant="settings.allowCloud ? 'brand' : 'neutral'">
                    {{ settings.allowCloud ? 'Cloud Enabled 🌐' : '100% Offline & Private 🔒' }}
                  </VnBadge>
                </div>
                <p class="muted small-copy">
                  When turned off, cloud engines (Gemini, OpenRouter) remain inactive and all stories generate locally via Ollama, keeping your text strictly on this machine.
                </p>
              </div>
              <label class="switch-toggle" aria-label="Toggle cloud engine assistance">
                <input
                  v-model="settings.allowCloud"
                  type="checkbox"
                  @change="saved = false"
                />
                <span class="slider" />
              </label>
            </div>
          </div>
        </div>
      </section>

      <!-- SECTION 2: Story Engines -->
      <section class="card settings-card targets-section">
        <div class="card-header-row">
          <div>
            <p class="eyebrow">Engines</p>
            <h3>Configured Story Engines</h3>
            <p class="muted small-copy">Manage local engine connections (Ollama) and cloud services.</p>
          </div>
        </div>

        <!-- Add Target Toolbar -->
        <div class="add-target-toolbar">
          <div class="add-target-info">
            <span class="toolbar-icon">➕</span>
            <div>
              <strong>Add a Story Engine</strong>
              <p class="muted small-copy">Configure a new engine endpoint to craft dialogue, plot, or character lore.</p>
            </div>
          </div>
          <div class="add-target-controls">
            <VnSelect
              v-model="newProvider"
              class="provider-dropdown"
              aria-label="Provider for new target"
              :options="providerOptions"
            />
            <button type="button" class="add-btn" @click="addTarget">
              <span>+ Add Engine</span>
            </button>
          </div>
        </div>

        <!-- Target Cards Grid -->
        <div class="targets-grid">
          <div
            v-for="(target, targetName) in settings.providerSettings.targets"
            :key="targetName"
            class="target-card"
            :class="`is-${target.provider}`"
          >
            <!-- Target Card Top Bar -->
            <div class="target-top-bar">
              <div class="target-identity">
                <div class="provider-pill" :class="target.provider">
                  <span>{{ getProviderIcon(target.provider) }}</span>
                  <span>{{ formatProviderName(target.provider) }}</span>
                </div>
                <div class="target-rename-wrap">
                  <span class="target-tag-label">Name:</span>
                  <input
                    :value="targetName"
                    class="target-rename-input"
                    maxlength="160"
                    autocomplete="off"
                    title="Click to rename engine"
                    @input="clearTargetNameError"
                    @change="renameTarget(targetName, $event)"
                  />
                </div>
              </div>
              <button
                class="target-remove-btn"
                type="button"
                :disabled="targetNames.length <= 1"
                :title="targetNames.length <= 1 ? 'At least one engine is required' : `Remove ${targetName}`"
                @click="removeTarget(targetName)"
              >
                <span>✕</span>
                <span>Remove</span>
              </button>
            </div>

            <!-- Target Form Body -->
            <div class="target-body">
              <div class="field-row two-cols">
                <div class="form-item">
                  <label class="item-label">Engine Provider</label>
                  <VnSelect
                    v-model="target.provider"
                    :options="targetProviderOptions"
                    @change="changeProvider(targetName, $event)"
                  />
                </div>
                <div class="form-item">
                  <label class="item-label">Model Name</label>
                  <ProviderModelField v-model="target.model" :target="target" @update:model-value="saved = false" />
                </div>
              </div>

              <!-- Ollama-specific configuration -->
              <div v-if="target.provider === 'ollama'" class="field-row three-cols">
                <div class="form-item">
                  <label class="item-label">Local Server Address</label>
                  <input
                    v-model="target.base_url"
                    placeholder="http://localhost:11434/api"
                    autocomplete="off"
                    @input="saved = false"
                  />
                </div>
                <div class="form-item">
                  <label class="item-label">Ollama Account</label>
                  <div class="account-control-group">
                    <input :value="ollamaAccountText" disabled aria-label="Ollama account" />
                    <button class="secondary small-btn" type="button" :disabled="settings.ollamaAccountLoading" @click="refreshOllamaAccount">
                      {{ settings.ollamaAccountLoading ? '…' : '↻' }}
                    </button>
                  </div>
                </div>
                <div class="form-item">
                  <label class="item-label">Response Timeout (seconds)</label>
                  <input v-model.number="target.timeout_seconds" type="number" min="1" max="600" @input="saved = false" />
                </div>
              </div>

              <!-- Cloud-specific configuration (Gemini, OpenRouter) -->
              <div v-else class="field-row two-cols">
                <div class="form-item">
                  <label class="item-label">
                    API Key Variable Name
                    <span class="sub-hint">(Environment variable in .env)</span>
                  </label>
                  <input
                    v-model="target.api_key_env"
                    autocomplete="off"
                    placeholder="e.g. GEMINI_API_KEY"
                    @input="saved = false"
                  />
                </div>
                <div class="form-item">
                  <label class="item-label">Response Timeout (seconds)</label>
                  <input v-model.number="target.timeout_seconds" type="number" min="1" max="600" @input="saved = false" />
                </div>
              </div>

              <div class="target-security-note">
                <span v-if="target.provider === 'ollama'">
                  💡 Ollama runs completely offline on your computer. Ensure your Ollama app or service is running.
                </span>
                <span v-else>
                  🔒 Secrets stay safe in your local configuration. Only the variable name is stored here.
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- Connection Test Results -->
        <div v-if="settings.connectivity.length" class="connectivity-results-box">
          <h4 class="conn-header">Engine Connection Status</h4>
          <div class="connectivity-grid">
            <div
              v-for="result in settings.connectivity"
              :key="`${result.provider}-${result.model}`"
              class="conn-pill"
              :class="result.reachable ? 'is-ok' : 'is-error'"
            >
              <span class="conn-icon">{{ result.reachable ? '✓' : '✕' }}</span>
              <div class="conn-details">
                <strong>{{ result.provider }} / {{ result.model }}</strong>
                <small>{{ result.reachable ? 'Connected & Ready' : (result.message || 'Connection failed') }}</small>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- SECTION 3: Story Role Assignments -->
      <section class="card settings-card routing-section">
        <div class="card-header-row">
          <div>
            <p class="eyebrow">Creative Roles</p>
            <h3>Story Role Assignments</h3>
            <p class="muted small-copy">Choose which engine handles each creative aspect of your story.</p>
          </div>
        </div>

        <div class="roles-matrix">
          <div v-for="role in roles" :key="role.id" class="role-matrix-row">
            <!-- Role Info -->
            <div class="role-info-col">
              <div class="role-icon-box">
                <span>{{ roleDescriptions[role.id]?.icon || '⚙️' }}</span>
              </div>
              <div class="role-text-box">
                <h4 class="role-name">{{ roleDescriptions[role.id]?.name || role.label }}</h4>
                <p class="role-summary">{{ roleDescriptions[role.id]?.desc }}</p>
              </div>
            </div>

            <!-- Primary Target Selection -->
            <div class="role-primary-col">
              <label class="item-label">Primary Engine</label>
              <VnSelect
                v-model="settings.providerSettings.role_routes[role.id].primary_target"
                class="primary-select"
                :options="targetNames.map((targetName) => ({
                  value: targetName,
                  label: targetName,
                  tag: settings.providerSettings?.targets[targetName]?.provider,
                }))"
                @change="changePrimary(role.id, $event)"
              />
            </div>

            <!-- Fallbacks Dropdown -->
            <div class="role-fallback-col">
              <label class="item-label">Backup Engines (Optional)</label>
              <VnSelect
                v-model="settings.providerSettings.role_routes[role.id].fallback_targets"
                multiple
                class="fallback-select"
                placeholder="None (primary engine only)"
                :summary-format="() => fallbackSummary(role.id)"
                :options="availableFallbacks(role.id).map((targetName) => ({
                  value: targetName,
                  label: targetName,
                  tag: settings.providerSettings?.targets[targetName]?.provider,
                }))"
                @toggle-option="(opt, selected) => {
                  settings.toggleFallback(role.id, String(opt.value), selected)
                  saved = false
                }"
              />
            </div>
          </div>
        </div>
      </section>

      <!-- SECTION 4: Story Data & Backups -->
      <section class="card settings-card data-management-section">
        <div class="card-header-row">
          <div>
            <p class="eyebrow">Storage</p>
            <h3>Story Data & Backups</h3>
            <p class="muted small-copy">Exported story files, playthrough progress, and complete archives stay safely on this machine.</p>
          </div>
        </div>

        <div class="data-panels-grid">
          <!-- Story Import Card -->
          <div class="data-subcard import-card">
            <div class="subcard-header">
              <div class="subcard-title-group">
                <span class="subcard-icon">📦</span>
                <div>
                  <h4 class="subcard-title">Import Playthrough</h4>
                  <p class="subcard-desc">Load an exported story file (<code>.json</code>) to continue your journey.</p>
                </div>
              </div>
            </div>
            <div class="import-action-box">
              <label class="file-upload-btn" :class="{ disabled: dataBusy }">
                <span>📂</span>
                <span>{{ dataBusy ? 'Importing…' : 'Select Story File (.json)' }}</span>
                <input
                  type="file"
                  accept="application/json,.json"
                  :disabled="dataBusy"
                  class="hidden-file-input"
                  @change="importBundle"
                />
              </label>
            </div>
          </div>

          <!-- Database Backups Card -->
          <div class="data-subcard backup-card">
            <div class="subcard-header">
              <div class="subcard-title-group">
                <span class="subcard-icon">💾</span>
                <div>
                  <h4 class="subcard-title">Story Archive Backups</h4>
                  <p class="subcard-desc">Complete snapshots of all story worlds, timelines, and playthrough progress.</p>
                </div>
              </div>
              <button
                type="button"
                class="secondary create-backup-btn"
                :disabled="dataBusy"
                @click="createBackup"
              >
                <span>+ Create Backup</span>
              </button>
            </div>

            <!-- Integrity status -->
            <div class="integrity-indicator" :class="{ 'is-ok': integrity?.ok, 'is-bad': integrity && !integrity.ok }">
              <span class="integrity-dot" />
              <span>Archive Health: {{ integrity?.message ?? 'checking…' }}</span>
            </div>

            <!-- Backups list -->
            <div v-if="backups.length" class="backups-list">
              <div v-for="record in backups" :key="record.name" class="backup-item-row">
                <div class="backup-meta">
                  <strong class="backup-name">{{ record.name }}</strong>
                  <span class="backup-details">
                    {{ formatBytes(record.size_bytes) }} · {{ new Date(record.modified_at).toLocaleString() }}
                  </span>
                </div>
                <button
                  type="button"
                  class="danger small-btn restore-btn"
                  :disabled="dataBusy || !record.integrity.ok"
                  @click="promptRestoreBackup(record)"
                >
                  Restore
                </button>
              </div>
            </div>
            <p v-else class="muted empty-backups-text">No backups have been created yet.</p>
          </div>
        </div>
      </section>
    </div>

    <!-- Confirm Restore Database Backup Modal -->
    <VnConfirmModal
      :open="Boolean(backupToRestore)"
      title="Restore Database Backup?"
      :message="backupToRestore ? `Are you sure you want to restore snapshot “${backupToRestore.name}”? All current database content and active progress will be replaced.` : ''"
      confirm-text="Restore Database"
      cancel-text="Cancel"
      variant="danger"
      :busy="dataBusy"
      @confirm="confirmRestoreBackup"
      @cancel="backupToRestore = null"
    />
  </div>
</template>

<style scoped>
.providers-page {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.lede {
  max-width: 46rem;
  margin-bottom: 0;
  color: var(--muted);
  line-height: 1.6;
}

.page-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.5rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.heading-content {
  flex: 1;
  min-width: 18rem;
}

.top-actions-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-shrink: 0;
}

.test-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  min-width: 10.5rem;
  padding: 0.65rem 1.1rem;
  font-size: 0.86rem;
  font-weight: 600;
}

.save-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  min-width: 10.5rem;
  padding: 0.65rem 1.25rem;
  font-size: 0.88rem;
  font-weight: 600;
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
  transition: all 200ms ease;
}

.save-btn.is-saved {
  background: linear-gradient(135deg, #10b981, #059669);
  box-shadow: 0 4px 14px rgba(16, 185, 129, 0.35);
}

.loading-card {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.85rem;
  padding: 3rem;
  color: var(--muted);
  font-size: 0.95rem;
}

.spin-dot {
  width: 0.85rem;
  height: 0.85rem;
  border-radius: 9999px;
  border: 2px solid #818cf8;
  border-top-color: transparent;
  animation: spin 800ms linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.settings-content-flow {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.settings-card {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  padding: 1.5rem;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  backdrop-filter: blur(16px);
}

.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.card-header-row h3 {
  margin: 0.2rem 0 0.15rem;
  font-size: 1.25rem;
  color: #fff;
}

/* SECTION 1: Runtime Grid */
.runtime-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.policy-card {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  padding: 1.15rem;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--radius-md);
}

.policy-card.full-span {
  grid-column: 1 / -1;
}

.policy-card-header {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
}

.policy-icon {
  font-size: 1.35rem;
  flex-shrink: 0;
  margin-top: 0.1rem;
}

.policy-card-title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 700;
  color: #f8fafc;
}

.policy-card-desc {
  margin: 0.15rem 0 0;
  font-size: 0.78rem;
  color: var(--muted);
}

.segmented-control {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.5rem;
}

.seg-item {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.65rem 0.85rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-sm);
  color: #cbd5e1;
  box-shadow: none;
  text-align: left;
  cursor: pointer;
  transition: all 160ms ease;
}

.seg-item:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(99, 102, 241, 0.3);
  color: #fff;
  transform: translateY(-1px);
}

.seg-item.active {
  background: rgba(99, 102, 241, 0.15);
  border-color: #6366f1;
  color: #fff;
  box-shadow: 0 0 12px rgba(99, 102, 241, 0.25);
}

.seg-badge {
  font-size: 1.15rem;
}

.seg-text {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  min-width: 0;
}

.seg-text strong {
  font-size: 0.86rem;
}

.seg-text small {
  font-size: 0.7rem;
  color: var(--muted);
}

.cloud-switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.cloud-switch-info {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  max-width: 50rem;
}

.cloud-title-wrap {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-wrap: wrap;
}

.cloud-title-wrap h4 {
  margin: 0;
  font-size: 1rem;
  color: #f8fafc;
}

/* Toggle Switch */
.switch-toggle {
  position: relative;
  display: inline-block;
  width: 3.2rem;
  height: 1.8rem;
  flex-shrink: 0;
  cursor: pointer;
}

.switch-toggle input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 9999px;
  transition: 200ms;
}

.slider::before {
  position: absolute;
  content: '';
  height: 1.3rem;
  width: 1.3rem;
  left: 0.2rem;
  bottom: 0.2rem;
  background-color: #cbd5e1;
  border-radius: 9999px;
  transition: 200ms cubic-bezier(0.16, 1, 0.3, 1);
}

.switch-toggle input:checked + .slider {
  background-color: #6366f1;
  border-color: #818cf8;
  box-shadow: 0 0 12px rgba(99, 102, 241, 0.4);
}

.switch-toggle input:checked + .slider::before {
  transform: translateX(1.4rem);
  background-color: #fff;
}

/* SECTION 2: Model Targets */
.add-target-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.85rem 1.15rem;
  background: rgba(99, 102, 241, 0.06);
  border: 1px dashed rgba(99, 102, 241, 0.3);
  border-radius: var(--radius-md);
  flex-wrap: wrap;
}

.add-target-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.toolbar-icon {
  font-size: 1.25rem;
}

.add-target-controls {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.provider-dropdown {
  min-width: 13rem;
}

.add-btn {
  padding: 0.65rem 1.1rem;
  font-size: 0.85rem;
  white-space: nowrap;
}

.targets-grid {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.target-card {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.15rem;
  background: rgba(13, 16, 26, 0.7);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  transition: border-color 180ms ease;
}

.target-card:hover {
  border-color: rgba(99, 102, 241, 0.35);
}

.target-top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.target-identity {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  flex-wrap: wrap;
  flex: 1;
}

.provider-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.3rem 0.65rem;
  border-radius: var(--radius-sm);
  font-size: 0.82rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.provider-pill.ollama {
  background: rgba(16, 185, 129, 0.12);
  border: 1px solid rgba(16, 185, 129, 0.35);
  color: #34d399;
}

.provider-pill.gemini {
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(99, 102, 241, 0.35);
  color: #a5b4fc;
}

.provider-pill.openrouter {
  background: rgba(236, 72, 153, 0.12);
  border: 1px solid rgba(236, 72, 153, 0.35);
  color: #f472b6;
}

.target-rename-wrap {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.target-tag-label {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--muted);
}

.target-rename-input {
  max-width: 13rem;
  font-weight: 700;
  font-size: 0.9rem;
  padding: 0.35rem 0.65rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: var(--radius-sm);
  color: #fff;
}

.target-rename-input:focus {
  border-color: #6366f1;
  background: rgba(18, 22, 34, 0.95);
}

.target-remove-btn {
  padding: 0.4rem 0.8rem;
  font-size: 0.78rem;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
  box-shadow: none;
}

.target-remove-btn:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.25);
  border-color: #ef4444;
  color: #fff;
}

.target-remove-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.target-body {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.field-row {
  display: grid;
  gap: 0.85rem;
}

.field-row.two-cols {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.6fr);
}

.field-row.three-cols {
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1.2fr) minmax(0, 0.8fr);
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.item-label {
  font-size: 0.78rem;
  font-weight: 700;
  color: #cbd5e1;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.sub-hint {
  font-size: 0.72rem;
  font-weight: 500;
  color: var(--muted);
}

.account-control-group {
  display: flex;
  gap: 0.45rem;
}

.account-control-group input {
  flex: 1;
  font-size: 0.82rem;
  color: #94a3b8;
}

.account-control-group button {
  padding: 0.4rem 0.75rem;
}

.target-security-note {
  font-size: 0.78rem;
  color: var(--muted);
  line-height: 1.4;
  padding-top: 0.35rem;
}

.target-security-note code {
  color: #cbd5e1;
  background: rgba(255, 255, 255, 0.06);
  padding: 0.15rem 0.35rem;
  border-radius: 0.3rem;
}

/* Connectivity Results */
.connectivity-results-box {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.conn-header {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
}

.connectivity-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
  gap: 0.65rem;
}

.conn-pill {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.65rem 0.85rem;
  border-radius: var(--radius-sm);
  font-size: 0.82rem;
}

.conn-pill.is-ok {
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.28);
  color: #34d399;
}

.conn-pill.is-error {
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.28);
  color: #fca5a5;
}

.conn-icon {
  font-size: 1.1rem;
  font-weight: 800;
}

.conn-details {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  min-width: 0;
}

.conn-details strong {
  font-size: 0.84rem;
  color: #f8fafc;
}

.conn-details small {
  font-size: 0.74rem;
  color: #94a3b8;
}

/* SECTION 3: Role Routing */
.roles-matrix {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.role-matrix-row {
  display: grid;
  grid-template-columns: minmax(14rem, 1.3fr) minmax(12rem, 1fr) minmax(14rem, 1.2fr);
  gap: 1.25rem;
  align-items: center;
  padding: 0.85rem 1.15rem;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--radius-md);
  transition: all 160ms ease;
}

.role-matrix-row:hover {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(99, 102, 241, 0.25);
}

.role-info-col {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.role-icon-box {
  width: 2.4rem;
  height: 2.4rem;
  border-radius: 0.6rem;
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(99, 102, 241, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
  flex-shrink: 0;
}

.role-text-box {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.role-name {
  margin: 0;
  font-size: 0.92rem;
  font-weight: 700;
  color: #f8fafc;
}

.role-summary {
  margin: 0;
  font-size: 0.74rem;
  color: var(--muted);
  line-height: 1.35;
}

.role-primary-col,
.role-fallback-col {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.primary-select,
.fallback-select {
  width: 100%;
}

/* Data Management & Backups */
.data-panels-grid {
  display: grid;
  grid-template-columns: minmax(18rem, 1fr) minmax(22rem, 1.4fr);
  gap: 1.25rem;
}

.data-subcard {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.25rem;
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-md);
  background: rgba(13, 16, 26, 0.7);
}

.subcard-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.85rem;
}

.subcard-title-group {
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
}

.subcard-icon {
  font-size: 1.5rem;
  flex-shrink: 0;
  line-height: 1;
}

.subcard-title {
  margin: 0 0 0.25rem;
  font-size: 0.95rem;
  font-weight: 700;
  color: #fff;
}

.subcard-desc {
  margin: 0;
  font-size: 0.8rem;
  color: var(--muted);
  line-height: 1.4;
}

.import-action-box {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 1.75rem 1rem;
  border: 2px dashed rgba(99, 102, 241, 0.35);
  border-radius: var(--radius-md);
  background: rgba(99, 102, 241, 0.04);
  transition: all 160ms ease;
}

.import-action-box:hover {
  border-color: var(--brand);
  background: rgba(99, 102, 241, 0.08);
}

.file-upload-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.65rem 1.25rem;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--brand), #4338ca);
  color: #fff;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.88rem;
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
  transition: all 160ms ease;
  user-select: none;
}

.file-upload-btn:hover:not(.disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.45);
}

.file-upload-btn.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.hidden-file-input {
  display: none;
}

.create-backup-btn {
  padding: 0.45rem 0.85rem;
  font-size: 0.8rem;
  white-space: nowrap;
}

.integrity-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.45rem 0.75rem;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.04);
  font-size: 0.8rem;
  color: var(--muted);
}

.integrity-indicator.is-ok {
  color: #34d399;
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.integrity-indicator.is-bad {
  color: #f87171;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.integrity-dot {
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 9999px;
  background: currentColor;
  flex-shrink: 0;
}

.backups-list {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  max-height: 15rem;
  overflow-y: auto;
  padding-right: 0.25rem;
}

.backup-item-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.65rem 0.85rem;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  background: rgba(18, 22, 34, 0.8);
  transition: border-color 140ms ease;
}

.backup-item-row:hover {
  border-color: rgba(99, 102, 241, 0.3);
}

.backup-meta {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.backup-name {
  font-size: 0.84rem;
  font-weight: 600;
  color: #fff;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.backup-details {
  font-size: 0.74rem;
  color: var(--muted);
}

.restore-btn {
  padding: 0.35rem 0.75rem;
  font-size: 0.76rem;
  flex-shrink: 0;
}

.empty-backups-text {
  padding: 1.5rem 0;
  margin: 0;
  text-align: center;
  font-size: 0.84rem;
}

.notice-close {
  all: unset;
  cursor: pointer;
  color: var(--muted);
  padding: 0.2rem 0.5rem;
  font-size: 0.85rem;
  margin-left: auto;
  border-radius: var(--radius-sm);
}

.notice-close:hover {
  color: #fff;
}

@media (max-width: 960px) {
  .runtime-grid,
  .data-panels-grid {
    grid-template-columns: 1fr;
  }

  .role-matrix-row {
    grid-template-columns: 1fr;
    gap: 0.85rem;
  }

  .field-row.two-cols,
  .field-row.three-cols {
    grid-template-columns: 1fr;
  }

  .add-target-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .add-target-controls {
    flex-direction: column;
    align-items: stretch;
  }

  .provider-dropdown {
    width: 100%;
  }
}
</style>
