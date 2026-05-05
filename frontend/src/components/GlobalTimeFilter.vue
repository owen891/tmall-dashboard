<template>
  <div class="global-time-filter">
    <div class="dim-switcher">
      <button 
        v-for="dim in dimensions" 
        :key="dim.value"
        :class="['dim-btn', { active: currentDim === dim.value }]"
        @click="switchDimension(dim.value)"
      >
        {{ dim.label }}
      </button>
    </div>
    
    <el-select 
      v-model="selectedPeriod" 
      @change="handlePeriodChange"
      size="small"
      class="period-select"
      placeholder="选择周期"
    >
      <el-option 
        v-for="period in periods" 
        :key="period.value" 
        :label="period.label" 
        :value="period.value" 
      />
    </el-select>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useTimeStore } from '@/stores/time'
import api from '@/api'

const timeStore = useTimeStore()

const dimensions = [
  { label: '日', value: 'daily' },
  { label: '周', value: 'weekly' },
  { label: '月', value: 'monthly' }
]

const currentDim = ref('weekly')
const periods = ref([])
const periodsCache = ref({})

const selectedPeriod = computed({
  get: () => timeStore.selectedPeriod,
  set: (val) => timeStore.setSelectedPeriod(val)
})

const loadPeriods = async (dim) => {
  if (periodsCache.value[dim]) {
    periods.value = periodsCache.value[dim]
    return
  }
  
  try {
    const res = await api.getPeriods(dim)
    const periodData = res.data?.periods || res.data || []
    if (Array.isArray(periodData)) {
      const periodList = periodData.map(p => ({
        value: p,
        label: formatPeriodLabel(p, dim)
      }))
      periodsCache.value[dim] = periodList
      periods.value = periodList
      
      if (periodList.length > 0) {
        const savedPeriod = timeStore.selectedPeriod
        if (savedPeriod && periodList.find(p => p.value === savedPeriod)) {
          selectedPeriod.value = savedPeriod
          handlePeriodChange(savedPeriod)
        } else {
          selectedPeriod.value = periodList[0].value
          handlePeriodChange(periodList[0].value)
        }
      }
    }
  } catch (e) {
    console.error('Failed to load periods:', e)
  }
}

const formatPeriodLabel = (period, dim) => {
  if (!period) return ''
  
  if (dim === 'daily') {
    return period
  } else if (dim === 'weekly') {
    if (period.includes('-W')) {
      return period.replace('-W', ' 第') + '周'
    }
    return period
  } else if (dim === 'monthly') {
    if (period.includes('-')) {
      const parts = period.split('-')
      if (parts.length >= 2) {
        return `${parts[0]}年${parseInt(parts[1])}月`
      }
    }
    return period + '月'
  }
  return period
}

const getISOWeekDates = (year, weekNumber) => {
  const jan4 = new Date(year, 0, 4)
  const dayOfWeek = jan4.getDay() || 7
  const firstMonday = new Date(jan4)
  firstMonday.setDate(jan4.getDate() - dayOfWeek + 1)
  
  const targetMonday = new Date(firstMonday)
  targetMonday.setDate(firstMonday.getDate() + (weekNumber - 1) * 7)
  
  const sunday = new Date(targetMonday)
  sunday.setDate(targetMonday.getDate() + 6)
  
  return { start: targetMonday, end: sunday }
}

const switchDimension = (dim) => {
  currentDim.value = dim
  timeStore.setDimension(dim)
  loadPeriods(dim)
}

const handlePeriodChange = (period) => {
  if (!period) return
  
  let startDate, endDate
  
  if (currentDim.value === 'daily') {
    startDate = period
    endDate = period
  } else if (currentDim.value === 'weekly') {
    if (period.includes('-W')) {
      const [yearStr, weekStr] = period.split('-W')
      const year = parseInt(yearStr)
      const weekNumber = parseInt(weekStr)
      const { start, end } = getISOWeekDates(year, weekNumber)
      startDate = formatDateStr(start)
      endDate = formatDateStr(end)
    } else {
      startDate = period
      endDate = period
    }
  } else if (currentDim.value === 'monthly') {
    const parts = period.split('-')
    if (parts.length >= 2) {
      const year = parseInt(parts[0])
      const month = parseInt(parts[1])
      const lastDay = new Date(year, month, 0).getDate()
      startDate = `${year}-${String(month).padStart(2, '0')}-01`
      endDate = `${year}-${String(month).padStart(2, '0')}-${lastDay}`
    } else {
      startDate = period
      endDate = period
    }
  }
  
  timeStore.setDateRange(startDate, endDate)
  timeStore.setSelectedPeriod(period)
}

const formatDateStr = (date) => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

onMounted(() => {
  const savedDim = timeStore.dimension || 'weekly'
  currentDim.value = savedDim
  loadPeriods(savedDim)
})
</script>

<style scoped>
.global-time-filter {
  display: flex;
  align-items: center;
  gap: 12px;
}

.dim-switcher {
  display: flex;
  background: #f0f2f5;
  border-radius: 4px;
  overflow: hidden;
}

.dim-btn {
  padding: 6px 16px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  color: #606266;
  transition: all 0.2s;
}

.dim-btn:hover {
  background: #e6e8eb;
}

.dim-btn.active {
  background: #409eff;
  color: #fff;
}

.period-select {
  width: 160px;
}
</style>
