<template>
  <div class="global-time-filter">
    <el-select 
      v-model="selectedRange" 
      @change="handleRangeChange"
      size="small"
      style="width: 120px;"
    >
      <el-option label="今日" value="today" />
      <el-option label="昨日" value="yesterday" />
      <el-option label="本周" value="this_week" />
      <el-option label="上周" value="last_week" />
      <el-option label="本月" value="this_month" />
      <el-option label="上月" value="last_month" />
      <el-option label="近7天" value="last_7_days" />
      <el-option label="近30天" value="last_30_days" />
      <el-option label="自定义" value="custom" />
    </el-select>
    
    <el-date-picker
      v-if="selectedRange === 'custom'"
      v-model="customRange"
      type="daterange"
      range-separator="-"
      start-placeholder="开始日期"
      end-placeholder="结束日期"
      size="small"
      style="width: 240px; margin-left: 8px;"
      @change="handleCustomChange"
    />
    
    <span v-if="dateDisplay" class="date-display">
      {{ dateDisplay }}
    </span>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useTimeStore } from '@/stores/time'
import { formatDate } from '@/utils/date'

const timeStore = useTimeStore()
const selectedRange = ref('last_30_days')
const customRange = ref([])

const dateDisplay = computed(() => {
  if (timeStore.startDate && timeStore.endDate) {
    const start = formatDate(timeStore.startDate)
    const end = formatDate(timeStore.endDate)
    return `${start} 至 ${end}`
  }
  return ''
})

const handleRangeChange = (value) => {
  if (value !== 'custom') {
    const range = timeStore.calculateDateRange(value)
    timeStore.setDateRange(range.start, range.end)
    timeStore.setSelectedRange(value)
  }
}

const handleCustomChange = (value) => {
  if (value && value.length === 2) {
    timeStore.setDateRange(value[0], value[1])
    timeStore.setSelectedRange('custom')
  }
}

onMounted(() => {
  const loaded = timeStore.loadFromLocalStorage()
  if (loaded) {
    selectedRange.value = timeStore.selectedRange
    if (selectedRange.value === 'custom' && timeStore.startDate && timeStore.endDate) {
      customRange.value = [timeStore.startDate, timeStore.endDate]
    }
  } else {
    handleRangeChange('last_30_days')
  }
})

watch(() => timeStore.selectedRange, (newVal) => {
  selectedRange.value = newVal
})
</script>

<style scoped>
.global-time-filter {
  display: flex;
  align-items: center;
  gap: 8px;
}

.date-display {
  font-size: 13px;
  color: #666;
  margin-left: 8px;
}
</style>
