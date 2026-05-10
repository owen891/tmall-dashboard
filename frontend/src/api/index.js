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
  dismissAnomaly(anomalyId) {
    return request.post(`/kpi/anomalies/${anomalyId}/dismiss`)
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
  getTrendsData(productId, dimension) {
    const params = { dimension }
    if (productId) params.product_id = productId
    return request.get('/trends/data', { params })
  },
  getTrendEvents(params) {
    return cachedRequest('get', '/trends/events', { params, useCache: true })
  },
  addTrendEvent(data) {
    return request.post('/trends/events', data)
  },
  deleteTrendEvent(eventId) {
    return request.delete(`/trends/events/${eventId}`)
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

  getProductRecommendations(params) {
    return cachedRequest('get', '/recommendations/products', { params, useCache: true })
  },
  getPriceOptimizations(params) {
    return cachedRequest('get', '/recommendations/price', { params, useCache: true })
  },
  getKeywordRecommendations(params) {
    return cachedRequest('get', '/recommendations/keywords', { params, useCache: true })
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
  },

  abtestSopApi: {
    getTests(params) {
      return cachedRequest('get', '/abtest-sop/tests', { params, useCache: true })
    },
    getSopTemplates(params) {
      return cachedRequest('get', '/abtest-sop/sop-templates', { params, useCache: true })
    },
    getCampaignProjects(params) {
      return cachedRequest('get', '/abtest-sop/campaign-projects', { params, useCache: true })
    },
    createTest(data) {
      return request.post('/abtest-sop/tests', data)
    },
    analyzeTest(testId) {
      return request.post(`/abtest-sop/tests/${testId}/analyze`)
    }
  },

  aiAnalyticsApi: {
    generateReport(params) {
      return request.post('/ai-analytics/report', params)
    },
    executeQuery(params) {
      return request.post('/ai-analytics/query', params)
    },
    getReportHistory(params) {
      return cachedRequest('get', '/ai-analytics/reports', { params, useCache: true })
    },
    getReport(reportId) {
      return request.get(`/ai-analytics/reports/${reportId}`)
    }
  },

  crowdAssetApi: {
    getDashboard() {
      return cachedRequest('get', '/crowd-asset/dashboard', { useCache: true })
    },
    getCampaigns(params) {
      return cachedRequest('get', '/crowd-asset/campaigns', { params, useCache: true })
    },
    getCampaignDetail(campaignId) {
      return request.get(`/crowd-asset/campaigns/${campaignId}`)
    },
    getCrowds(params) {
      return cachedRequest('get', '/crowd-asset/crowds', { params, useCache: true })
    },
    getEfficiencyMatrix() {
      return cachedRequest('get', '/crowd-asset/efficiency-matrix', { useCache: true })
    },
    updateCrowdBid(crowdId, bidRatio) {
      return request.post(`/crowd-asset/crowds/${crowdId}/update-bid`, { bid_ratio: bidRatio })
    }
  },

  funnelApi: {
    getOverview(params) {
      return cachedRequest('get', '/funnel/overview', { params, useCache: true })
    },
    getBySource(params) {
      return cachedRequest('get', '/funnel/by-source', { params, useCache: true })
    },
    getDropAnalysis(params) {
      return cachedRequest('get', '/funnel/drop-analysis', { params, useCache: true })
    }
  },

  backupApi: {
    getList() {
      return request.get('/backup/list')
    },
    create(data) {
      return request.post('/backup/create', data)
    },
    restore(backupId) {
      return request.post(`/backup/${backupId}/restore`)
    },
    download(backupId) {
      return request.get(`/backup/${backupId}/download`, { responseType: 'blob' })
    },
    delete(backupId) {
      return request.delete(`/backup/${backupId}`)
    }
  },

  getSettings() {
    return request.get('/settings')
  },
  updateSettings(data) {
    return request.put('/settings', data)
  },
  initializeSettings() {
    return request.post('/settings/init')
  },

  getPrediction(params) {
    return request.get('/prediction/overview', { params })
  },
  getImportHistory(params) {
    return request.get('/imports/history', { params })
  },
  startImport(data) {
    return request.post('/imports/upload', data)
  },
  getImportTemplates() {
    return request.get('/imports/templates')
  },

  get(url, params) {
    return request.get(url, { params })
  },
  post(url, data) {
    return request.post(url, data)
  },
  put(url, data) {
    return request.put(url, data)
  },
  delete(url) {
    return request.delete(url)
  },
  request
}
