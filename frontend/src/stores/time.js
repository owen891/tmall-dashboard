import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useTimeStore = defineStore('time', () => {
  const startDate = ref(null)
  const endDate = ref(null)
  const selectedRange = ref('last_30_days')

  const dateRange = computed(() => ({
    start: startDate.value,
    end: endDate.value
  }))

  function setDateRange(start, end) {
    startDate.value = start
    endDate.value = end
    saveToLocalStorage()
  }

  function setSelectedRange(range) {
    selectedRange.value = range
    saveToLocalStorage()
  }

  function saveToLocalStorage() {
    const data = {
      startDate: startDate.value,
      endDate: endDate.value,
      selectedRange: selectedRange.value
    }
    localStorage.setItem('timeRange', JSON.stringify(data))
  }

  function loadFromLocalStorage() {
    const data = localStorage.getItem('timeRange')
    if (data) {
      const parsed = JSON.parse(data)
      startDate.value = parsed.startDate
      endDate.value = parsed.endDate
      selectedRange.value = parsed.selectedRange
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
      case 'yesterday':
        const yesterday = new Date(today)
        yesterday.setDate(yesterday.getDate() - 1)
        start = yesterday
        end = yesterday
        break
      case 'this_week':
        const dayOfWeek = today.getDay() || 7
        const weekStart = new Date(today)
        weekStart.setDate(weekStart.getDate() - dayOfWeek + 1)
        start = weekStart
        end = today
        break
      case 'last_week':
        const lastWeekEnd = new Date(today)
        lastWeekEnd.setDate(lastWeekEnd.getDate() - (today.getDay() || 7))
        const lastWeekStart = new Date(lastWeekEnd)
        lastWeekStart.setDate(lastWeekStart.getDate() - 6)
        start = lastWeekStart
        end = lastWeekEnd
        break
      case 'this_month':
        const monthStart = new Date(today.getFullYear(), today.getMonth(), 1)
        start = monthStart
        end = today
        break
      case 'last_month':
        const lastMonthEnd = new Date(today.getFullYear(), today.getMonth(), 0)
        const lastMonthStart = new Date(today.getFullYear(), today.getMonth() - 1, 1)
        start = lastMonthStart
        end = lastMonthEnd
        break
      case 'last_7_days':
        const last7 = new Date(today)
        last7.setDate(last7.getDate() - 6)
        start = last7
        end = today
        break
      case 'last_30_days':
        const last30 = new Date(today)
        last30.setDate(last30.getDate() - 29)
        start = last30
        end = today
        break
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
    dateRange,
    setDateRange,
    setSelectedRange,
    loadFromLocalStorage,
    calculateDateRange
  }
})
