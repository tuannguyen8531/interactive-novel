<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
import { useDebugStore } from '@/stores/debug'

const debug = useDebugStore()
</script>

<template>
  <div class="shell">
    <!-- Ambient corner glows inspired by Romcom Creator -->
    <div class="glow-top-right" aria-hidden="true" />
    <div class="glow-bottom-left" aria-hidden="true" />

    <header class="topbar">
      <div class="brand-container">
        <RouterLink class="topbar-brand" to="/">
          <span class="brand-icon">✨</span>
          <span class="brand-title">Interactive Novel</span>
        </RouterLink>
      </div>
      <nav aria-label="Primary navigation">
        <RouterLink to="/" class="nav-item">
          <span>Library</span>
        </RouterLink>
        <RouterLink to="/settings" class="nav-item">
          <span>Settings</span>
        </RouterLink>
        <RouterLink v-if="debug.enabled" to="/inspector" class="nav-item debug-item">
          <span>Inspector</span>
        </RouterLink>
      </nav>
    </header>

    <main class="content">
      <RouterView v-slot="{ Component }">
        <Transition name="page-fade" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </main>
  </div>
</template>

<style>
:root {
  color-scheme: dark;
  --bg-canvas: #090a0f;
  --bg-surface: rgba(18, 22, 34, 0.75);
  --bg-surface-elevated: rgba(26, 31, 48, 0.85);
  --border-subtle: rgba(255, 255, 255, 0.08);
  --border-medium: rgba(255, 255, 255, 0.16);
  --brand: #6366f1;
  --brand-light: #818cf8;
  --brand-alpha: rgba(99, 102, 241, 0.15);
  --accent: #ec4899;
  --accent-light: #f472b6;
  --accent-alpha: rgba(236, 72, 153, 0.15);
  --success: #10b981;
  --warning: #f59e0b;
  --danger: #ef4444;
  --ink: #f8fafc;
  --muted: #94a3b8;
  --muted-dark: #64748b;
  --line: rgba(255, 255, 255, 0.08);
  --shadow-sm: 0 4px 12px rgba(0, 0, 0, 0.25);
  --shadow-lg: 0 12px 32px rgba(0, 0, 0, 0.45);
  --radius-sm: 0.5rem;
  --radius-md: 0.75rem;
  --radius-lg: 1.15rem;

  color: var(--ink);
  background: var(--bg-canvas);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-synthesis: none;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
}

* {
  box-sizing: border-box;
  scrollbar-color: rgba(255, 255, 255, 0.2) transparent;
  scrollbar-width: thin;
}

*::-webkit-scrollbar {
  width: 0.45rem;
  height: 0.45rem;
}

*::-webkit-scrollbar-track {
  background: transparent;
}

*::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.15);
}

*::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}

html {
  overflow-y: scroll;
  scrollbar-gutter: stable;
}

body {
  margin: 0;
  min-width: 320px;
  background: var(--bg-canvas);
  overflow-x: hidden;
}

a {
  color: inherit;
  text-decoration: none;
}

.shell {
  min-height: 100vh;
  position: relative;
  display: flex;
  flex-direction: column;
}

/* Ambient Radial Glows */
.glow-top-right {
  position: fixed;
  top: 0;
  right: 0;
  width: clamp(28%, 35vw, 42%);
  height: clamp(32%, 42vw, 52%);
  background: radial-gradient(ellipse at top right, rgba(99, 102, 241, 0.14) 0%, transparent 70%);
  pointer-events: none;
  z-index: 0;
}

.glow-bottom-left {
  position: fixed;
  bottom: 0;
  left: 0;
  width: clamp(24%, 31vw, 36%);
  height: clamp(30%, 39vw, 46%);
  background: radial-gradient(ellipse at bottom left, rgba(236, 72, 153, 0.11) 0%, transparent 70%);
  pointer-events: none;
  z-index: 0;
}

/* Topbar Navigation */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 4rem;
  min-height: 4rem;
  max-height: 4rem;
  padding: 0 clamp(1rem, 4vw, 3.5rem);
  background: rgba(13, 16, 26, 0.85);
  border-bottom: 1px solid var(--border-subtle);
  backdrop-filter: blur(20px);
  position: sticky;
  top: 0;
  z-index: 50;
  box-sizing: border-box;
}

.brand-container {
  display: flex;
  align-items: center;
  height: 100%;
}

.topbar-brand {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-weight: 800;
  font-size: 1.1rem;
  line-height: 1;
  background: linear-gradient(135deg, #f8fafc, #cbd5e1);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  transition: transform 180ms ease;
}

.topbar-brand:hover {
  transform: translateY(-1px);
}

.brand-icon {
  font-size: 1.25rem;
  line-height: 1;
  filter: drop-shadow(0 0 8px rgba(99, 102, 241, 0.6));
  -webkit-text-fill-color: initial;
}

nav {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  height: 100%;
}

.nav-item {
  display: inline-flex;
  align-items: center;
  padding: 0.45rem 0.85rem;
  border-radius: var(--radius-sm);
  font-size: 0.88rem;
  font-weight: 500;
  color: var(--muted);
  line-height: 1.25;
  border: 1px solid transparent;
  box-sizing: border-box;
  transition: color 160ms ease, background-color 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
}

.nav-item:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.05);
}

.nav-item.router-link-active {
  color: #fff;
  background: var(--brand-alpha);
  border-color: rgba(99, 102, 241, 0.3);
  box-shadow: 0 0 12px rgba(99, 102, 241, 0.2);
}

.debug-item {
  color: #fbbf24;
}

/* Main Content Layout */
.content {
  width: min(100% - 2rem, 80rem);
  margin: 0 auto;
  padding: 2rem 0 4rem;
  position: relative;
  z-index: 1;
  flex: 1;
  min-height: calc(100vh - 5rem);
}

/* Smooth Page Route Transition */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 120ms ease;
}

.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
}

/* Typography & Base UI */
h1, h2, h3, h4, p {
  margin-top: 0;
}

h1, h2, h3, h4 {
  color: var(--ink);
  font-weight: 700;
  letter-spacing: -0.015em;
}

.page-heading {
  display: flex;
  gap: 1rem;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 2rem;
  flex-wrap: wrap;
}

.eyebrow {
  margin: 0 0 0.4rem;
  color: var(--brand-light);
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.muted {
  color: var(--muted);
}

/* Buttons */
button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  font: inherit;
  font-size: 0.9rem;
  font-weight: 600;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  padding: 0.65rem 1.15rem;
  background: linear-gradient(135deg, var(--brand), #4f46e5);
  color: #fff;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
  transition: all 180ms ease;
  user-select: none;
}

button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.45);
  filter: brightness(1.1);
}

button:active:not(:disabled) {
  transform: translateY(0);
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
  box-shadow: none;
}

button.secondary {
  border: 1px solid var(--border-medium);
  background: rgba(255, 255, 255, 0.05);
  color: var(--ink);
  box-shadow: none;
}

button.secondary:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.25);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
}

button.accent {
  background: linear-gradient(135deg, var(--accent), #db2777);
  box-shadow: 0 4px 14px rgba(236, 72, 153, 0.35);
}

button.accent:hover:not(:disabled) {
  box-shadow: 0 6px 20px rgba(236, 72, 153, 0.45);
}

button.danger {
  background: linear-gradient(135deg, var(--danger), #b91c1c);
  box-shadow: 0 4px 14px rgba(239, 68, 68, 0.35);
}

/* Inputs & Form controls */
input, textarea, select {
  font: inherit;
  font-size: 0.92rem;
  background: rgba(13, 16, 26, 0.85);
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-md);
  color: #fff;
  padding: 0.65rem 0.9rem;
  transition: all 180ms ease;
  width: 100%;
}

input:focus, textarea:focus, select:focus {
  outline: none;
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25);
  background: rgba(18, 22, 34, 0.95);
}

input::placeholder, textarea::placeholder {
  color: var(--muted-dark);
}

/* Cards and Panels */
.card, .panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  backdrop-filter: blur(16px);
  box-shadow: var(--shadow-sm);
  transition: border-color 200ms ease, transform 200ms ease, box-shadow 200ms ease;
}

.card {
  padding: 1.5rem;
}

.panel {
  padding: 1.25rem;
}

.error-box, .notice-box {
  margin: 1rem 0;
  padding: 0.85rem 1.15rem;
  border-radius: var(--radius-md);
  font-size: 0.88rem;
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.error-box {
  border: 1px solid rgba(239, 68, 68, 0.35);
  background: rgba(239, 68, 68, 0.12);
  color: #fca5a5;
}

.notice-box {
  border: 1px solid rgba(245, 158, 11, 0.35);
  background: rgba(245, 158, 11, 0.12);
  color: #fde68a;
}

.empty-state {
  padding: 3rem 1.5rem;
  border: 1px dashed var(--border-medium);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.02);
  color: var(--muted);
  text-align: center;
}
</style>
