import request, { cachedRequest } from './request'

export default {
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

  getInventoryWarnings(params) {
    return request.get('/inventory/warnings', { params })
  },

  getInventorySummary(params) {
    return request.get('/inventory/summary', { params })
  },

  getInventoryVelocity(params) {
    return request.get('/inventory/velocity', { params })
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

  getAlerts(params) {
    return request.get('/alerts', { params })
  }
}
