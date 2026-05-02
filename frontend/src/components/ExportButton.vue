<template>
  <el-button-group>
    <el-button type="primary" @click="handleExport('xlsx')" :loading="exporting">
      <el-icon><Download /></el-icon>
      导出 Excel
    </el-button>
    <el-dropdown @command="handleExport">
      <el-button type="primary">
        <el-icon><ArrowDown /></el-icon>
      </el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="xlsx">导出 Excel (.xlsx)</el-dropdown-item>
          <el-dropdown-item command="csv">导出 CSV (.csv)</el-dropdown-item>
          <el-dropdown-item command="json">导出 JSON (.json)</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </el-button-group>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, ArrowDown } from '@element-plus/icons-vue'

const props = defineProps({
  data: {
    type: Array,
    required: true,
  },
  columns: {
    type: Array,
    default: () => [],
  },
  filename: {
    type: String,
    default: 'export',
  },
})

const emitting = defineEmits(['export'])

const exporting = ref(false)

const handleExport = async (format) => {
  if (!props.data || props.data.length === 0) {
    ElMessage.warning('没有可导出的数据')
    return
  }

  exporting.value = true

  try {
    let content, mimeType, extension

    switch (format) {
      case 'csv':
        content = exportToCSV(props.data, props.columns)
        mimeType = 'text/csv;charset=utf-8'
        extension = 'csv'
        break
      case 'json':
        content = JSON.stringify(props.data, null, 2)
        mimeType = 'application/json;charset=utf-8'
        extension = 'json'
        break
      case 'xlsx':
      default:
        content = exportToCSV(props.data, props.columns)
        mimeType = 'text/csv;charset=utf-8'
        extension = 'csv'
        break
    }

    downloadFile(content, `${props.filename}.${extension}`, mimeType)
    ElMessage.success('导出成功')
    emitting('export', { format, count: props.data.length })
  } catch (error) {
    console.error('Export error:', error)
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

const exportToCSV = (data, columns) => {
  if (!columns || columns.length === 0) {
    columns = Object.keys(data[0] || {}).map((key) => ({
      key,
      label: key,
    }))
  }

  const headers = columns.map((col) => col.label || col.key).join(',')
  const rows = data.map((row) =>
    columns
      .map((col) => {
        const value = row[col.key]
        if (value === null || value === undefined) return ''
        const str = String(value)
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
          return `"${str.replace(/"/g, '""')}"`
        }
        return str
      })
      .join(',')
  )

  return '\ufeff' + headers + '\n' + rows.join('\n')
}

const downloadFile = (content, filename, mimeType) => {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
</script>
