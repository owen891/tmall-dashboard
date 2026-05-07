import { ref, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'

export function useRequest(options = {}) {
  const { defaultErrorMsg = '请求失败', showError = true } = options
  
  const loading = ref(false)
  const error = ref(null)
  const abortControllers = new Set()
  
  const createAbortController = () => {
    const controller = new AbortController()
    abortControllers.add(controller)
    return controller
  }
  
  const clearAbortControllers = () => {
    abortControllers.forEach(controller => controller.abort())
    abortControllers.clear()
  }
  
  const execute = async (requestFn, opts = {}) => {
    const { 
      errorMsg = defaultErrorMsg, 
      showErr = showError,
      fallbackData = null,
      onSuccess = null,
      onError = null
    } = opts
    
    loading.value = true
    error.value = null
    
    try {
      const controller = createAbortController()
      const result = await requestFn(controller.signal)
      
      if (onSuccess) onSuccess(result)
      return result
    } catch (err) {
      if (err.name === 'AbortError' || err.message?.includes('cancel')) {
        return null
      }
      
      error.value = err
      const message = err.response?.data?.detail || err.message || errorMsg
      
      if (showErr) {
        ElMessage.error(`${errorMsg}: ${message}`)
      }
      
      if (onError) onError(err)
      
      if (fallbackData !== undefined) {
        return fallbackData
      }
      
      throw err
    } finally {
      loading.value = false
    }
  }
  
  onBeforeUnmount(() => {
    clearAbortControllers()
  })
  
  return {
    loading,
    error,
    execute,
    clearAbortControllers
  }
}

export function useLoading() {
  const loading = ref(false)
  const submitting = ref(false)
  const exporting = ref(false)
  
  const withLoading = async (fn) => {
    loading.value = true
    try {
      return await fn()
    } finally {
      loading.value = false
    }
  }
  
  const withSubmitting = async (fn) => {
    submitting.value = true
    try {
      return await fn()
    } finally {
      submitting.value = false
    }
  }
  
  const withExporting = async (fn) => {
    exporting.value = true
    try {
      return await fn()
    } finally {
      exporting.value = false
    }
  }
  
  return {
    loading,
    submitting,
    exporting,
    withLoading,
    withSubmitting,
    withExporting
  }
}

export function useDebounce(fn, delay = 300) {
  let timer = null
  
  const debounced = (...args) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      fn(...args)
    }, delay)
  }
  
  const cancel = () => {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }
  
  onBeforeUnmount(() => {
    cancel()
  })
  
  return { debounced, cancel }
}
