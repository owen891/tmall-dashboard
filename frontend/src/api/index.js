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
    return request.get('/products', { params })
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
  getProductTags(productId) {
    return request.get(`/products/${productId}/tags`)
  },
  addProductTag(productId, tag) {
    return request.post(`/products/${productId}/tags`, null, { params: { tag } })
  },
  removeProductTag(productId, tag) {
    return request.delete(`/products/${productId}/tags/${tag}`)
  },
  toggleProductStar(productId) {
    return request.post(`/products/${productId}/star`)
  },
  getFilterOptions() {
    return request.get('/products/filters/options')
  },
  importExcel(file, weekStart) {
    const formData = new FormData()
    formData.append('file', file)
    if (weekStart) {
      formData.append('week_start', weekStart)
    }
    return request.post('/import/excel', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }
}
