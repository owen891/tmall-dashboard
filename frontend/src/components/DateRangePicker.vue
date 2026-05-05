<template>
  <div class="date-range-picker">
    <!-- 快捷选项和日期显示 -->
    <div class="quick-range-bar">
      <span class="current-range-text">
        (统计时间: {{ displayRangeText }})
      </span>
      <div class="quick-actions">
        <button 
          v-for="action in quickActions" 
          :key="action.key"
          :class="['quick-btn', { active: currentQuickAction === action.key }]"
          @click="selectQuickAction(action)"
        >
          {{ action.label }}
        </button>
        <div class="dim-group">
          <button 
            v-for="dim in dimensionOptions" 
            :key="dim.value"
            :class="['dim-btn', { active: currentDim === dim.value }]"
            @click="setDimension(dim.value)"
          >
            {{ dim.label }}
          </button>
        </div>
        <button class="nav-btn" @click="navigate(-1)">‹</button>
        <button class="nav-btn" @click="navigate(1)">›</button>
        <button 
          :class="['custom-btn', { active: showCalendar }]"
          @click="toggleCalendar"
        >
          自定义
          <el-icon><InfoFilled /></el-icon>
        </button>
      </div>
    </div>

    <!-- 双月日历面板 -->
    <transition name="calendar-fade">
      <div v-if="showCalendar" class="calendar-panel">
        <div class="calendar-months">
          <!-- 上个月 -->
          <div class="calendar-month">
            <div class="month-header">
              <button class="month-nav" @click="changeMonth(0, -1)">«</button>
              <span class="month-title">{{ formatMonthTitle(0) }}</span>
              <button class="month-nav" @click="changeMonth(0, 1)">»</button>
            </div>
            <div class="weekdays">
              <span v-for="day in weekDays" :key="day" class="weekday">{{ day }}</span>
            </div>
            <div class="days-grid">
              <div 
                v-for="day in calendarDays[0]" 
                :key="day.dateStr"
                :class="[
                  'day-cell',
                  { 
                    'other-month': !day.currentMonth,
                    'selected': isSelectedDay(day.dateStr),
                    'in-range': isInRange(day.dateStr),
                    'range-start': isRangeStart(day.dateStr),
                    'range-end': isRangeEnd(day.dateStr)
                  }
                ]"
                @click="selectDay(day.dateStr)"
              >
                {{ day.day }}
              </div>
            </div>
          </div>

          <!-- 下个月 -->
          <div class="calendar-month">
            <div class="month-header">
              <button class="month-nav" @click="changeMonth(1, -1)">«</button>
              <span class="month-title">{{ formatMonthTitle(1) }}</span>
              <button class="month-nav" @click="changeMonth(1, 1)">»</button>
            </div>
            <div class="weekdays">
              <span v-for="day in weekDays" :key="day" class="weekday">{{ day }}</span>
            </div>
            <div class="days-grid">
              <div 
                v-for="day in calendarDays[1]" 
                :key="day.dateStr"
                :class="[
                  'day-cell',
                  { 
                    'other-month': !day.currentMonth,
                    'selected': isSelectedDay(day.dateStr),
                    'in-range': isInRange(day.dateStr),
                    'range-start': isRangeStart(day.dateStr),
                    'range-end': isRangeEnd(day.dateStr)
                  }
                ]"
                @click="selectDay(day.dateStr)"
              >
                {{ day.day }}
              </div>
            </div>
          </div>
        </div>
        <div class="calendar-footer">
          <span class="range-hint">* 最少选择 1 天，最多选择 31 天</span>
          <div class="calendar-actions">
            <button class="btn-cancel" @click="cancelSelection">取消</button>
            <button class="btn-confirm" @click="confirmSelection">确定</button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { InfoFilled } from '@element-plus/icons-vue'
import { useTimeStore } from '@/stores/time'
import api from '@/api'

const timeStore = useTimeStore()

const weekDays = ['一', '二', '三', '四', '五', '六', '日']

const dimensionOptions = [
  { label: '日', value: 'daily' },
  { label: '周', value: 'weekly' },
  { label: '月', value: 'monthly' },
  { label: '年', value: 'yearly' }
]

const quickActions = [
  { label: '7天', key: '7days', days: 7 },
  { label: '30天', key: '30days', days: 30 }
]

const currentDim = ref(timeStore.dimension || 'daily')
const showCalendar = ref(false)
const currentQuickAction = ref('7days')
const tempStartDate = ref('')
const tempEndDate = ref('')
const calendarBaseDate = ref(new Date())

const calendarDays = computed(() => [
  generateMonthDays(calendarBaseDate.value.getFullYear(), calendarBaseDate.value.getMonth()),
  generateMonthDays(
    calendarBaseDate.value.getFullYear(), 
    calendarBaseDate.value.getMonth() + 1
  )
])

const displayRangeText = computed(() => {
  const start = timeStore.startDate
  const end = timeStore.endDate
  if (!start) return '--'
  if (start === end) return formatDateDisplay(start)
  return `${formatDateDisplay(start)} ~ ${formatDateDisplay(end)}`
})

function generateMonthDays(year, month) {
  const days = []
  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0)
  
  let startDayOfWeek = firstDay.getDay()
  if (startDayOfWeek === 0) startDayOfWeek = 7
  startDayOfWeek--
  
  const prevMonthLastDay = new Date(year, month, 0).getDate()
  for (let i = startDayOfWeek - 1; i >= 0; i--) {
    const day = prevMonthLastDay - i
    const date = new Date(year, month - 1, day)
    days.push({
      day,
      dateStr: formatDate(date),
      currentMonth: false
    })
  }
  
  for (let d = 1; d <= lastDay.getDate(); d++) {
    const date = new Date(year, month, d)
    days.push({
      day: d,
      dateStr: formatDate(date),
      currentMonth: true
    })
  }
  
  const remaining = 42 - days.length
  for (let d = 1; d <= remaining; d++) {
    const date = new Date(year, month + 1, d)
    days.push({
      day: d,
      dateStr: formatDate(date),
      currentMonth: false
    })
  }
  
  return days
}

function formatDate(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatDateDisplay(dateStr) {
  if (!dateStr) return '--'
  const parts = dateStr.split('-')
  if (parts.length >= 3) {
    return `${parts[1]}月${parseInt(parts[2])}日`
  }
  return dateStr
}

function formatMonthTitle(offset) {
  const date = new Date(calendarBaseDate.value)
  date.setMonth(date.getMonth() + offset)
  const year = date.getFullYear()
  const month = date.getMonth() + 1
  return `${year} 年 ${month} 月`
}

function isSelectedDay(dateStr) {
  return dateStr === tempStartDate.value || dateStr === tempEndDate.value
}

function isInRange(dateStr) {
  if (!tempStartDate.value || !tempEndDate.value) return false
  return dateStr > tempStartDate.value && dateStr < tempEndDate.value
}

function isRangeStart(dateStr) {
  return dateStr === tempStartDate.value
}

function isRangeEnd(dateStr) {
  return dateStr === tempEndDate.value
}

function selectQuickAction(action) {
  currentQuickAction.value = action.key
  showCalendar.value = false
  
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - action.days + 1)
  
  tempStartDate.value = formatDate(start)
  tempEndDate.value = formatDate(end)
  
  timeStore.setDateRange(tempStartDate.value, tempEndDate.value)
}

function selectDay(dateStr) {
  if (!tempStartDate.value || (tempStartDate.value && tempEndDate.value)) {
    tempStartDate.value = dateStr
    tempEndDate.value = ''
  } else {
    if (dateStr < tempStartDate.value) {
      tempEndDate.value = tempStartDate.value
      tempStartDate.value = dateStr
    } else {
      const diff = dateDiff(tempStartDate.value, dateStr)
      if (diff > 31) {
        tempEndDate.value = addDays(tempStartDate.value, 31)
      } else {
        tempEndDate.value = dateStr
      }
    }
  }
}

function confirmSelection() {
  if (!tempStartDate.value) return
  
  if (!tempEndDate.value) {
    tempEndDate.value = tempStartDate.value
  }
  
  timeStore.setDateRange(tempStartDate.value, tempEndDate.value)
  showCalendar.value = false
  currentQuickAction.value = 'custom'
}

function cancelSelection() {
  tempStartDate.value = timeStore.startDate || ''
  tempEndDate.value = timeStore.endDate || ''
  showCalendar.value = false
}

function toggleCalendar() {
  showCalendar.value = !showCalendar.value
  if (showCalendar.value) {
    tempStartDate.value = timeStore.startDate || formatDate(new Date())
    tempEndDate.value = timeStore.endDate || ''
    calendarBaseDate.value = new Date()
  }
}

function changeMonth(offset, direction) {
  const date = new Date(calendarBaseDate.value)
  if (offset === 0) {
    date.setMonth(date.getMonth() + direction)
  } else {
    date.setMonth(date.getMonth() + direction)
  }
  calendarBaseDate.value = date
}

function navigate(direction) {
  const days = getRangeDays()
  const end = new Date(timeStore.endDate || new Date())
  const start = new Date(timeStore.startDate || end)
  
  end.setDate(end.getDate() + direction * days)
  start.setDate(start.getDate() + direction * days)
  
  tempStartDate.value = formatDate(start)
  tempEndDate.value = formatDate(end)
  
  timeStore.setDateRange(tempStartDate.value, tempEndDate.value)
}

function getRangeDays() {
  if (currentQuickAction.value === '7days') return 7
  if (currentQuickAction.value === '30days') return 30
  return 7
}

function dateDiff(start, end) {
  const s = new Date(start)
  const e = new Date(end)
  return Math.floor((e - s) / (1000 * 60 * 60 * 24))
}

function addDays(dateStr, days) {
  const d = new Date(dateStr)
  d.setDate(d.getDate() + days)
  return formatDate(d)
}

function setDimension(dim) {
  currentDim.value = dim
  timeStore.setDimension(dim)
}

onMounted(() => {
  const today = formatDate(new Date())
  const weekAgo = addDays(today, -6)
  
  if (!timeStore.startDate) {
    tempStartDate.value = weekAgo
    tempEndDate.value = today
    timeStore.setDateRange(weekAgo, today)
  } else {
    tempStartDate.value = timeStore.startDate
    tempEndDate.value = timeStore.endDate
  }
})
</script>

<style scoped>
.date-range-picker {
  position: relative;
}

.quick-range-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: #f5f7fa;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}

.current-range-text {
  font-size: 13px;
  color: #606266;
  white-space: nowrap;
}

.quick-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.quick-btn {
  padding: 4px 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 12px;
  color: #606266;
  border-radius: 4px;
  transition: all 0.2s;
}

.quick-btn:hover {
  background: #e6e8eb;
}

.quick-btn.active {
  background: #409eff;
  color: #fff;
}

.dim-group {
  display: flex;
  background: #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
  margin: 0 4px;
}

.dim-btn {
  padding: 4px 10px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 12px;
  color: #606266;
  transition: all 0.2s;
}

.dim-btn:hover {
  background: #d0d4db;
}

.dim-btn.active {
  background: #409eff;
  color: #fff;
}

.nav-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 16px;
  color: #606266;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.nav-btn:hover {
  background: #e6e8eb;
  color: #409eff;
}

.custom-btn {
  padding: 4px 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 12px;
  color: #606266;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.2s;
}

.custom-btn:hover {
  background: #e6e8eb;
}

.custom-btn.active {
  background: #ecf5ff;
  color: #409eff;
  border: 1px solid #409eff;
}

.calendar-panel {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.12);
  padding: 16px;
  z-index: 1000;
  min-width: 560px;
}

.calendar-months {
  display: flex;
  gap: 16px;
}

.calendar-month {
  flex: 1;
}

.month-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.month-nav {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  color: #606266;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.month-nav:hover {
  background: #f0f2f5;
  color: #409eff;
}

.month-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
  margin-bottom: 8px;
}

.weekday {
  text-align: center;
  font-size: 12px;
  color: #909399;
  padding: 4px 0;
}

.days-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
}

.day-cell {
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: #303133;
  border-radius: 50%;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.day-cell:hover:not(.other-month) {
  background: #ecf5ff;
  color: #409eff;
}

.day-cell.other-month {
  color: #c0c4cc;
  cursor: default;
}

.day-cell.selected {
  background: #409eff;
  color: #fff;
  font-weight: 600;
}

.day-cell.in-range {
  background: #ecf5ff;
  border-radius: 0;
}

.day-cell.range-start {
  background: #409eff;
  color: #fff;
  font-weight: 600;
  border-radius: 50% 0 0 50%;
}

.day-cell.range-end {
  background: #409eff;
  color: #fff;
  font-weight: 600;
  border-radius: 0 50% 50% 0;
}

.calendar-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
}

.range-hint {
  font-size: 11px;
  color: #909399;
}

.calendar-actions {
  display: flex;
  gap: 8px;
}

.btn-cancel,
.btn-confirm {
  padding: 6px 16px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}

.btn-cancel {
  background: #fff;
  color: #606266;
}

.btn-cancel:hover {
  border-color: #c0c4cc;
  color: #409eff;
}

.btn-confirm {
  background: #409eff;
  color: #fff;
  border-color: #409eff;
}

.btn-confirm:hover {
  background: #66b1ff;
}

.calendar-fade-enter-active,
.calendar-fade-leave-active {
  transition: all 0.25s ease;
}

.calendar-fade-enter-from,
.calendar-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

:deep(.dark) .quick-range-bar {
  background: #1f1f1f;
  border-color: #333;
}

:deep(.dark) .current-range-text {
  color: #a0a0a0;
}

:deep(.dark) .quick-btn,
:deep(.dark) .dim-btn,
:deep(.dark) .nav-btn,
:deep(.dark) .custom-btn {
  color: #a0a0a0;
}

:deep(.dark) .quick-btn:hover,
:deep(.dark) .dim-btn:hover,
:deep(.dark) .nav-btn:hover,
:deep(.dark) .custom-btn:hover {
  background: #333;
}

:deep(.dark) .dim-group {
  background: #333;
}

:deep(.dark) .calendar-panel {
  background: #1f1f1f;
}

:deep(.dark) .month-title {
  color: #e0e0e0;
}

:deep(.dark) .month-nav {
  color: #a0a0a0;
}

:deep(.dark) .month-nav:hover {
  background: #333;
}

:deep(.dark) .weekday {
  color: #666;
}

:deep(.dark) .day-cell {
  color: #e0e0e0;
}

:deep(.dark) .day-cell.other-month {
  color: #555;
}

:deep(.dark) .day-cell:hover:not(.other-month) {
  background: #2a2a2a;
}

:deep(.dark) .day-cell.in-range {
  background: #2a2a2a;
}

:deep(.dark) .calendar-footer {
  border-top-color: #333;
}

:deep(.dark) .range-hint {
  color: #666;
}

:deep(.dark) .btn-cancel {
  background: #1f1f1f;
  border-color: #333;
  color: #a0a0a0;
}

:deep(.dark) .btn-confirm {
  background: #409eff;
  border-color: #409eff;
}
</style>
