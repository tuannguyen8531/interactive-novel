<script setup lang="ts">
import { ref, computed } from 'vue'
import VnBadge from './VnBadge.vue'
import type { CharacterView } from '@/api/types'

const props = defineProps<{
  characters: CharacterView[]
  selectedId?: string | null
}>()

const emit = defineEmits<{
  (event: 'select', characterId: string): void
}>()

const sortedCharacters = computed(() => {
  return [...props.characters].sort((a, b) => {
    if (a.role === 'player' && b.role !== 'player') return -1
    if (a.role !== 'player' && b.role === 'player') return 1
    return 0
  })
})

const defaultId = computed(() => {
  const player = sortedCharacters.value.find((c) => c.role === 'player')
  return player?.id || sortedCharacters.value[0]?.id || ''
})

const internalSelectedId = ref<string>('')

const activeId = computed(() => props.selectedId || internalSelectedId.value || defaultId.value)

const activeCharacter = computed(() => {
  return (
    sortedCharacters.value.find((c) => c.id === activeId.value) ||
    sortedCharacters.value.find((c) => c.role === 'player') ||
    sortedCharacters.value[0]
  )
})

function selectCharacter(id: string): void {
  internalSelectedId.value = id
  emit('select', id)
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

function charRole(char: CharacterView | undefined): string {
  const role = char?.public_profile?.role
  return typeof role === 'string' ? role : ''
}

function charBackground(char: CharacterView | undefined): string {
  const bg = char?.public_profile?.background
  return typeof bg === 'string' ? bg : ''
}

function charAppearance(char: CharacterView | undefined): string {
  const app = char?.public_profile?.appearance
  return typeof app === 'string' ? app : ''
}

function charVoice(char: CharacterView | undefined): string {
  const voice = char?.public_profile?.voice
  return typeof voice === 'string' ? voice : ''
}

function charTraits(char: CharacterView | undefined): string[] {
  const traits = char?.public_profile?.traits
  return Array.isArray(traits) ? traits.filter((t): t is string => typeof t === 'string') : []
}

function charValues(char: CharacterView | undefined): string[] {
  const values = char?.public_profile?.values
  return Array.isArray(values) ? values.filter((v): v is string => typeof v === 'string') : []
}

function charLocation(char: CharacterView | undefined): string {
  const loc = char?.state?.location_id
  return typeof loc === 'string' ? loc.replaceAll('_', ' ') : ''
}

function charEmotionalState(char: CharacterView | undefined): string {
  const emo = char?.state?.emotional_state
  return typeof emo === 'string' ? emo : ''
}

function charPhysicalCondition(char: CharacterView | undefined): string {
  const phys = char?.state?.physical_condition
  return typeof phys === 'string' ? phys : ''
}
</script>

<template>
  <div v-if="characters.length > 0" class="character-slider-wrapper">
    <!-- Character portrait avatar tabs -->
    <div class="portraits-bar">
      <div
        v-for="char in sortedCharacters"
        :key="char.id"
        class="portrait-tab"
        :class="{ 'is-selected': char.id === activeId, 'is-player': char.role === 'player' }"
        @click="selectCharacter(char.id)"
      >
        <div class="avatar-circle" :class="{ 'avatar-player': char.role === 'player' }">
          <span>{{ getInitials(char.display_name) }}</span>
          <span v-if="char.role === 'player'" class="player-dot" title="Protagonist (You)">★</span>
        </div>
        <span class="portrait-name">
          {{ char.display_name }}
          <span v-if="char.role === 'player'" class="you-tag">(You)</span>
        </span>
      </div>
    </div>

    <!-- Active character detail card -->
    <div v-if="activeCharacter" class="character-detail-card">
      <!-- Identity Hero -->
      <div class="card-hero">
        <div class="large-avatar" :class="{ 'avatar-player': activeCharacter.role === 'player' }">
          <span>{{ getInitials(activeCharacter.display_name) }}</span>
        </div>
        <div class="hero-info">
          <div class="char-title-row">
            <h4 class="char-name">{{ activeCharacter.display_name }}</h4>
            <VnBadge v-if="activeCharacter.role === 'player'" variant="success">
              Protagonist (You)
            </VnBadge>
          </div>
          <VnBadge v-if="charRole(activeCharacter)" variant="brand" capitalize>
            {{ charRole(activeCharacter) }}
          </VnBadge>
        </div>
      </div>

      <!-- Structured Status Grid -->
      <div class="status-grid">
        <div v-if="charEmotionalState(activeCharacter)" class="status-card">
          <span class="status-label">Mood</span>
          <div class="status-value">
            <span class="status-icon">💭</span>
            <span class="status-text">{{ charEmotionalState(activeCharacter) }}</span>
          </div>
        </div>

        <div v-if="charPhysicalCondition(activeCharacter)" class="status-card">
          <span class="status-label">Condition</span>
          <div class="status-value">
            <span class="status-icon">💚</span>
            <span class="status-text">{{ charPhysicalCondition(activeCharacter) }}</span>
          </div>
        </div>

        <div v-if="charLocation(activeCharacter)" class="status-card full-width">
          <span class="status-label">Location</span>
          <div class="status-value">
            <span class="status-icon">📍</span>
            <span class="status-text">{{ charLocation(activeCharacter) }}</span>
          </div>
        </div>
      </div>

      <!-- Scrollable Details Section -->
      <div class="character-details-scroll">
        <!-- Voice / Mannerism Quote -->
        <div v-if="charVoice(activeCharacter)" class="voice-box">
          <span class="info-subtitle">Voice & Demeanor</span>
          <p class="voice-text">“{{ charVoice(activeCharacter) }}”</p>
        </div>

        <!-- Background & Bio -->
        <div v-if="charBackground(activeCharacter)" class="background-box">
          <span class="info-subtitle">Background</span>
          <p class="bio-text">{{ charBackground(activeCharacter) }}</p>
        </div>

        <!-- Appearance -->
        <div v-if="charAppearance(activeCharacter)" class="appearance-box">
          <span class="info-subtitle">Appearance</span>
          <p class="bio-text">{{ charAppearance(activeCharacter) }}</p>
        </div>

        <!-- Traits list -->
        <div v-if="charTraits(activeCharacter).length" class="traits-container">
          <span class="info-subtitle">Traits</span>
          <div class="traits-wrap">
            <span
              v-for="trait in charTraits(activeCharacter)"
              :key="trait"
              class="trait-pill"
            >
              #{{ trait }}
            </span>
          </div>
        </div>

        <!-- Core Values -->
        <div v-if="charValues(activeCharacter).length" class="traits-container">
          <span class="info-subtitle">Values</span>
          <div class="traits-wrap">
            <span
              v-for="val in charValues(activeCharacter)"
              :key="val"
              class="value-pill"
            >
              {{ val }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.character-slider-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  width: 100%;
}

.portraits-bar {
  display: flex;
  gap: 0.5rem;
  overflow-x: auto;
  padding-bottom: 0.4rem;
}

.portrait-tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  cursor: pointer;
  padding: 0.4rem 0.6rem;
  border-radius: 0.75rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  transition: all 180ms ease;
  min-width: 4rem;
  user-select: none;
}

.portrait-tab:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(99, 102, 241, 0.3);
}

.portrait-tab.is-selected {
  background: rgba(99, 102, 241, 0.15);
  border-color: #6366f1;
  box-shadow: 0 0 10px rgba(99, 102, 241, 0.3);
}

.avatar-circle {
  width: 2.2rem;
  height: 2.2rem;
  border-radius: 9999px;
  background: linear-gradient(135deg, #4f46e5, #ec4899);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.85rem;
  color: #fff;
}

.portrait-name {
  font-size: 0.72rem;
  color: #cbd5e1;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
}

.you-tag {
  font-size: 0.68rem;
  color: #34d399;
  font-weight: 600;
}

.avatar-circle.avatar-player {
  position: relative;
  background: linear-gradient(135deg, #059669, #0d9488);
  box-shadow: 0 0 8px rgba(16, 185, 129, 0.4);
}

.player-dot {
  position: absolute;
  bottom: -2px;
  right: -2px;
  font-size: 0.62rem;
  line-height: 1;
  background: #0f172a;
  color: #fbbf24;
  border-radius: 9999px;
  padding: 1px 2px;
  border: 1px solid rgba(251, 191, 36, 0.6);
}

.character-detail-card {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  background: rgba(18, 22, 34, 0.75);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 1rem;
  padding: 1rem;
  backdrop-filter: blur(16px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}

.character-details-scroll {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.card-hero {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.large-avatar {
  width: 3.2rem;
  height: 3.2rem;
  border-radius: 9999px;
  background: linear-gradient(135deg, #6366f1, #ec4899);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 1.2rem;
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 0 12px rgba(236, 72, 153, 0.35);
}

.large-avatar.avatar-player {
  background: linear-gradient(135deg, #059669, #0284c7);
  box-shadow: 0 0 12px rgba(16, 185, 129, 0.45);
}

.hero-info {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 0;
  flex: 1;
}

.char-title-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.char-name {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 700;
  color: #f8fafc;
}

/* Structured Status Grid */
.status-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.5rem;
}

.status-card {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.5rem 0.65rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 0.55rem;
  min-width: 0;
}

.status-card.full-width {
  grid-column: 1 / -1;
}

.status-label {
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #94a3b8;
}

.status-value {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  min-width: 0;
}

.status-icon {
  font-size: 0.85rem;
  flex-shrink: 0;
}

.status-text {
  font-size: 0.82rem;
  font-weight: 600;
  color: #e2e8f0;
  text-transform: capitalize;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.info-subtitle {
  display: block;
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #a5b4fc;
  margin-bottom: 0.3rem;
}

.voice-box {
  padding: 0.65rem 0.85rem;
  background: rgba(99, 102, 241, 0.08);
  border-left: 3px solid #818cf8;
  border-radius: 0.4rem;
}

.voice-text {
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.45;
  color: #e2e8f0;
  font-style: italic;
}

.background-box,
.appearance-box {
  padding: 0.65rem 0.85rem;
  background: rgba(0, 0, 0, 0.25);
  border-left: 3px solid rgba(255, 255, 255, 0.15);
  border-radius: 0.4rem;
}

.bio-text {
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.5;
  color: #cbd5e1;
}

.traits-container {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.traits-wrap {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.trait-pill {
  padding: 0.18rem 0.5rem;
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(99, 102, 241, 0.25);
  border-radius: 0.35rem;
  color: #a5b4fc;
  font-size: 0.74rem;
  text-transform: capitalize;
}

.value-pill {
  padding: 0.18rem 0.5rem;
  background: rgba(236, 72, 153, 0.12);
  border: 1px solid rgba(236, 72, 153, 0.25);
  border-radius: 0.35rem;
  color: #f472b6;
  font-size: 0.74rem;
  text-transform: capitalize;
}
</style>
