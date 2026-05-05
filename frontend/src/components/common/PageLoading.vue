<template>
  <div v-if="visible" class="page-loading">
    <div v-if="type === 'page'" class="page-loading-overlay">
      <el-icon class="is-loading" :size="32" color="#409eff"><Loading /></el-icon>
      <p class="loading-text">{{ text }}</p>
    </div>
    <div v-else-if="type === 'table'" class="table-loading-overlay">
      <el-icon class="is-loading" :size="28" color="#409eff"><Loading /></el-icon>
      <p class="loading-text">{{ text }}</p>
    </div>
    <div v-else class="spin-loading">
      <el-icon class="is-loading" :size="24" color="#409eff"><Loading /></el-icon>
    </div>
  </div>
</template>

<script setup>
import { Loading } from '@element-plus/icons-vue'

defineProps({
  visible: { type: Boolean, default: true },
  type: { type: String, default: 'page', validator: (v) => ['page', 'table', 'spin'].includes(v) },
  text: { type: String, default: '加载中...' },
})
</script>

<style scoped>
.page-loading {
  width: 100%;
}
.page-loading-overlay {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 8px;
}
.table-loading-overlay {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}
.spin-loading {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.loading-text {
  margin-top: 12px;
  color: #909399;
  font-size: 14px;
}
:deep(.dark) .page-loading-overlay {
  background: rgba(20, 20, 20, 0.8);
}
:deep(.dark) .loading-text {
  color: #8c8c8c;
}
</style>
