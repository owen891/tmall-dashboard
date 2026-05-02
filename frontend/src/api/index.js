import axios from 'axios'
import apiCache from '@/utils/cache'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000
})

request.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

const CACHE_DURATION = 5 * 60 * 1000 // 5 分钟缓存

const cachedRequest = async (method, url, options = {}) => {
  const { useCache = false, cacheDuration = CACHE_DURATION, ...requestOptions } = options

  // GET 请求使用缓存
  if (useCache && method === 'get') {
    const cached = apiCache.get(url, requestOptions.params || {})
    if (cached) {
      return cached
    }
    const response = await request[method](url, requestOptions)
    apiCache.set(url, requestOptions.params || {}, response, cacheDuration)
    return response
  }

  // 其他请求直接发送
  return request[method](url, requestOptions)
}

export default {
  // Dashboard APIs (使用缓存)
  getDashboardSummary() {
    return cachedRequest('get', '/dashboard/summary', { useCache: true })
  },
  getTopProducts() {
    return cachedRequest('get', '/dashboard/top-products', { useCache: true })
  },
  getQuadrantData() {
    return cachedRequest('get', '/dashboard/quadrant', { useCache: true })
  },

  // Product APIs
  getProducts(params) {
    const { page, page_size, ...rest } = params || {}
    const limit = page_size || 20
    const offset = page ? (page - 1) * limit : 0
    return request.get('/products', {
      params: {
        limit,
        offset,
        ...rest
      }
    })
  },
  getProduct(productId) {
    return request.get(`/products/${productId}`)
  },
  getProductWeeklyData(productId) {
    return request.get(`/products/${productId}/weekly-data`)
  },
  getProductOperations(productId) {
    return request.get(`/products/${productId}/operations`)
  },
  getProductNotes(productId) {
    return request.get(`/products/${productId}/notes`)
  },

  // Cache management
  clearCache(url = null) {
    apiCache.clear(url)
  },
  getCacheStats() {
    return apiCache.getStats()
  }
}
