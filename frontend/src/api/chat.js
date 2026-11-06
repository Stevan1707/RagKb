import http from './http'

/**
 * 提问。后端是非流式的：等模型写完才返回，所以超时给足。
 * conversation_id 传 null 表示新建会话。
 */
export function ask(question, conversationId = null, topK = 3) {
  return http.post(
    '/chat',
    { question, conversation_id: conversationId, top_k: topK },
    { timeout: 180000 },
  )
}

/** 会话列表，最近更新的在前 */
export function listConversations(limit = 50) {
  return http.get('/conversations', { params: { limit } })
}

/** 会话详情：所有消息 + 每条 assistant 消息的引用 */
export function getConversation(id) {
  return http.get(`/conversations/${id}`)
}
