import { defineStore } from 'pinia'

import { ask, getConversation, listConversations } from '@/api/chat'

const STORAGE_KEY = 'ragkb.conversation_id'

let seq = 0
const localId = () => `local-${++seq}`

export const useChatStore = defineStore('chat', {
  state: () => ({
    conversationId: null,
    conversations: [],
    messages: [],
    sending: false,
    error: '',
  }),

  getters: {
    canSend: (state) => !state.sending,
  },

  actions: {
    async loadConversations() {
      try {
        const data = await listConversations()
        this.conversations = data.items || []
      } catch {
        // 侧栏失败不影响主流程
      }
    },

    /** 刷新页面后恢复上次的会话 */
    async restore() {
      const saved = Number(localStorage.getItem(STORAGE_KEY))
      if (!saved) return
      try {
        await this.openConversation(saved)
      } catch {
        localStorage.removeItem(STORAGE_KEY)
      }
    },

    async openConversation(id) {
      const data = await getConversation(id)
      this.conversationId = data.conversation.id
      this.messages = (data.messages || []).map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        sources: m.sources || [],
        pending: false,
        error: '',
      }))
      localStorage.setItem(STORAGE_KEY, String(id))
      this.error = ''
    },

    newChat() {
      this.conversationId = null
      this.messages = []
      this.error = ''
      localStorage.removeItem(STORAGE_KEY)
    },

    async send(question) {
      const text = (question || '').trim()
      if (!text || this.sending) return

      this.error = ''
      this.messages.push({ id: localId(), role: 'user', content: text, sources: [] })

      const pending = {
        id: localId(),
        role: 'assistant',
        content: '',
        sources: [],
        pending: true,
        error: '',
      }
      this.messages.push(pending)
      this.sending = true

      try {
        const data = await ask(text, this.conversationId)
        this.conversationId = data.conversation_id
        localStorage.setItem(STORAGE_KEY, String(data.conversation_id))
        pending.id = data.message_id
        pending.content = data.answer
        pending.sources = data.sources || []
        await this.loadConversations()
      } catch (err) {
        pending.error = err.message
        this.error = err.message
      } finally {
        pending.pending = false
        this.sending = false
      }
    },
  },
})
