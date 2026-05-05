<template>
  <div class="stat-card" @click="$emit('click')">
    <div class="stat-card-header">
      <span class="stat-card-title">{{ title }}</span>
      <el-tooltip v-if="tooltip" :content="tooltip" placement="top">
        <el-icon class="stat-card-tooltip"><QuestionFilled /></el-icon>
      </el-tooltip>
    </div>
    <div class="stat-card-body">
      <div class="stat-card-value" :class="valueClass">
        {{ displayValue }}
        <span v-if="unit" class="stat-unit">{{ unit }}</span>
      </div>
      <div class="stat-card-footer">
        <el-tag v-if="trend" :type="trendType" size="small" class="stat-trend">
          <el-icon><component :is="trendIcon" /></el-icon>
          {{ trend }}
        </el-tag>
        <span v-if="subtitle" class="stat-subtitle">{{ subtitle }}</span>
      </div>
    </div>
    <div v-if="footer" class="stat-card-footer-line">{{ footer }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { QuestionFilled, Top, Bottom, CaretRight } from '@element-plus/icons-vue'

const props = defineProps({
  title: { type: String, required: true },
  value: { type: [Number, String], required: true },
  unit: { type: String, default: '' },
  tooltip: { type: String, default: '' },
  trend: { type: String, default: '' },
  trendType: { type: String, default: 'success' },
  subtitle: { type: String, default: '' },
  footer: { type: String, default: '' },
  valueClass: { type: String, default: '' },
})

const displayValue = computed(() => {
  if (typeof props.value === 'number') {
    if (props.value >= 1000000) return (props.value / 1000000).toFixed(2) + 'M'
    if (props.value >= 10000) return (props.value / 10000).toFixed(2) + 'W'
    if (props.value >= 1000) return props.value.toLocaleString()
    if (props.value % 1 !== 0) return props.value.toFixed(2)
  }
  return props.value
})

const trendIcon = computed(() => {
  if (!props.trend) return CaretRight
  if (props.trend.includes('+') || props.trend.includes('上升')) return Top
  if (props.trend.includes('-') || props.trend.includes('下降')) return Bottom
  return CaretRight
})
</script>

<style scoped>
.stat-card {
  background: white;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: all 0.3s;
  cursor: default;
}
.stat-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}
.stat-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.stat-card-title {
  font-size: 13px;
  color: #909399;
  font-weight: 500;
}
.stat-card-tooltip {
  color: #c0c4cc;
  cursor: help;
}
.stat-card-value {
  font-size: 24px;
  font-weight: 700;
  color: #303133;
  line-height: 1.2;
}
.stat-unit {
  font-size: 14px;
  font-weight: 400;
  color: #909399;
  margin-left: 4px;
}
.stat-card-footer {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.stat-trend {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.stat-subtitle {
  font-size: 12px;
  color: #909399;
}
.stat-card-footer-line {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #ebeef5;
  font-size: 12px;
  color: #909399;
}
:deep(.dark) .stat-card {
  background: #1f1f1f;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}
:deep(.dark) .stat-card-value {
  color: #e0e0e0;
}
:deep(.dark) .stat-card-title,
:deep(.dark) .stat-subtitle,
:deep(.dark) .stat-card-footer-line {
  color: #8c8c8c;
}
:deep(.dark) .stat-card-footer-line {
  border-top-color: #333;
}
</style>
