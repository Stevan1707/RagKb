import axios from 'axios'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 15000,
})

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    // 后端有两种错误体：字符串（404/400）和对象（上传失败时带 doc_id/reason）
    const detail = err.response?.data?.detail
    const message =
      typeof detail === 'string'
        ? detail
        : detail?.message || detail?.reason || err.message || '请求失败'
    return Promise.reject(new Error(message))
  },
)

export default http
