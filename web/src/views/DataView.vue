<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { BackupRecord } from '@/api/types'

const backups = ref<BackupRecord[]>([])
const integrity = ref<{ ok: boolean; message: string } | null>(null)
const busy = ref(false)
const message = ref<string | null>(null)
const error = ref<string | null>(null)
const rating = ref(5)
const category = ref('general')
const comment = ref('')

onMounted(() => void refresh())

async function refresh(): Promise<void> {
  busy.value = true
  error.value = null
  try {
    const [records, report] = await Promise.all([api.listBackups(), api.databaseIntegrity()])
    backups.value = records
    integrity.value = report
  } catch (cause) {
    error.value = errorText(cause)
  } finally {
    busy.value = false
  }
}

async function createBackup(): Promise<void> {
  busy.value = true
  error.value = null
  try {
    const report = await api.createBackup()
    message.value = `Backup created (${formatBytes(report.size_bytes)}).`
    await refresh()
  } catch (cause) {
    error.value = errorText(cause)
  } finally {
    busy.value = false
  }
}

async function restoreBackup(record: BackupRecord): Promise<void> {
  if (!window.confirm(`Restore ${record.name}? Current database contents will be replaced.`)) return
  busy.value = true
  error.value = null
  try {
    await api.restoreBackup(record.name)
    message.value = 'Backup restored. Reloading the application…'
    window.location.assign('/')
  } catch (cause) {
    error.value = errorText(cause)
    busy.value = false
  }
}

async function importBundle(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  busy.value = true
  error.value = null
  try {
    const imported = await api.importExportBundle(await file.arrayBuffer())
    message.value = `Imported “${imported.world.name}”.`
  } catch (cause) {
    error.value = errorText(cause)
  } finally {
    input.value = ''
    busy.value = false
  }
}

async function sendFeedback(): Promise<void> {
  busy.value = true
  error.value = null
  try {
    await api.submitFeedback({ rating: rating.value, category: category.value, comment: comment.value })
    comment.value = ''
    message.value = 'Feedback saved locally. Thank you.'
  } catch (cause) {
    error.value = errorText(cause)
  } finally {
    busy.value = false
  }
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

function errorText(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause)
}
</script>

<template>
  <section class="page-heading">
    <div>
      <p class="eyebrow">Local data</p>
      <h1>Backup, restore and feedback</h1>
      <p class="muted">Portable story bundles and full database backups stay on this machine.</p>
    </div>
  </section>

  <div v-if="error" class="error-box" role="alert">{{ error }}</div>
  <div v-if="message" class="notice-box" aria-live="polite">{{ message }}</div>

  <div class="data-grid">
    <section class="panel">
      <p class="eyebrow">Portable stories</p>
      <h2>Import a playthrough</h2>
      <p class="muted">Choose a checksummed <code>.json</code> bundle exported by this application.</p>
      <label class="file-button" :class="{ disabled: busy }">
        Import bundle
        <input type="file" accept="application/json,.json" :disabled="busy" @change="importBundle">
      </label>
    </section>

    <section class="panel">
      <div class="panel-heading">
        <div>
          <p class="eyebrow">Database</p>
          <h2>Full backups</h2>
        </div>
        <button type="button" :disabled="busy" @click="createBackup">Create backup</button>
      </div>
      <p class="integrity" :class="{ healthy: integrity?.ok }">
        Integrity: {{ integrity?.message ?? 'checking…' }}
      </p>
      <div v-if="backups.length" class="backup-list">
        <div v-for="record in backups" :key="record.name" class="backup-row">
          <div>
            <strong>{{ record.name }}</strong>
            <small>{{ formatBytes(record.size_bytes) }} · {{ new Date(record.modified_at).toLocaleString() }}</small>
          </div>
          <button class="danger" type="button" :disabled="busy || !record.integrity.ok" @click="restoreBackup(record)">
            Restore
          </button>
        </div>
      </div>
      <p v-else class="muted">No backups have been created yet.</p>
    </section>

    <section class="panel feedback-panel">
      <p class="eyebrow">Alpha feedback</p>
      <h2>Tell us what needs attention</h2>
      <div class="feedback-fields">
        <label>Rating
          <select v-model.number="rating" :disabled="busy">
            <option v-for="value in 5" :key="value" :value="value">{{ value }}/5</option>
          </select>
        </label>
        <label>Category
          <select v-model="category" :disabled="busy">
            <option value="general">General</option>
            <option value="story">Story quality</option>
            <option value="memory">Memory</option>
            <option value="ui">Interface</option>
            <option value="bug">Bug</option>
          </select>
        </label>
      </div>
      <label>Comment
        <textarea v-model="comment" rows="5" maxlength="4000" :disabled="busy" placeholder="What happened, and what did you expect?" />
      </label>
      <button type="button" :disabled="busy || !comment.trim()" @click="sendFeedback">Send feedback</button>
    </section>
  </div>
</template>

<style scoped>
.data-grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.feedback-panel {
  grid-column: 1 / -1;
}

.panel-heading,
.backup-row,
.feedback-fields {
  display: flex;
  gap: 1rem;
  align-items: center;
  justify-content: space-between;
}

.panel-heading h2,
.panel h2 {
  margin-bottom: 0.5rem;
}

.file-button {
  display: inline-block;
  border-radius: 0.55rem;
  padding: 0.7rem 1rem;
  background: var(--accent);
  color: #fff;
  cursor: pointer;
}

.file-button.disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.file-button input {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
}

.integrity {
  color: #9a3e48;
}

.integrity.healthy {
  color: var(--green);
}

.backup-list {
  display: grid;
  gap: 0.7rem;
  margin-top: 1rem;
}

.backup-row {
  padding-top: 0.7rem;
  border-top: 1px solid var(--line);
}

.backup-row small {
  display: block;
  margin-top: 0.25rem;
  color: var(--muted);
}

.feedback-fields label,
.feedback-panel > label {
  display: grid;
  flex: 1;
  gap: 0.4rem;
  margin-bottom: 1rem;
  font-weight: 700;
}

select,
textarea {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 0.55rem;
  padding: 0.7rem;
  background: #fff;
}

@media (max-width: 700px) {
  .data-grid {
    grid-template-columns: 1fr;
  }

  .feedback-panel {
    grid-column: auto;
  }

  .panel-heading,
  .backup-row,
  .feedback-fields {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
