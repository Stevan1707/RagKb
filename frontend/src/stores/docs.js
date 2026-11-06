import { defineStore } from 'pinia'

import { deleteDoc, getStats, listDocs, uploadDoc } from '@/api/docs'

// 轮询句柄放在模块里，不进 state：它不可序列化，也不需要响应式
let timer = null

export const useDocsStore = defineStore('docs', {
  state: () => ({
    items: [],
    stats: null,
    loading: false,
    uploading: false,
    progress: 0,
    error: '',
  }),

  getters: {
    /** 有文档在排队/处理中时，前端要继续轮询 */
    hasPending: (state) =>
      state.items.some((d) => d.status === 'pending' || d.status === 'processing'),
  },

  actions: {
    async refresh() {
      this.loading = true
      try {
        const data = await listDocs()
        this.items = data.items || []
        this.error = ''
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },

    async refreshStats() {
      try {
        this.stats = await getStats()
      } catch (err) {
        this.error = err.message
      }
    },

    /** 首屏：列表 + 统计一起拉，然后按需开始轮询 */
    async load() {
      await Promise.all([this.refresh(), this.refreshStats()])
      this.syncPolling()
    },

    syncPolling() {
      if (this.hasPending) this.startPolling()
      else this.stopPolling()
    },

    startPolling(interval = 2000) {
      if (timer) return
      timer = setInterval(async () => {
        await this.refresh()
        await this.refreshStats()
        this.syncPolling()
      }, interval)
    },

    stopPolling() {
      if (timer) {
        clearInterval(timer)
        timer = null
      }
    },

    async upload(file) {
      this.uploading = true
      this.progress = 0
      this.error = ''
      try {
        const data = await uploadDoc(file, (percent) => {
          this.progress = percent
        })
        await this.load()
        return data
      } catch (err) {
        this.error = err.message
        throw err
      } finally {
        this.uploading = false
      }
    },

    async remove(id) {
      await deleteDoc(id)
      await this.load()
    },
  },
})
