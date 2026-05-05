class APICache {
  constructor(maxSize = 500) {
    this.cache = new Map()
    this.ttl = 5 * 60 * 1000
    this.maxSize = maxSize
  }

  generateKey(url, params = {}) {
    const sortedParams = Object.keys(params)
      .sort()
      .reduce((obj, key) => {
        obj[key] = params[key]
        return obj
      }, {})
    return `${url}:${JSON.stringify(sortedParams)}`
  }

  get(url, params = {}) {
    const key = this.generateKey(url, params)
    const cached = this.cache.get(key)

    if (!cached) return null

    if (Date.now() > cached.expireAt) {
      this.cache.delete(key)
      return null
    }

    return cached.data
  }

  set(url, params = {}, data, ttl = this.ttl) {
    if (this.cache.size >= this.maxSize) {
      this.evictOldest()
    }

    const key = this.generateKey(url, params)
    this.cache.set(key, {
      data,
      expireAt: Date.now() + ttl,
      createdAt: Date.now()
    })
  }

  evictOldest() {
    let oldestKey = null
    let oldestTime = Infinity
    for (const [key, value] of this.cache.entries()) {
      if (value.createdAt < oldestTime) {
        oldestTime = value.createdAt
        oldestKey = key
      }
    }
    if (oldestKey) {
      this.cache.delete(oldestKey)
    }
  }

  clear(url = null, params = null) {
    if (!url) {
      this.cache.clear()
      return
    }

    if (!params) {
      for (const key of this.cache.keys()) {
        if (key.startsWith(`${url}:`)) {
          this.cache.delete(key)
        }
      }
      return
    }

    const key = this.generateKey(url, params)
    this.cache.delete(key)
  }

  cleanExpired() {
    const now = Date.now()
    const keysToDelete = []
    for (const [key, value] of this.cache.entries()) {
      if (now > value.expireAt) {
        keysToDelete.push(key)
      }
    }
    for (const key of keysToDelete) {
      this.cache.delete(key)
    }
  }

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
      expired,
      maxSize: this.maxSize
    }
  }

  destroy() {
    this.cache.clear()
  }
}

const apiCache = new APICache(500)

let cleanupTimer = null

export function startCleanup() {
  if (cleanupTimer) return
  cleanupTimer = setInterval(() => apiCache.cleanExpired(), 60000)
}

export function stopCleanup() {
  if (cleanupTimer) {
    clearInterval(cleanupTimer)
    cleanupTimer = null
  }
}

startCleanup()

export default apiCache
export { APICache }
