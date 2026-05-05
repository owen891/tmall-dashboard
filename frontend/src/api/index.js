import request, { cachedRequest } from './request'
import apiCache from '@/utils/cache'

export default {
  getPeriods(dim = 'weekly') {
    return request.get('/periods', { params: { dim } })
  },
  getDashboardSummary() {
    return cachedRequest('get', '/dashboard/summary', { useCache: true })
  },
  getTopProducts(params) {
    return cachedRequest('get', '/dashboard/top-products', { params, useCache: true })
  },
  getQuadrantData() {
    return cachedRequest('get', '/dashboard/quadrant', { useCache: true })
  },

  getProducts(params) {
    const { page, page_size, ...rest } = params || {}
    if (page) rest.page = page
    if (page_size) rest.page_size = page_size
    return request.get('/products', {
      params: {
        ...rest
      }
    })
  },
  getFilterOptions() {
    return request.get('/products/categories')
  },
  getProduct(productId) {
    return request.get(`/products/${productId}`)
  },
  getProductDetail(productId) {
    return request.get(`/products/${productId}/detail`)
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
  getProductLifecycle(productId) {
    return request.get(`/products/${productId}/lifecycle`)
  },
  updateProductLifecycle(productId, data) {
    return request.post(`/products/${productId}/lifecycle`, data)
  },
  getBatchLifecycle(productIds) {
    return request.get('/products/lifecycle/batch', { params: { product_ids: productIds } })
  },

  getKPI(params) {
    return request.get('/kpi', { params })
  },
  getKPISummary(params) {
    return request.get('/kpi/summary', { params })
  },
  getKPIAnomalies(params) {
    return request.get('/kpi/anomalies', { params })
  },
  getKPIDimensions() {
    return request.get('/kpi/dimensions')
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
    },
    getComparison() {
      return cachedRequest('get', '/ads/comparison', { useCache: true })
    },
    getProducts() {
      return cachedRequest('get', '/ads/products', { useCache: true })
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
