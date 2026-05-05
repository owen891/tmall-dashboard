import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

export function usePageData(fetchFn, options = {}) {
  const loading = ref(false)
  const data = ref(null)
  const error = ref(null)
  const { autoFetch = true, errorMessage = '加载失败' } = options

  async function fetchData(...args) {
    loading.value = true
    error.value = null
    try {
      data.value = await fetchFn(...args)
    } catch (e) {
      error.value = e.message || '未知错误'
      ElMessage.error(errorMessage + (e.message ? `: ${e.message}` : ''))
    } finally {
      loading.value = false
    }
  }

  if (autoFetch) {
    onMounted(() => fetchData())
  }

  return { loading, data, error, fetchData }
}

export function useTable(options = {}) {
  const tableData = ref([])
  const loading = ref(false)
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(options.defaultPageSize || 20)
  const { fetchFn, errorMessage = '加载数据失败' } = options

  async function loadData() {
    loading.value = true
    try {
      const result = await fetchFn(page.value, pageSize.value)
      tableData.value = result.data || result.list || []
      total.value = result.total || tableData.value.length
    } catch (e) {
      ElMessage.error(errorMessage + (e.message ? `: ${e.message}` : ''))
    } finally {
      loading.value = false
    }
  }

  function handlePageChange(p) {
    page.value = p
    loadData()
  }

  function handleSizeChange(s) {
    pageSize.value = s
    page.value = 1
    loadData()
  }

  return {
    tableData, loading, total, page, pageSize,
    loadData, handlePageChange, handleSizeChange,
  }
}

export function useConfirm(message = '确定执行此操作吗？', title = '提示') {
  return ElMessageBox.confirm(message, title, {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(() => true).catch(() => false)
}

export function formatNumber(num, options = {}) {
  if (num == null || num === '') return '-'
  const { decimals = 2, unit = '' } = options
  const n = Number(num)
  if (isNaN(n)) return '-'
  
  if (n >= 100000000) return (n / 100000000).toFixed(decimals) + '亿'
  if (n >= 10000) return (n / 10000).toFixed(decimals) + '万'
  if (n >= 1000) return n.toLocaleString()
  return n % 1 === 0 ? String(n) : n.toFixed(decimals)
}

export function formatPercent(val, decimals = 2) {
  if (val == null || val === '') return '-'
  const n = Number(val)
  if (isNaN(n)) return '-'
  return (n * 100).toFixed(decimals) + '%'
}

export function getStatusType(status) {
  const map = {
    'success': 'success',
    'warning': 'warning',
    'error': 'danger',
    'info': 'info',
    'active': 'success',
    'inactive': 'info',
    'pending': 'warning',
    'completed': 'success',
    'failed': 'danger',
    'running': '',
    'planned': 'info',
    'unresolved': 'danger',
    'resolved': 'success',
  }
  return map[status?.toLowerCase()] || 'info'
}

export function getStatusLabel(status) {
  const map = {
    'success': '成功',
    'warning': '警告',
    'error': '错误',
    'info': '信息',
    'active': '启用',
    'inactive': '停用',
    'pending': '待处理',
    'completed': '已完成',
    'failed': '失败',
    'running': '运行中',
    'planned': '计划中',
    'unresolved': '未解决',
    'resolved': '已解决',
  }
  return map[status?.toLowerCase()] || status || '-'
}
