<template>
  <div class="chart-container" :class="{ 'chart-bordered': bordered }">
    <div class="chart-header" v-if="title || $slots.actions">
      <div class="chart-title-area">
        <h3 v-if="title" class="chart-title">
          <el-icon v-if="icon" class="chart-icon"><component :is="icon" /></el-icon>
          {{ title }}
        </h3>
        <el-tooltip v-if="tooltip" :content="tooltip" placement="top" :show-after="300">
          <el-icon class="chart-tooltip-icon"><QuestionFilled /></el-icon>
        </el-tooltip>
        <span v-if="subtitle" class="chart-subtitle">{{ subtitle }}</span>
      </div>
      <div class="chart-actions">
        <slot name="actions"></slot>
        <el-button-group v-if="dimensionButtons.length > 0" size="small">
          <el-button
            v-for="btn in dimensionButtons"
            :key="btn.dim"
            :type="activeDimension === btn.dim ? 'primary' : 'default'"
            @click="handleDimensionChange(btn.dim)"
          >
            {{ btn.label }}
          </el-button>
        </el-button-group>
        <el-button 
          v-if="refreshable" 
          :icon="refreshing ? Loading : Refresh" 
          circle 
          size="small" 
          :loading="refreshing"
          @click="handleRefresh" 
        />
      </div>
    </div>
    
    <div class="chart-content" :class="{ 'is-loading': loading }">
      <div v-if="loading" class="chart-loading-overlay">
        <el-skeleton :rows="4" animated />
      </div>
      <div v-else-if="empty" class="chart-empty">
        <el-empty 
          :description="emptyText" 
          :image-size="emptyImageSize"
          :image="emptyImage"
        >
          <el-button 
            v-if="emptyActionText" 
            type="primary" 
            size="small" 
            @click="$emit('empty-action')"
          >
            {{ emptyActionText }}
          </el-button>
        </el-empty>
      </div>
      <div v-else class="chart-body" :style="{ height: height }">
        <slot></slot>
      </div>
    </div>
    
    <div v-if="footer || $slots.footer" class="chart-footer">
      <slot name="footer">{{ footer }}</slot>
    </div>
    
    <div v-if="showStats" class="chart-stats">
      <div class="stat-item" v-for="(stat, index) in stats" :key="index">
        <div class="stat-label">{{ stat.label }}</div>
        <div class="stat-value" :class="stat.class">{{ stat.value }}</div>
        <div v-if="stat.change" class="stat-change" :class="getChangeClass(stat.change)">
          <el-icon><component :is="getChangeIcon(stat.change)" /></el-icon>
          {{ Math.abs(stat.change) }}%
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { QuestionFilled, Refresh, Loading, Top, Bottom, CaretRight } from '@element-plus/icons-vue'

const props = defineProps({
  title: { type: String, default: '' },
  icon: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  tooltip: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  empty: { type: Boolean, default: false },
  emptyText: { type: String, default: '暂无数据' },
  emptyImage: { type: String, default: '' },
  emptyImageSize: { type: Number, default: 120 },
  emptyActionText: { type: String, default: '' },
  footer: { type: String, default: '' },
  refreshable: { type: Boolean, default: false },
  bordered: { type: Boolean, default: true },
  height: { type: String, default: '300px' },
  dimensions: { type: Array, default: () => [] },
  defaultDimension: { type: String, default: '' },
  showStats: { type: Boolean, default: false },
  stats: { type: Array, default: () => [] },
})

const emit = defineEmits(['refresh', 'dimension-change', 'empty-action'])

const refreshing = ref(false)
const activeDimension = ref(props.defaultDimension || props.dimensions[0]?.dim || '')

const dimensionButtons = computed(() => {
  if (!props.dimensions || props.dimensions.length === 0) return []
  return props.dimensions.map(d => ({
    dim: d,
    label: d === 'daily' ? '日' : d === 'weekly' ? '周' : d === 'monthly' ? '月' : d
  }))
})

function handleDimensionChange(dim) {
  activeDimension.value = dim
  emit('dimension-change', dim)
}

function handleRefresh() {
  refreshing.value = true
  emit('refresh')
  setTimeout(() => {
    refreshing.value = false
  }, 500)
}

function getChangeClass(change) {
  if (change > 0) return 'text-success'
  if (change < 0) return 'text-danger'
  return ''
}

function getChangeIcon(change) {
  if (change > 0) return Top
  if (change < 0) return Bottom
  return CaretRight
}
</script>

<style scoped>
.chart-container {
  background: white;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  margin-bottom: 16px;
  transition: all 0.3s;
}

.chart-container:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.chart-container.chart-bordered {
  border: 1px solid #ebeef5;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  gap: 12px;
}

.chart-title-area {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.chart-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 6px;
}

.chart-icon {
  color: #409eff;
  font-size: 18px;
}

.chart-tooltip-icon {
  color: #c0c4cc;
  cursor: help;
  font-size: 14px;
  transition: color 0.2s;
}

.chart-tooltip-icon:hover {
  color: #409eff;
}

.chart-subtitle {
  font-size: 12px;
  color: #909399;
}

.chart-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.chart-content {
  min-height: 200px;
  position: relative;
  transition: opacity 0.3s;
}

.chart-content.is-loading {
  opacity: 0.5;
}

.chart-loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.8);
  z-index: 10;
  border-radius: 8px;
  padding: 20px;
}

.chart-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}

.chart-body {
  width: 100%;
  position: relative;
}

.chart-footer {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #ebeef5;
  font-size: 12px;
  color: #909399;
}

.chart-stats {
  display: flex;
  gap: 16px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
  flex-wrap: wrap;
}

.stat-item {
  flex: 1;
  min-width: 100px;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 6px;
}

.stat-label {
  font-size: 11px;
  color: #909399;
  margin-bottom: 4px;
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.stat-change {
  font-size: 11px;
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 2px;
}

.text-success {
  color: #67c23a;
}

.text-danger {
  color: #f56c6c;
}

:deep(.dark) .chart-container {
  background: #1f1f1f;
}

:deep(.dark) .chart-container.chart-bordered {
  border-color: #333;
}

:deep(.dark) .chart-title {
  color: #e0e0e0;
}

:deep(.dark) .chart-subtitle,
:deep(.dark) .chart-footer,
:deep(.dark) .stat-label {
  color: #8c8c8c;
}

:deep(.dark) .chart-footer {
  border-top-color: #333;
}

:deep(.dark) .chart-loading-overlay {
  background: rgba(20, 20, 20, 0.8);
}

:deep(.dark) .stat-item {
  background: #2a2a2a;
}

:deep(.dark) .stat-value {
  color: #e0e0e0;
}

:deep(.dark) .chart-stats {
  border-top-color: #333;
}
</style>
