<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'

import MessageBubble from '@/components/MessageBubble.vue'
import { useChatStore } from '@/stores/chat'

const chat = useChatStore()
const input = ref('')
const scroller = ref(null)

const suggestions = [
  '公民可以自由表达意见吗？',
  '国家机构由哪些部分组成？',
  '宪法规定公民有哪些义务？',
]

async function scrollToBottom() {
  await nextTick()
  const el = scroller.value
  if (el) el.scrollTop = el.scrollHeight
}

watch(
  () => [chat.messages.length, chat.messages.at(-1)?.content?.length],
  scrollToBottom,
)

async function submit() {
  const text = input.value.trim()
  if (!text || chat.sending) return
  input.value = ''
  await chat.send(text)
  scrollToBottom()
}

function useSuggestion(text) {
  input.value = text
  submit()
}

async function open(id) {
  await chat.openConversation(id)
  scrollToBottom()
}

function onKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submit()
  }
}

onMounted(async () => {
  await chat.loadConversations()
  await chat.restore()
  scrollToBottom()
})
</script>

<template>
  <section class="chat">
    <aside class="sidebar">
      <button class="new" @click="chat.newChat()">＋ 新对话</button>

      <p class="sidebar-title">最近会话</p>
      <ul class="conversations">
        <li v-if="!chat.conversations.length" class="empty">暂无历史会话</li>
        <li
          v-for="item in chat.conversations"
          :key="item.id"
          :class="{ active: chat.conversationId === item.id }"
          @click="open(item.id)"
        >
          <span class="title" :title="item.title">{{ item.title }}</span>
        </li>
      </ul>
    </aside>

    <div class="main">
      <div ref="scroller" class="scroll">
        <div v-if="!chat.messages.length" class="welcome">
          <h1>个人知识库问答</h1>
          <p>先在「文档库」上传 PDF，再在这里提问。答案会带 [1][2] 引用，点开可看原文。</p>
          <div class="suggestions">
            <button v-for="text in suggestions" :key="text" @click="useSuggestion(text)">
              {{ text }}
            </button>
          </div>
        </div>

        <MessageBubble v-for="message in chat.messages" :key="message.id" :message="message" />
      </div>

      <p v-if="chat.error" class="banner">{{ chat.error }}</p>

      <div class="composer">
        <textarea
          v-model="input"
          rows="2"
          placeholder="输入问题，Enter 发送，Shift + Enter 换行"
          :disabled="chat.sending"
          @keydown="onKeydown"
        />
        <button class="send" :disabled="!input.trim() || chat.sending" @click="submit">
          {{ chat.sending ? '生成中…' : '发送' }}
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.chat {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 18px;
  height: calc(100vh - 56px - 48px);
  max-width: 1140px;
  margin: 0 auto;
}

.sidebar {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.new {
  padding: 9px 12px;
  border-radius: 8px;
  border: 1px solid #dbeafe;
  background: #eff6ff;
  color: #1d4ed8;
  cursor: pointer;
  font-size: 13.5px;
  font-weight: 500;
}

.new:hover {
  background: #dbeafe;
}

.sidebar-title {
  margin: 18px 0 6px;
  font-size: 11.5px;
  color: #94a3b8;
}

.conversations {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  min-height: 0;
}

.conversations li {
  padding: 7px 9px;
  border-radius: 7px;
  cursor: pointer;
  font-size: 13px;
  color: #475569;
}

.conversations li:hover {
  background: #f1f5f9;
}

.conversations li.active {
  background: #eef2ff;
  color: #1d4ed8;
}

.conversations .title {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conversations .empty {
  color: #cbd5e1;
  font-size: 12.5px;
  cursor: default;
}

.main {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
}

.scroll {
  flex: 1;
  overflow-y: auto;
  padding: 24px 24px 8px;
}

.welcome {
  max-width: 560px;
  margin: 8vh auto 0;
  text-align: center;
}

.welcome h1 {
  margin: 0;
  font-size: 24px;
}

.welcome p {
  color: #6b7280;
  font-size: 13.5px;
  line-height: 1.7;
}

.suggestions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 22px;
}

.suggestions button {
  text-align: left;
  padding: 10px 14px;
  border-radius: 9px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  color: #374151;
  cursor: pointer;
  font-size: 13.5px;
}

.suggestions button:hover {
  border-color: #bfdbfe;
  background: #f8faff;
}

.banner {
  margin: 0;
  padding: 8px 24px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 13px;
}

.composer {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  padding: 14px 18px 18px;
  border-top: 1px solid #f1f5f9;
}

textarea {
  flex: 1;
  resize: none;
  padding: 10px 12px;
  border-radius: 9px;
  border: 1px solid #d1d5db;
  font: inherit;
  font-size: 14px;
  line-height: 1.6;
  outline: none;
  transition: border-color 0.15s;
}

textarea:focus {
  border-color: #2563eb;
}

textarea:disabled {
  background: #f8fafc;
  color: #9ca3af;
}

.send {
  padding: 10px 20px;
  border-radius: 9px;
  border: none;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  background: #2563eb;
  color: #fff;
  white-space: nowrap;
}

.send:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

@media (max-width: 820px) {
  .chat {
    grid-template-columns: 1fr;
    height: auto;
  }

  .sidebar {
    display: none;
  }

  .main {
    height: 72vh;
  }
}
</style>
