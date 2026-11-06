<script setup>
import { ref } from 'vue'

defineProps({
  sources: { type: Array, default: () => [] },
})

const openIndex = ref(null)

function toggle(index) {
  openIndex.value = openIndex.value === index ? null : index
}
</script>

<template>
  <div v-if="sources.length" class="sources">
    <div class="title">参考来源 · {{ sources.length }} 条</div>

    <ol class="list">
      <li
        v-for="(source, index) in sources"
        :key="source.chunk_id || index"
        class="item"
        :class="{ open: openIndex === index }"
        @click="toggle(index)"
      >
        <div class="head">
          <span class="rank">[{{ source.rank || index + 1 }}]</span>
          <span class="doc" :title="source.doc_name">{{ source.doc_name }}</span>
          <span class="page">第 {{ source.page }} 页</span>
          <span v-if="source.score != null" class="score">
            {{ Number(source.score).toFixed(3) }}
          </span>
          <span class="chevron">{{ openIndex === index ? '−' : '+' }}</span>
        </div>
        <p v-if="openIndex === index" class="excerpt">{{ source.content }}</p>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.sources {
  margin-top: 14px;
  border-top: 1px dashed #e5e7eb;
  padding-top: 10px;
}

.title {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 6px;
}

.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.item {
  border-radius: 8px;
  padding: 6px 8px;
  cursor: pointer;
  background: #f9fafb;
  border: 1px solid transparent;
  transition: background 0.15s, border-color 0.15s;
}

.item:hover,
.item.open {
  background: #f3f4f6;
  border-color: #e5e7eb;
}

.head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  color: #374151;
}

.rank {
  color: #2563eb;
  font-weight: 600;
}

.doc {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.page,
.score {
  color: #9ca3af;
}

.score {
  font-variant-numeric: tabular-nums;
}

.chevron {
  width: 14px;
  text-align: center;
  color: #9ca3af;
}

.excerpt {
  margin: 8px 0 2px;
  font-size: 12.5px;
  line-height: 1.7;
  color: #4b5563;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 260px;
  overflow-y: auto;
}
</style>
