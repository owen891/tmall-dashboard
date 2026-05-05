import request, { cachedRequest } from './request'

export default {
  getList(params) {
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

  getFilterOptions() {
    return cachedRequest('get', '/products/categories', { useCache: true })
  },

  getDetail(productId, params) {
    return request.get(`/products/${productId}`, { params })
  },

  getWeeklyData(productId) {
    return request.get(`/products/${productId}/weekly-data`)
  },

  getOperations(productId) {
    return request.get(`/products/${productId}/operations`)
  },

  getNotes(productId) {
    return request.get(`/products/${productId}/notes`)
  },

  getLifecycle(productId) {
    return request.get(`/products/${productId}/lifecycle`)
  },

  updateLifecycle(productId, data) {
    return request.post(`/products/${productId}/lifecycle`, data)
  },

  getBatchLifecycle(productIds) {
    return request.get('/products/lifecycle/batch', { params: { product_ids: productIds } })
  },

  updateField(productId, field, value) {
    return request.patch(`/products/${productId}`, { field, value })
  },

  batchUpdate(productIds, updates) {
    return request.post('/products/batch-update', { product_ids: productIds, ...updates })
  },

  getTags(productId) {
    return request.get(`/products/${productId}/tags`)
  },

  addTag(productId, tag) {
    return request.post(`/products/${productId}/tags`, { tag })
  },

  deleteTag(productId, tagId) {
    return request.delete(`/products/${productId}/tags/${tagId}`)
  },

  addNote(productId, note, createdBy = 'admin') {
    return request.post(`/products/${productId}/notes`, { note, created_by: createdBy })
  },

  deleteNote(productId, noteId) {
    return request.delete(`/products/${productId}/notes/${noteId}`)
  },

  createAction(data) {
    return request.post('/products/actions', data)
  },

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
  },

  getTopProducts(params) {
    return cachedRequest('get', '/products/top', { params, useCache: true })
  }
}
