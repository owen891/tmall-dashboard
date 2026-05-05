import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const STORAGE_KEY = 'timeStore'

function persist(state) {
  const data = {
    startDate: state.startDate,
    endDate: state.endDate,
    selectedRange: state.selectedRange,
    dimension: state.dimension,
    selectedPeriod: state.selectedPeriod,
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
}

function restore() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export const useTimeStore = defineStore('time', () => {
  const saved = restore()

  const startDate = ref(saved?.startDate || null)
  const endDate = ref(saved?.endDate || null)
  const selectedRange = ref(saved?.selectedRange || 'last_30_days')
  const dimension = ref(saved?.dimension || 'weekly')
  const selectedPeriod = ref(saved?.selectedPeriod || '')

  const dateRange = computed(() => ({
    start: startDate.value,
    end: endDate.value
  }))

  function _persist() {
    persist({
      startDate: startDate.value,
      endDate: endDate.value,
      selectedRange: selectedRange.value,
      dimension: dimension.value,
      selectedPeriod: selectedPeriod.value,
    })
  }

  function setDateRange(start, end) {
    startDate.value = start
    endDate.value = end
    _persist()
  }

  function setSelectedRange(range) {
    selectedRange.value = range
    _persist()
  }

  function setDimension(dim) {
    dimension.value = dim
    _persist()
  }

  function setSelectedPeriod(period) {
    selectedPeriod.value = period
    _persist()
  }

  function loadFromLocalStorage() {
    const data = restore()
    if (data) {
      startDate.value = data.startDate
      endDate.value = data.endDate
      selectedRange.value = data.selectedRange
      dimension.value = data.dimension || 'weekly'
      selectedPeriod.value = data.selectedPeriod || ''
      return true
    }
    return false
  }

  function calculateDateRange(rangeType) {
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())

    let start, end

    switch (rangeType) {
      case 'today':
        start = today
        end = today
        break
      case 'yesterday': {
        const yesterday = new Date(today)
        yesterday.setDate(yesterday.getDate() - 1)
        start = yesterday
        end = yesterday
        break
      }
      case 'this_week': {
        const dayOfWeek = today.getDay() || 7
        const weekStart = new Date(today)
        weekStart.setDate(weekStart.getDate() - dayOfWeek + 1)
        start = weekStart
        end = today
        break
      }
      case 'last_week': {
        const lastWeekEnd = new Date(today)
        lastWeekEnd.setDate(lastWeekEnd.getDate() - (today.getDay() || 7))
        const lastWeekStart = new Date(lastWeekEnd)
        lastWeekStart.setDate(lastWeekStart.getDate() - 6)
        start = lastWeekStart
        end = lastWeekEnd
        break
      }
      case 'this_month': {
        const monthStart = new Date(today.getFullYear(), today.getMonth(), 1)
        start = monthStart
        end = today
        break
      }
      case 'last_month': {
        const lastMonthEnd = new Date(today.getFullYear(), today.getMonth(), 0)
        const lastMonthStart = new Date(today.getFullYear(), today.getMonth() - 1, 1)
        start = lastMonthStart
        end = lastMonthEnd
        break
      }
      case 'last_7_days': {
        const last7 = new Date(today)
        last7.setDate(last7.getDate() - 6)
        start = last7
        end = today
        break
      }
      case 'last_30_days': {
        const last30 = new Date(today)
        last30.setDate(last30.getDate() - 29)
        start = last30
        end = today
        break
      }
      case 'last_90_days': {
        const last90 = new Date(today)
        last90.setDate(last90.getDate() - 89)
        start = last90
        end = today
        break
      }
      default:
        start = today
        end = today
    }

    return { start, end }
  }

  return {
    startDate,
    endDate,
    selectedRange,
    dimension,
    selectedPeriod,
    dateRange,
    setDateRange,
    setSelectedRange,
    setDimension,
    setSelectedPeriod,
    loadFromLocalStorage,
    calculateDateRange
  }
})
