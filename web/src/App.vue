<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <RouterLink class="brand" to="/">Interactive Novel</RouterLink>
      <nav aria-label="Primary navigation">
        <RouterLink to="/">Home</RouterLink>
      </nav>
    </header>
    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<style>
:root {
  color: #18212f;
  background: #eef3f9;
  font-family: Inter, ui-sans-serif, system-ui, sans-serif;
  font-synthesis: none;
  text-rendering: optimizeLegibility;
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
  background: #18212f;
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
  width: min(100% - 2rem, 72rem);
  margin: 0 auto;
  padding: 3rem 0;
}
</style>
