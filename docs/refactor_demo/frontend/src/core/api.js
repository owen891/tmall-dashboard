/**
 * API 统一封装 — 替代各 JS 文件中散落的 fetch 调用
 *
 * 原始方式：每个 JS 文件自己写 fetch('/api/xxx')
 * 重构后：统一封装，自动处理错误、loading、参数序列化
 */

const BASE_URL = '/api'

class ApiClient {
  constructor() {
    this.cache = new Map()
  }

  /**
   * GET 请求
   * @param {string} path - API 路径，如 '/kpi'
   * @param {Object} params - 查询参数
   * @param {Object} options - { cache: false, cacheTTL: 300000 }
   */
  async get(path, params = {}, options = {}) {
    const url = new URL(BASE_URL + path, window.location.origin)
    Object.entries(params).forEach(([k, v]) => {
      if (v !== null && v !== undefined) url.searchParams.set(k, v)
    })

    // 缓存检查
    const cacheKey = url.toString()
    if (options.cache !== false) {
      const cached = this.cache.get(cacheKey)
      if (cached && Date.now() < cached.expires) {
        return cached.data
      }
    }

    const response = await fetch(url)
    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`)
    }

    const data = await response.json()

    // 写入缓存
    if (options.cache !== false) {
      const ttl = options.cacheTTL || 300000  // 5 分钟
      this.cache.set(cacheKey, { data, expires: Date.now() + ttl })
    }

    return data
  }

  /**
   * POST 请求
   */
  async post(path, body = {}) {
    const response = await fetch(BASE_URL + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`)
    }

    return response.json()
  }

  /**
   * PUT 请求
   */
  async put(path, body = {}) {
    const response = await fetch(BASE_URL + path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`)
    }

    return response.json()
  }

  /**
   * DELETE 请求
   */
  async delete(path) {
    const response = await fetch(BASE_URL + path, { method: 'DELETE' })

    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`)
    }

    return response.json()
  }

  /**
   * 文件上传
   */
  async upload(path, file, onProgress = null) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      const formData = new FormData()
      formData.append('file', file)

      xhr.upload.addEventListener('progress', (e) => {
        if (onProgress && e.lengthComputable) {
          onProgress(Math.round((e.loaded / e.total) * 100))
        }
      })

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText))
        } else {
          reject(new Error(`Upload failed: ${xhr.status}`))
        }
      })

      xhr.addEventListener('error', () => reject(new Error('Upload failed')))
      xhr.open('POST', BASE_URL + path)
      xhr.send(formData)
    })
  }

  /**
   * 清除缓存
   */
  clearCache() {
    this.cache.clear()
  }
}

export const api = new ApiClient()
