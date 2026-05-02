import axios from 'axios'
import apiCache from '@/utils/cache'
import { ApiError, handleError } from '@/utils/errorHandler'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

request.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    if (error.response) {
      const { status, data } = error.response
      const message = data?.message || data?.detail || '请求失败'
      return Promise.reject(new ApiError(message, status, data))
    }
    if (error.request) {
      return Promise.reject(new ApiError('网络错误，请检查网络连接', 0))
    }
    return Promise.reject(new ApiError(error.message || '未知错误', -1))
  }
)

const CACHE_DURATION = 5 * 60 * 1000

const cachedRequest = async (method, url, options = {}) => {
  const { useCache = false, cacheDuration = CACHE_DURATION, ...requestOptions } = options

  if (useCache && method === 'get') {
    const cached = apiCache.get(url, requestOptions.params || {})
    if (cached) {
      return cached
    }
    const response = await request[method](url, requestOptions)
    apiCache.set(url, requestOptions.params || {}, response, cacheDuration)
    return response
  }

  return request[method](url, requestOptions)
}

export default {
  getDashboardSummary() {
    return cachedRequest('get', '/dashboard/summary', { useCache: true })
  },
  getTopProducts() {
    return cachedRequest('get', '/dashboard/top-products', { useCache: true })
  },
  getQuadrantData() {
    return cachedRequest('get', '/dashboard/quadrant', { useCache: true })
  },

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

  getKPI(params) {
    return request.get('/kpi', { params })
  },
  getKPISummary(params) {
    return request.get('/kpi/summary', { params })
  },

  getHealthList(params) {
    return request.get('/health/list', { params })
  },
  getHealthSummary(params) {
    return request.get('/health/summary', { params })
  },

  getTrends(params) {
    return request.get('/trends', { params })
  },

  getAlerts(params) {
    return request.get('/alerts', { params })
  },

  getOperations(params) {
    return request.get('/operations', { params })
  },

  clearCache(url = null) {
    apiCache.clear(url)
  },
  getCacheStats() {
    return apiCache.getStats()
  }
}
