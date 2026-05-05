<template>
  <el-dropdown @command="handleCommand">
    <el-button :type="type" :size="size">
      <el-icon><Download /></el-icon>
      <span>{{ buttonText }}</span>
      <el-icon class="el-icon--right"><ArrowDown /></el-icon>
    </el-button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="excel" :disabled="!tableData || tableData.length === 0">
          <el-icon><Document /></el-icon>
          导出Excel
        </el-dropdown-item>
        <el-dropdown-item command="csv" :disabled="!tableData || tableData.length === 0">
          <el-icon><DocumentCopy /></el-icon>
          导出CSV
        </el-dropdown-item>
        <el-dropdown-item 
          v-if="chartInstance" 
          command="png"
          :divided="true"
        >
          <el-icon><Picture /></el-icon>
          导出图表PNG
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup>
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, ArrowDown, Document, DocumentCopy, Picture } from '@element-plus/icons-vue'
import { exportTableToExcel, exportToCSV, exportChartToPNG } from '@/utils/export'

const props = defineProps({
  tableData: {
    type: Array,
    default: () => []
  },
  chartInstance: {
    type: Object,
    default: null
  },
  fileName: {
    type: String,
    default: 'export'
  },
  buttonText: {
    type: String,
    default: '导出'
  },
  type: {
    type: String,
    default: 'default'
  },
  size: {
    type: String,
    default: 'default'
  },
  columns: {
    type: Array,
    default: null
  }
})

const emit = defineEmits(['export-success', 'export-error'])

const handleCommand = (command) => {
  try {
    switch (command) {
      case 'excel':
        exportAsExcel()
        break
      case 'csv':
        exportAsCSV()
        break
      case 'png':
        exportAsPNG()
        break
    }
  } catch (error) {
    ElMessage.error('导出失败：' + error.message)
    emit('export-error', error)
  }
}

const transformData = () => {
  if (!props.tableData || props.tableData.length === 0) return null
  if (!props.columns) return props.tableData
  return props.tableData.map(row => {
    const obj = {}
    props.columns.forEach(col => {
      obj[col.label] = row[col.prop]
    })
    return obj
  })
}

const exportAsExcel = () => {
  const dataToExport = transformData()
  if (!dataToExport) {
    ElMessage.warning('没有可导出的数据')
    return
  }
  exportTableToExcel(dataToExport, props.fileName)
  ElMessage.success('导出成功')
  emit('export-success', { type: 'excel', fileName: props.fileName })
}

const exportAsCSV = () => {
  const dataToExport = transformData()
  if (!dataToExport) {
    ElMessage.warning('没有可导出的数据')
    return
  }
  exportToCSV(dataToExport, props.fileName)
  ElMessage.success('导出成功')
  emit('export-success', { type: 'csv', fileName: props.fileName })
}

const exportAsPNG = () => {
  if (!props.chartInstance) {
    ElMessage.warning('没有可导出的图表')
    return
  }
  
  exportChartToPNG(props.chartInstance, props.fileName)
  ElMessage.success('图表导出成功')
  emit('export-success', { type: 'png', fileName: props.fileName })
}
</script>

<style scoped>
.el-dropdown {
  margin-left: 12px;
}
</style>
