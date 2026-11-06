<script setup>
import { onMounted } from 'vue'
import { RouterLink, RouterView } from 'vue-router'

import { useAppStore } from '@/stores/app'

const app = useAppStore()

onMounted(() => app.checkHealth())
</script>

<template>
  <header class="nav">
    <RouterLink to="/" class="brand">RagKb<span>个人知识库</span></RouterLink>

    <nav>
      <RouterLink to="/chat">对话</RouterLink>
      <RouterLink to="/docs">文档库</RouterLink>
    </nav>

    <span class="status" :class="app.backendStatus" :title="`后端：${app.backendStatus}`">
      <i />
      {{ app.backendStatus === 'ok' ? '已连接' : '未连接' }}
    </span>
  </header>

  <main class="main">
    <RouterView />
  </main>
</template>

<style scoped>
.nav {
  display: flex;
  align-items: center;
  gap: 28px;
  padding: 0 24px;
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  position: sticky;
  top: 0;
  z-index: 10;
}

.brand {
  font-weight: 650;
  color: #111827;
  text-decoration: none;
  font-size: 16px;
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.brand span {
  font-weight: 400;
  font-size: 12px;
  color: #9ca3af;
}

nav {
  display: flex;
  gap: 20px;
  flex: 1;
}

nav a {
  color: #4b5563;
  text-decoration: none;
  font-size: 14px;
  padding: 4px 0;
  border-bottom: 2px solid transparent;
}

nav a.router-link-active {
  color: #2563eb;
  border-bottom-color: #2563eb;
}

.status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #6b7280;
}

.status i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #d1d5db;
}

.status.ok i {
  background: #22c55e;
}

.status.error i {
  background: #ef4444;
}

.main {
  padding: 24px;
}
</style>
