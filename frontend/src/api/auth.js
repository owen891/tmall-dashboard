import request, { cachedRequest, CACHE_DURATION } from './request'

export default {
  login(data) {
    const formData = new URLSearchParams()
    formData.append('username', data.username)
    formData.append('password', data.password)
    return request.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
  },

  register(data) {
    return request.post('/auth/register', data)
  },

  getCurrentUser() {
    return cachedRequest('get', '/auth/me', { useCache: true, cacheDuration: 60 * 1000 })
  },

  listUsers(params) {
    return request.get('/auth/users', { params })
  },

  updateUser(userId, data) {
    return request.patch(`/auth/users/${userId}`, data)
  },

  initAdmin() {
    return request.post('/auth/init-admin')
  },

  getToken() {
    return localStorage.getItem('token')
  },

  setToken(token) {
    localStorage.setItem('token', token)
  },

  removeToken() {
    localStorage.removeItem('token')
  },

  isAuthenticated() {
    return !!localStorage.getItem('token')
  }
}
