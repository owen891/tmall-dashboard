import { ElMessage, ElNotification } from 'element-plus'

const ERROR_MESSAGES = {
  400: '请求参数错误',
  401: '未授权，请重新登录',
  403: '拒绝访问',
  404: '请求的资源不存在',
  408: '请求超时',
  500: '服务器内部错误',
  502: '网关错误',
  503: '服务不可用',
  504: '网关超时',
}

export class ApiError extends Error {
  constructor(message, code, data = null) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.data = data
  }
}

export const handleError = (error, options = {}) => {
  const { silent = false, title = '错误' } = options

  console.error('API Error:', error)

  if (silent) return

  if (error instanceof ApiError) {
    ElNotification({
      title,
      message: error.message,
      type: 'error',
      duration: 5000,
    })
    return
  }

  if (error.response) {
    const status = error.response.status
    const message = ERROR_MESSAGES[status] || error.response.data?.message || '请求失败'
    ElMessage.error(message)
    return
  }

  if (error.request) {
    ElMessage.error('网络错误，请检查网络连接')
    return
  }

  ElMessage.error(error.message || '未知错误')
}

export const withErrorHandling = async (fn, options = {}) => {
  try {
    return await fn()
  } catch (error) {
    handleError(error, options)
    throw error
  }
}

export const retryWithBackoff = async (fn, maxRetries = 3, delay = 1000) => {
  const isRetryable = (error) => {
    if (!error) return false
    if (error.code === 'ERR_NETWORK' || error.code === 'ECONNABORTED') return true
    const status = error?.response?.status
    if (!status) return true
    return status >= 500
  }

  let lastError
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn()
    } catch (error) {
      lastError = error
      if (!isRetryable(error) || i >= maxRetries - 1) {
        throw error
      }
      const jitter = delay * Math.pow(2, i) * (0.5 + Math.random() * 0.5)
      await new Promise((resolve) => setTimeout(resolve, jitter))
    }
  }
  throw lastError
}
