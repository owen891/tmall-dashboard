import { ElNotification } from 'element-plus'

const ERROR_MESSAGES = {
  400: '请求参数错误',
  401: '未授权，请重新登录',
  403: '没有权限访问',
  404: '请求的资源不存在',
  422: '数据验证失败',
  429: '请求过于频繁，请稍后再试',
  500: '服务器内部错误',
  502: '网关错误',
  503: '服务暂不可用',
}

export function setupGlobalErrorHandler(app) {
  app.config.errorHandler = (err, instance, info) => {
    console.error('Vue Error:', err)
    console.error('Component:', instance?.$options?.name || 'Unknown')
    console.error('Info:', info)
    
    ElNotification({
      title: '页面错误',
      message: err.message || '未知错误',
      type: 'error',
      duration: 5000,
    })
  }

  window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled Promise Rejection:', event.reason)
    
    const status = event.reason?.response?.status
    if (status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
      return
    }
    
    const message = ERROR_MESSAGES[status] || event.reason?.message || '未知错误'
    
    ElNotification({
      title: '请求错误',
      message,
      type: 'error',
      duration: 4000,
    })
    
    event.preventDefault()
  })

  window.addEventListener('error', (event) => {
    console.error('Global Error:', event.error)
  })
}
