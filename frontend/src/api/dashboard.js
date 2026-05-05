import request, { cachedRequest } from './request'

export default {
  getSummary(params) {
    return request.get('/dashboard/summary', { params })
  },

  getTopProducts(params) {
    return cachedRequest('get', '/dashboard/top-products', { params, useCache: true })
  },

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
  },

  getLegacyDashboard(params) {
    return cachedRequest('get', '/dashboard', { params, useCache: true })
  },

  getQuadrantData() {
    return cachedRequest('get', '/dashboard/quadrant', { useCache: true })
  }
}
