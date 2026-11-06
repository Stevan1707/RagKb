import http from './http'

/** 文档列表（含处理状态） */
export function listDocs() {
  return http.get('/docs')
}

/** 两库一致性：documents / chunks / vectors / synced */
export function getStats() {
  return http.get('/stats')
}

/**
 * 上传 PDF。
 * 必须用 FormData：后端是 multipart/form-data，字段名固定为 file。
 */
export function uploadDoc(file, onProgress) {
  const form = new FormData()
  form.append('file', file)
  return http.post('/docs/upload', form, {
    timeout: 120000, // 入库是同步的，大文件要等几十秒
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    },
  })
}

export function deleteDoc(id) {
  return http.delete(`/docs/${id}`)
}

/** 查看某文档切出来的块，调 CHUNK_SIZE 时用 */
export function listChunks(id, { page = 1, pageSize = 20, withContent = true } = {}) {
  return http.get(`/docs/${id}/chunks`, {
    params: { page, page_size: pageSize, with_content: withContent },
  })
}

/** 只检索不生成，排查召回用 */
export function searchDocs(q, topK = 5) {
  return http.get('/search', { params: { q, top_k: topK } })
}
