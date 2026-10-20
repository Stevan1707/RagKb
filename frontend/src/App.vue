<script setup>
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <header class="nav">
    <span class="brand">RagKb</span>
    <nav>
      <RouterLink to="/">首页</RouterLink>
    </nav>
  </header>

  <main class="main">
    <RouterView />
  </main>
</template>

<style scoped>
.nav {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 0 24px;
  height: 56px;
  border-bottom: 1px solid #e5e7eb;
}

.brand {
  font-weight: 600;
}

nav a {
  color: #4b5563;
  text-decoration: none;
}

nav a.router-link-active {
  color: #2563eb;
}

.main {
  padding: 24px;
}
</style>
