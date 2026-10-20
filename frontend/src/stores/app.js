import { defineStore } from 'pinia'

import http from '@/api/http'

export const useAppStore = defineStore('app', {
  state: () => ({
    backendStatus: 'unknown',
  }),
  actions: {
    async checkHealth() {
      try {
        const data = await http.get('/health')
        this.backendStatus = data.status === 'ok' ? 'ok' : 'error'
      } catch (e) {
        this.backendStatus = 'error'
      }
      return this.backendStatus
    },
  },
})
