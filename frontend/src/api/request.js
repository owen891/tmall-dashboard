import axios from 'axios'
import apiCache from '@/utils/cache'
import { ApiError, handleError } from '@/utils/errorHandler'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

const CACHE_DURATION = 5 * 60 * 1000
const pendingRequests = new Map()

const getRequestKey = (config) => {
  return `${config.method}:${config.url}:${JSON.stringify(config.params || {})}:${JSON.stringify(config.data || {})}`
}

request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    
    const timeRange = localStorage.getItem('timeRange')
    if (timeRange && config.params) {
      try {
        const parsed = JSON.parse(timeRange)
        if (parsed.startDate && parsed.endDate) {
          config.params.start_date = parsed.startDate
          config.params.end_date = parsed.endDate
        }
      } catch (e) {}
    }
    
    const requestKey = getRequestKey(config)
    
    if (pendingRequests.has(requestKey)) {
      const cancelToken = pendingRequests.get(requestKey)
      cancelToken.cancel('重复请求取消')
      pendingRequests.delete(requestKey)
    }
    
    const cancelToken = axios.CancelToken.source()
    config.cancelToken = cancelToken.token
    pendingRequests.set(requestKey, cancelToken)
    
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

request.interceptors.response.use(
  (response) => {
    const requestKey = getRequestKey(response.config)
    pendingRequests.delete(requestKey)
    return response.data
  },
  (error) => {
    if (!axios.isCancel(error)) {
      const requestKey = getRequestKey(error.config || {})
      pendingRequests.delete(requestKey)
    }
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

const cancelAllRequests = () => {
  pendingRequests.forEach((cancelToken) => {
    cancelToken.cancel('页面切换取消所有请求')
  })
  pendingRequests.clear()
}

export default request
export { cachedRequest, CACHE_DURATION, cancelAllRequests }
