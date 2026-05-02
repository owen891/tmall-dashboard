/**
 * 简单的 API 缓存工具
 * 用于减少重复的 API 请求
 */
class APICache {
  constructor() {
    this.cache = new Map()
    this.ttl = 5 * 60 * 1000 // 默认 5 分钟缓存
  }

  /**
   * 生成缓存键
   */
  generateKey(url, params = {}) {
    return `${url}:${JSON.stringify(params)}`
  }

  /**
   * 获取缓存
   */
  get(url, params = {}) {
    const key = this.generateKey(url, params)
    const cached = this.cache.get(key)

    if (!cached) return null

    // 检查是否过期
    if (Date.now() > cached.expireAt) {
      this.cache.delete(key)
      return null
    }

    return cached.data
  }

  /**
   * 设置缓存
   */
  set(url, params = {}, data, ttl = this.ttl) {
    const key = this.generateKey(url, params)
    this.cache.set(key, {
      data,
      expireAt: Date.now() + ttl
    })
  }

  /**
   * 清除指定缓存
   */
  clear(url = null, params = null) {
    if (!url) {
      this.cache.clear()
      return
    }

    const key = this.generateKey(url, params || {})
    this.cache.delete(key)
  }

  /**
   * 清除过期缓存
   */
  cleanExpired() {
    const now = Date.now()
    for (const [key, value] of this.cache.entries()) {
      if (now > value.expireAt) {
        this.cache.delete(key)
      }
    }
  }

  /**
   * 获取缓存统计
   */
  getStats() {
    let valid = 0
    let expired = 0
    const now = Date.now()

    for (const value of this.cache.values()) {
      if (now > value.expireAt) {
        expired++
      } else {
        valid++
      }
    }

    return {
      total: this.cache.size,
      valid,
      expired
    }
  }
}

// 创建全局缓存实例
const apiCache = new APICache()

// 定期清理过期缓存
setInterval(() => apiCache.cleanExpired(), 60000)

export default apiCache
export { APICache }
