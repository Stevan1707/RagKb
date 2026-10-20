<script setup>
import { onMounted } from 'vue'

import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

onMounted(() => {
  appStore.checkHealth()
})
</script>

<template>
  <div class="home">
    <h1>RagKb</h1>
    <p>Vue 3 + Vite（JavaScript）+ FastAPI 已就绪。</p>

    <div class="status">
      后端状态：
      <span :class="['badge', appStore.backendStatus]">
        {{ appStore.backendStatus === 'ok' ? '已连接' : '未连接' }}
      </span>
      <button @click="appStore.checkHealth()">重新检测</button>
    </div>
  </div>
</template>

<style scoped>
.home {
  max-width: 720px;
  margin: 0 auto;
}

.status {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
}

.badge {
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 13px;
  background: #e5e7eb;
  color: #4b5563;
}

.badge.ok {
  background: #dcfce7;
  color: #15803d;
}

.badge.error {
  background: #fee2e2;
  color: #b91c1c;
}

button {
  padding: 6px 14px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
}

button:hover {
  background: #f3f4f6;
}
</style>
