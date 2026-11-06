<script setup>
import { computed, onMounted, onUnmounted } from 'vue'

import UploadPanel from '@/components/UploadPanel.vue'
import { useDocsStore } from '@/stores/docs'

const docs = useDocsStore()

const STATUS_TEXT = {
  pending: '排队中',
  processing: '处理中',
  done: '已入库',
  failed: '失败',
}

const synced = computed(() => docs.stats?.synced)
const cards = computed(() => [
  { label: '文档', value: docs.stats?.documents ?? '-' },
  { label: '文本块', value: docs.stats?.chunks ?? '-' },
  { label: '向量', value: docs.stats?.vectors ?? '-' },
])

async function onUpload(file) {
  try {
    await docs.upload(file)
  } catch {
    // 错误已经写进 store.error
  }
}

async function onDelete(doc) {
  if (!window.confirm(`确定删除《${doc.filename}》？对应的文本块和向量会一起清掉。`)) return
  try {
    await docs.remove(doc.id)
  } catch {
    // 同上
  }
}

onMounted(() => docs.load())
onUnmounted(() => docs.stopPolling())
</script>

<template>
  <section class="docs">
    <header class="head">
      <div>
        <h1>文档库</h1>
        <p class="sub">上传 PDF / Word / 文本后会自动解析、切块、向量化；处理完就能在对话里检索到。</p>
      </div>
      <button class="ghost" :disabled="docs.loading" @click="docs.load()">
        {{ docs.loading ? '刷新中…' : '刷新' }}
      </button>
    </header>

    <div class="stats">
      <div v-for="card in cards" :key="card.label" class="card">
        <span class="value">{{ card.value }}</span>
        <span class="label">{{ card.label }}</span>
      </div>
      <div class="card" :class="synced ? 'ok' : 'warn'">
        <span class="value">{{ synced ? '同步' : '不一致' }}</span>
        <span class="label">两库状态</span>
      </div>
    </div>

    <p v-if="docs.stats && !synced" class="banner warn-text">
      MySQL 里的块数与 FAISS 的向量数不一致，检索结果可能缺原文。删掉出问题的文档重新上传即可。
    </p>

    <UploadPanel :uploading="docs.uploading" :progress="docs.progress" @upload="onUpload" />

    <p v-if="docs.error" class="banner error">{{ docs.error }}</p>

    <div class="table">
      <div class="row head-row">
        <span>文件名</span>
        <span>状态</span>
        <span>块数</span>
        <span>上传时间</span>
        <span />
      </div>

      <div v-if="!docs.items.length" class="empty">
        还没有文档，先上传一份 PDF 吧。
      </div>

      <div v-for="doc in docs.items" :key="doc.id" class="row">
        <span class="name" :title="doc.filename">{{ doc.filename }}</span>
        <span>
          <span class="chip" :class="doc.status">
            {{ STATUS_TEXT[doc.status] || doc.status }}
          </span>
          <span v-if="doc.error" class="reason" :title="doc.error">查看原因</span>
        </span>
        <span class="num">{{ doc.chunk_count }}</span>
        <span class="time">{{ doc.created_time }}</span>
        <span class="actions">
          <button class="danger" @click="onDelete(doc)">删除</button>
        </span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.docs {
  max-width: 980px;
  margin: 0 auto;
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

h1 {
  margin: 0;
  font-size: 22px;
}

.sub {
  margin: 6px 0 0;
  color: #6b7280;
  font-size: 13.5px;
}

.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin: 20px 0 16px;
}

.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.card .value {
  font-size: 20px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.card .label {
  font-size: 12px;
  color: #9ca3af;
}

.card.ok {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.card.warn {
  background: #fffbeb;
  border-color: #fde68a;
}

.banner {
  margin: 12px 0 0;
  font-size: 13px;
  padding: 10px 12px;
  border-radius: 8px;
}

.error {
  background: #fef2f2;
  color: #b91c1c;
}

.warn-text {
  background: #fffbeb;
  color: #92400e;
}

.table {
  margin-top: 20px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  overflow: hidden;
}

.row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 150px 70px 170px 80px;
  align-items: center;
  gap: 12px;
  padding: 11px 14px;
  border-top: 1px solid #f1f5f9;
  font-size: 13.5px;
}

.head-row {
  border-top: none;
  background: #f8fafc;
  font-size: 12px;
  color: #64748b;
}

.name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.num,
.time {
  color: #64748b;
  font-variant-numeric: tabular-nums;
}

.time {
  font-size: 12.5px;
}

.empty {
  padding: 32px;
  text-align: center;
  color: #94a3b8;
  font-size: 13.5px;
}

.chip {
  display: inline-block;
  padding: 1px 9px;
  border-radius: 999px;
  font-size: 12px;
  background: #f1f5f9;
  color: #475569;
}

.chip.done {
  background: #dcfce7;
  color: #15803d;
}

.chip.processing,
.chip.pending {
  background: #dbeafe;
  color: #1d4ed8;
}

.chip.failed {
  background: #fee2e2;
  color: #b91c1c;
}

.reason {
  margin-left: 6px;
  font-size: 11.5px;
  color: #b91c1c;
  cursor: help;
}

.ghost {
  padding: 6px 14px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  white-space: nowrap;
}

.ghost:hover {
  background: #f8fafc;
}

.danger {
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid #fecaca;
  background: #fff;
  color: #b91c1c;
  cursor: pointer;
  font-size: 12.5px;
}

.danger:hover {
  background: #fef2f2;
}
</style>
