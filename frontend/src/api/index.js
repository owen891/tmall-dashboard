import axios from 'axios'

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

export default {
  getDashboardSummary() {
    return request.get('/dashboard/summary')
  },
  getTopProducts() {
    return request.get('/dashboard/top-products')
  },
  getQuadrantData() {
    return request.get('/dashboard/quadrant')
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
  addProductNote(productId, note, createdBy = 'admin') {
    return request.post(`/products/${productId}/notes`, { 
      note, created_by: createdBy 
    })
  },
  deleteProductNote(productId, noteId) {
    return request.delete(`/products/${productId}/notes/${noteId}`)
  },
  getProductTags(productId) {
    return request.get(`/products/${productId}/tags`)
  },
  addProductTag(productId, tag) {
    return request.post(`/products/${productId}/tags`, { tag })
  },
  removeProductTag(productId, tagId) {
    return request.delete(`/products/${productId}/tags/${tagId}`)
  },
  toggleProductStar(productId) {
    return request.post(`/products/${productId}/star`)
  },
  updateProductField(productId, field, value) {
    return request.patch(`/products/${productId}`, { 
      field, value 
    })
  },
  batchUpdateProducts(productIds, updates) {
    return request.post('/products/batch-update', { 
      product_ids: productIds, 
      ...updates 
    })
  },
  getFilterOptions() {
    return request.get('/products/filters/options')
  },
  getCategories() {
    return request.get('/products/categories')
  },
  importExcel(file, weekStart) {
    const formData = new FormData()
    formData.append('file', file)
    if (weekStart) {
      formData.append('week_start', weekStart)
    }
    return request.post('/import/excel', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: weekStart ? { week_start: weekStart } : {}
    })
  },
  previewImport(formData) {
    return request.post('/import/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  getImportHistory(params) {
    return request.get('/import/history', { params })
  },
  getPeriods(dim = 'weekly') {
    return request.get('/periods', { params: { dim } })
  },
  getSystemStatus() {
    return request.get('/status')
  },
  getCompareData(dim, period1, period2) {
    return request.get('/compare', { 
      params: { dim, period1, period2 } 
    })
  },
  getActions(productId, limit, offset) {
    return request.get('/actions', { 
      params: { product_id: productId, limit, offset } 
    })
  },
  addAction(productId, actionDate, actionType, actionDetail) {
    return request.post('/actions', { 
      product_id: productId, action_date: actionDate, action_type: actionType, action_detail: actionDetail 
    })
  },
  createAction(actionData) {
    return request.post('/actions', actionData)
  },
  deleteAction(actionId) {
    return request.delete(`/actions/${actionId}`)
  },
  getActionStats(period) {
    return request.get('/action-stats', { params: { period } })
  },
  exportProducts(params) {
    return request.get('/export/products', { 
      params, 
      responseType: 'blob' 
    })
  },
  getKPISummary(dimension = 'weekly') {
    return request.get('/kpi/summary', { params: { dimension } })
  },
  getKPIAnomalies(params) {
    return request.get('/kpi/anomalies', { params })
  },
  dismissAnomaly(alertId) {
    return request.post(`/kpi/anomalies/${alertId}/dismiss`)
  },
  getTrendsData(productId, dimension = 'weekly') {
    if (productId) {
      return request.get(`/trends/product/${productId}`, { params: { dimension } })
    }
    return request.get('/trends/shop', { params: { dimension } })
  },
  getTrendEvents() {
    return request.get('/trends/events')
  },
  addTrendEvent(eventData) {
    return request.post('/trends/events', eventData)
  },
  deleteTrendEvent(eventId) {
    return request.delete(`/trends/events/${eventId}`)
  },
  getHealthList() {
    return request.get('/health/list')
  },
  getHealthDistribution() {
    return request.get('/health/distribution')
  },
  refreshHealthScore(productId) {
    return request.post(`/health/refresh/${productId}`)
  },
  getPromotionPlans(params) {
    return request.get('/promotion/plans', { params })
  },
  getSearchEfficiency(params) {
    return request.get('/promotion/search-efficiency', { params })
  },
  getPromotionProducts() {
    return request.get('/promotion/products')
  },
  getLifecycleStats() {
    return request.get('/lifecycle/stats')
  },
  getLifecycleDistribution() {
    return request.get('/lifecycle/distribution')
  },
  getLifecycleProducts(stage) {
    return request.get('/lifecycle/products', { params: { stage } })
  },
  getCompareSummary(params) {
    return request.get('/compare/summary', { params })
  },
  getCompareDetail() {
    return request.get('/compare/detail')
  },
  getCompareTrend(params) {
    return request.get('/compare/trend', { params })
  },
  getMarketTrends(category) {
    return request.get('/market/trends', { params: { category } })
  },
  getPriceDistribution(category) {
    return request.get('/market/price-distribution', { params: { category } })
  },
  getTopBrands(category) {
    return request.get('/market/top-brands', { params: { category } })
  },
  getCompetitionAnalysis(category) {
    return request.get('/market/competition', { params: { category } })
  },
  getProductRecommendations(params) {
    return request.get('/recommendation/products', { params })
  },
  getPriceOptimizations(params) {
    return request.get('/recommendation/price-optimization', { params })
  },
  getCrossSellOpportunities(productId, limit = 5) {
    return request.get('/recommendation/cross-sell', { params: { product_id: productId, limit } })
  },
  getKeywordRecommendations(params) {
    return request.get('/recommendation/keywords', { params })
  },
  getWeeklyReport(period) {
    return request.get('/reports/weekly-summary', { params: { period } })
  },
  getMonthlyReport(month) {
    return request.get('/reports/monthly-summary', { params: { month } })
  },
  getHealthReport(period) {
    return request.get('/reports/health-report', { params: { period } })
  },
  getAlertSummary(days) {
    return request.get('/reports/alert-summary', { params: { days } })
  },
  exportReportJson(type, period) {
    return request.get('/reports/export/json', { params: { report_type: type, period } })
  },
  getRealtimeSummary() {
    return request.get('/realtime/summary')
  },
  getRealtimeTopProducts(limit) {
    return request.get('/realtime/top-products', { params: { limit } })
  },
  getPrediction(params) {
    return request.get('/prediction/gmv', { params })
  },
  getSalesPrediction(params) {
    return request.get('/prediction/sales', { params })
  },
  getStockPrediction(productId, leadTime) {
    return request.get('/prediction/stock', { params: { product_id: productId, lead_time: leadTime } })
  },
  getTeamMembers() {
    return request.get('/collaboration/team')
  },
  getActivityLog(limit) {
    return request.get('/collaboration/activity-log', { params: { limit } })
  },
  createActivityLog(action, detail, operator) {
    return request.post('/collaboration/activity-log', { action, detail, operator })
  },
  getDataQualityOverview() {
    return request.get('/data-quality/overview')
  },
  getMissingValues(period) {
    return request.get('/data-quality/missing-values', { params: { period } })
  },
  getDataAnomalies(period) {
    return request.get('/data-quality/anomalies', { params: { period } })
  },
  getBackupStatus() {
    return request.get('/backup/status')
  },
  createBackup() {
    return request.post('/backup/create')
  },
  deleteBackup(filename) {
    return request.delete(`/backup/delete/${filename}`)
  }
}
