import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'

export function useToast() {
  function success(message, options = {}) {
    return ElMessage.success({
      message,
      duration: 3000,
      ...options
    })
  }

  function error(message, options = {}) {
    return ElMessage.error({
      message,
      duration: 5000,
      ...options
    })
  }

  function warning(message, options = {}) {
    return ElMessage.warning({
      message,
      duration: 4000,
      ...options
    })
  }

  function info(message, options = {}) {
    return ElMessage.info({
      message,
      duration: 3000,
      ...options
    })
  }

  function loading(message, options = {}) {
    return ElMessage({
      message,
      type: 'info',
      duration: 0,
      showClose: true,
      ...options
    })
  }

  function confirm(message, title = '确认', options = {}) {
    return ElMessageBox.confirm(message, title, {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
      ...options
    })
  }

  function notify(title, message, type = 'info', options = {}) {
    return ElNotification({
      title,
      message,
      type,
      duration: 4500,
      ...options
    })
  }

  return { success, error, warning, info, loading, confirm, notify }
}

export const toast = useToast()

export default useToast
