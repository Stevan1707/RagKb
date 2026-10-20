import axios from 'axios'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 15000,
})

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const message = err.response?.data?.detail || err.message || '请求失败'
    return Promise.reject(new Error(message))
  },
)

export default http
