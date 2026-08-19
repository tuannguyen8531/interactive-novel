<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
import { useDebugStore } from '@/stores/debug'

const debug = useDebugStore()
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <RouterLink class="brand" to="/">Interactive Novel</RouterLink>
      <nav aria-label="Primary navigation">
        <RouterLink to="/">Home</RouterLink>
        <RouterLink to="/settings">Providers</RouterLink>
        <RouterLink v-if="debug.enabled" to="/inspector">Inspector</RouterLink>
      </nav>
    </header>
    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<style>
:root {
  color: #202b3c;
  background: #f3f0e8;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, sans-serif;
  font-synthesis: none;
  text-rendering: optimizeLegibility;
  --ink: #202b3c;
  --muted: #6f7887;
  --line: #ddd8cb;
  --paper: #fffdf8;
  --accent: #9d4d36;
  --accent-dark: #713525;
  --accent-soft: #f3dfd5;
  --green: #267252;
  --shadow: 0 1.5rem 4rem rgb(46 37 27 / 10%);
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
}

a {
  color: inherit;
  text-decoration: none;
}

.shell {
  min-height: 100vh;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem clamp(1rem, 4vw, 4rem);
  background: #252b39;
  color: #fff;
}

.brand {
  font-weight: 800;
}

nav {
  display: flex;
  gap: 1rem;
  color: #dbe7f5;
}

nav a.router-link-active {
  color: #fff;
  text-decoration: underline;
  text-underline-offset: 0.3rem;
}

.content {
  width: min(100% - 2rem, 78rem);
  margin: 0 auto;
  padding: 2.5rem 0 4rem;
}

button,
input,
textarea,
select {
  font: inherit;
}

button {
  border: 0;
  border-radius: 0.55rem;
  padding: 0.7rem 1rem;
  background: var(--accent);
  color: #fff;
  cursor: pointer;
  transition: transform 120ms ease, background 120ms ease, opacity 120ms ease;
}

button:hover:not(:disabled) {
  background: var(--accent-dark);
  transform: translateY(-1px);
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

button.secondary {
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink);
}

button.secondary:hover:not(:disabled) {
  background: #f1ece2;
}

button.danger {
  background: #a33f48;
}

.page-heading {
  display: flex;
  gap: 1rem;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}

.eyebrow {
  margin: 0 0 0.45rem;
  color: var(--accent);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.11em;
  text-transform: uppercase;
}

h1,
h2,
h3,
p {
  margin-top: 0;
}

h1,
h2,
h3 {
  color: var(--ink);
}

.card,
.panel {
  border: 1px solid var(--line);
  border-radius: 1rem;
  background: var(--paper);
  box-shadow: var(--shadow);
}

.card {
  padding: 1.35rem;
}

.panel {
  padding: 1.15rem;
}

.muted {
  color: var(--muted);
}

.error-box,
.notice-box {
  margin: 1rem 0;
  padding: 0.9rem 1rem;
  border-radius: 0.65rem;
}

.error-box {
  border: 1px solid #e5b9bd;
  background: #fff0f0;
  color: #8e303b;
}

.notice-box {
  border: 1px solid #e5d3a4;
  background: #fff7df;
  color: #6f5721;
}

.empty-state {
  padding: 2rem 1rem;
  border: 1px dashed var(--line);
  border-radius: 0.75rem;
  color: var(--muted);
  text-align: center;
}
</style>
