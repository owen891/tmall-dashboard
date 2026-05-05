import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import authApi from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(authApi.getToken())
  const loading = ref(false)

  const isAuthenticated = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isManager = computed(() => user.value?.role === 'manager' || user.value?.role === 'admin')
  const userRole = computed(() => user.value?.role || 'viewer')

  async function login(credentials) {
    loading.value = true
    try {
      const response = await authApi.login(credentials)
      token.value = response.access_token
      authApi.setToken(token.value)
      await fetchCurrentUser()
      return true
    } catch (error) {
      throw error
    } finally {
      loading.value = false
    }
  }

  async function fetchCurrentUser() {
    try {
      const response = await authApi.getCurrentUser()
      user.value = response
    } catch (error) {
      logout()
    }
  }

  function logout() {
    user.value = null
    token.value = null
    authApi.removeToken()
  }

  async function init() {
    if (token.value) {
      await fetchCurrentUser()
    }
  }

  return {
    user,
    token,
    loading,
    isAuthenticated,
    isAdmin,
    isManager,
    userRole,
    login,
    logout,
    fetchCurrentUser,
    init
  }
})
