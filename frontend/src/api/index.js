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

  getProfitSummary(params) {
    return request.get('/profit/summary', { params })
  },
  getProductProfits(params) {
    return request.get('/profit/products', { params })
  },
  getProfitTrends(params) {
    return request.get('/profit/trends', { params })
  },
  getProfitByTier(params) {
    return request.get('/profit/by-tier', { params })
  },

  getCompareSummary(params) {
    return request.get('/compare/summary', { params })
  },
  getCompareProducts(params) {
    return request.get('/compare/products', { params })
  },
  getCompareTrends(params) {
    return request.get('/compare/trends', { params })
  },

  getInventoryWarnings(params) {
    return request.get('/inventory/warnings', { params })
  },
  getInventorySummary(params) {
    return request.get('/inventory/summary', { params })
  },
  getInventoryVelocity(params) {
    return request.get('/inventory/velocity', { params })
  },

  clearCache(url = null) {
    apiCache.clear(url)
  },
  getCacheStats() {
    return apiCache.getStats()
  },

  dashboardApi: {
    getMetrics(params) {
      return cachedRequest('get', '/dashboard/metrics', { params, useCache: true })
    },
    getTarget(params) {
      return cachedRequest('get', '/dashboard/target', { params, useCache: true })
    },
    getTraffic(params) {
      return cachedRequest('get', '/dashboard/traffic', { params, useCache: true })
    },
    getKpiCards(params) {
      return cachedRequest('get', '/dashboard/kpi-cards', { params, useCache: true })
    },
    getTrend(params) {
      return cachedRequest('get', '/dashboard/trend', { params, useCache: true })
    }
  },

  trafficApi: {
    getKeywords(params) {
      return cachedRequest('get', '/traffic/keywords', { params, useCache: true })
    },
    getKeywordsStats(params) {
      return cachedRequest('get', '/traffic/keywords/stats', { params, useCache: true })
    },
    getFunnel(params) {
      return cachedRequest('get', '/traffic/funnel', { params, useCache: true })
    },
    getFunnelTrend(params) {
      return cachedRequest('get', '/traffic/funnel/trend', { params, useCache: true })
    },
    getCompetitor(params) {
      return cachedRequest('get', '/traffic/competitor', { params, useCache: true })
    }
  },

  productsApi: {
    getRanking(params) {
      return cachedRequest('get', '/products/ranking', { params, useCache: true })
    },
    getProfit(params) {
      return cachedRequest('get', '/products/profit', { params, useCache: true })
    },
    getReviews(params) {
      return cachedRequest('get', '/products/reviews', { params, useCache: true })
    },
    getMatrix(params) {
      return cachedRequest('get', '/products/matrix', { params, useCache: true })
    },
    getSummary() {
      return cachedRequest('get', '/products/summary', { useCache: true })
    }
  },

  supplyApi: {
    getInventory(params) {
      return cachedRequest('get', '/supply/inventory', { params, useCache: true })
    },
    getInventoryStats() {
      return cachedRequest('get', '/supply/inventory/stats', { useCache: true })
    },
    getSlowMoving(params) {
      return cachedRequest('get', '/supply/slow-moving', { params, useCache: true })
    },
    getSlowMovingStats() {
      return cachedRequest('get', '/supply/slow-moving/stats', { useCache: true })
    }
  },

  adsApi: {
    getCampaigns(params) {
      return cachedRequest('get', '/ads/campaigns', { params, useCache: true })
    },
    getAipl(params) {
      return cachedRequest('get', '/ads/aipl', { params, useCache: true })
    },
    getAiplTrend(params) {
      return cachedRequest('get', '/ads/aipl/trend', { params, useCache: true })
    },
    getDmp(params) {
      return cachedRequest('get', '/ads/dmp', { params, useCache: true })
    },
    getSummary() {
      return cachedRequest('get', '/ads/summary', { useCache: true })
    }
  },

  alertsApi: {
    getRules(params) {
      return cachedRequest('get', '/alerts/rules', { params, useCache: true })
    },
    createRule(data) {
      return request.post('/alerts/rules', data)
    },
    updateRule(ruleId, data) {
      return request.put(`/alerts/rules/${ruleId}`, data)
    },
    deleteRule(ruleId) {
      return request.delete(`/alerts/rules/${ruleId}`)
    },
    getRecords(params) {
      return cachedRequest('get', '/alerts/records', { params, useCache: true })
    },
    updateRecord(recordId, data) {
      return request.put(`/alerts/records/${recordId}`, data)
    },
    getStats() {
      return cachedRequest('get', '/alerts/stats', { useCache: true })
    }
  },

  tasksApi: {
    getTasks(params) {
      return cachedRequest('get', '/tasks', { params, useCache: true })
    },
    createTask(data) {
      return request.post('/tasks', data)
    },
    updateTask(taskId, data) {
      return request.put(`/tasks/${taskId}`, data)
    },
    deleteTask(taskId) {
      return request.delete(`/tasks/${taskId}`)
    },
    getStats() {
      return cachedRequest('get', '/tasks/stats', { useCache: true })
    }
  },

  kpisApi: {
    getKpis(params) {
      return cachedRequest('get', '/kpis', { params, useCache: true })
    },
    getStats() {
      return cachedRequest('get', '/kpis/stats', { useCache: true })
    }
  }
}
