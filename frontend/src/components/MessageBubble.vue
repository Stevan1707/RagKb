<script setup>
import SourceList from '@/components/SourceList.vue'

defineProps({
  message: { type: Object, required: true },
})
</script>

<template>
  <div class="row" :class="message.role">
    <div class="avatar">{{ message.role === 'user' ? '我' : 'AI' }}</div>

    <div class="bubble">
      <p v-if="message.content" class="content">{{ message.content }}</p>
      <p v-else-if="message.pending" class="content pending">正在检索资料并生成回答…</p>

      <span v-if="message.pending" class="cursor" />

      <p v-if="message.error" class="error">⚠ {{ message.error }}</p>

      <SourceList :sources="message.sources || []" />
    </div>
  </div>
</template>

<style scoped>
.row {
  display: flex;
  gap: 12px;
  margin-bottom: 22px;
}

.row.user {
  flex-direction: row-reverse;
}

.avatar {
  flex: none;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  background: #9ca3af;
}

.row.assistant .avatar {
  background: #2563eb;
}

.bubble {
  max-width: min(720px, 86%);
  padding: 10px 14px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e5e7eb;
  box-shadow: 0 1px 2px rgb(15 23 42 / 4%);
}

.row.user .bubble {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}

.content {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14.5px;
  line-height: 1.75;
}

.pending {
  color: #9ca3af;
}

.cursor {
  display: inline-block;
  width: 7px;
  height: 15px;
  background: #2563eb;
  vertical-align: -2px;
  margin-left: 2px;
  animation: blink 1s steps(2, start) infinite;
}

@keyframes blink {
  to {
    visibility: hidden;
  }
}

.error {
  margin: 8px 0 0;
  font-size: 13px;
  color: #b91c1c;
}
</style>
