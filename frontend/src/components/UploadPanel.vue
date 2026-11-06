<script setup>
import { ref } from 'vue'

const props = defineProps({
  uploading: { type: Boolean, default: false },
  progress: { type: Number, default: 0 },
})

const emit = defineEmits(['upload'])

const inputEl = ref(null)
const dragging = ref(false)
const localError = ref('')

const MAX_MB = 50

function pick() {
  if (props.uploading) return
  inputEl.value?.click()
}

function validate(file) {
  if (!file) return '没有选择文件'
  if (!file.name.toLowerCase().endsWith('.pdf')) return '目前只支持 PDF'
  if (file.size > MAX_MB * 1024 * 1024) return `文件超过 ${MAX_MB}MB`
  return ''
}

function handle(files) {
  const file = files?.[0]
  const error = validate(file)
  localError.value = error
  if (!error) emit('upload', file)
}

function onChange(event) {
  handle(event.target.files)
  event.target.value = ''
}

function onDrop(event) {
  dragging.value = false
  handle(event.dataTransfer.files)
}
</script>

<template>
  <div
    class="upload"
    :class="{ dragging, busy: uploading }"
    @click="pick"
    @dragover.prevent="dragging = true"
    @dragleave.prevent="dragging = false"
    @drop.prevent="onDrop"
  >
    <input ref="inputEl" type="file" accept="application/pdf,.pdf" hidden @change="onChange" />

    <template v-if="uploading">
      <div class="title">正在上传… {{ progress }}%</div>
      <div class="bar"><span :style="{ width: progress + '%' }" /></div>
      <p class="desc">上传完成后会解析、切块、向量化，稍等几秒</p>
    </template>
    <template v-else>
      <div class="icon">＋</div>
      <div class="title">点击或把 PDF 拖到这里</div>
      <p class="desc">单文件 ≤ {{ MAX_MB }}MB，入库完成后就能在对话里检索到</p>
    </template>

    <p v-if="localError" class="error">{{ localError }}</p>
  </div>
</template>

<style scoped>
.upload {
  border: 1.5px dashed #cbd5e1;
  border-radius: 12px;
  padding: 26px;
  text-align: center;
  cursor: pointer;
  background: #fff;
  transition: border-color 0.15s, background 0.15s;
}

.upload:hover,
.upload.dragging {
  border-color: #2563eb;
  background: #f8faff;
}

.upload.busy {
  cursor: progress;
}

.icon {
  font-size: 26px;
  color: #94a3b8;
  line-height: 1;
}

.title {
  margin-top: 8px;
  font-size: 14.5px;
  font-weight: 500;
  color: #334155;
}

.desc {
  margin: 6px 0 0;
  font-size: 12.5px;
  color: #94a3b8;
}

.bar {
  margin: 12px auto 0;
  width: 70%;
  height: 6px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
}

.bar span {
  display: block;
  height: 100%;
  background: #2563eb;
  transition: width 0.2s;
}

.error {
  margin: 10px 0 0;
  color: #b91c1c;
  font-size: 13px;
}
</style>
