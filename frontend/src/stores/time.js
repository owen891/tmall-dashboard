import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useTimeStore = defineStore('time', () => {
  const startDate = ref(null)
  const endDate = ref(null)
  const dimension = ref('weekly')
  const preset = ref('month')

  const dateRange = computed(() => ({
    startDate: startDate.value,
    endDate: endDate.value
  }))

  const hasRange = computed(() => !!(startDate.value && endDate.value))

  function setDateRange(start, end) {
    startDate.value = start
    endDate.value = end
  }

  function setPreset(presetValue) {
    preset.value = presetValue
    const now = new Date()
    const end = now.toISOString().split('T')[0]
    let start

    switch (presetValue) {
      case 'today':
        start = end
        break
      case 'week': {
        const d = new Date(now)
        d.setDate(d.getDate() - 7)
        start = d.toISOString().split('T')[0]
        break
      }
      case 'month': {
        const d = new Date(now)
        d.setMonth(d.getMonth() - 1)
        start = d.toISOString().split('T')[0]
        break
      }
      case '30days': {
        const d = new Date(now)
        d.setDate(d.getDate() - 30)
        start = d.toISOString().split('T')[0]
        break
      }
      case '90days': {
        const d = new Date(now)
        d.setDate(d.getDate() - 90)
        start = d.toISOString().split('T')[0]
        break
      }
      default:
        start = end
    }

    startDate.value = start
    endDate.value = end
  }

  function setDimension(dim) {
    dimension.value = dim
  }

  function clearRange() {
    startDate.value = null
    endDate.value = null
    preset.value = null
  }

  setPreset('month')

  return {
    startDate,
    endDate,
    dimension,
    preset,
    dateRange,
    hasRange,
    setDateRange,
    setPreset,
    setDimension,
    clearRange
  }
})
