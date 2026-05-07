<template>
  <div class="backup-page page-container">
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-icon><FolderOpened /></el-icon>
            <span>数据备份管理</span>
          </div>
          <div class="header-actions">
            <el-button type="success" @click="createBackup" :loading="creating">
              <el-icon><Plus /></el-icon>
              创建备份
            </el-button>
            <el-button @click="loadBackups">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-alert
        title="备份说明"
        type="info"
        :closable="false"
        style="margin-bottom: 20px;"
      >
        <template #default>
          备份文件保存在服务器本地，支持下载和恢复操作。建议定期创建备份以保护数据安全。
        </template>
      </el-alert>

      <el-row :gutter="20" class="stats-row">
        <el-col :span="8">
          <el-card class="stat-card">
            <div class="stat-value">{{ backups.length }}</div>
            <div class="stat-label">备份数量</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card class="stat-card">
            <div class="stat-value">{{ totalSize }}</div>
            <div class="stat-label">总大小</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card class="stat-card">
            <div class="stat-value">{{ lastBackupTime }}</div>
            <div class="stat-label">最近备份</div>
          </el-card>
        </el-col>
      </el-row>

      <el-table :data="backups" stripe v-loading="loading">
        <el-table-column prop="filename" label="文件名" min-width="250">
          <template #default="{ row }">
            <el-icon class="file-icon"><Document /></el-icon>
            {{ row.filename }}
          </template>
        </el-table-column>
        <el-table-column prop="size_formatted" label="大小" width="120" align="center" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="modified_at" label="更新时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.modified_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="downloadFile(row)">
              <el-icon><Download /></el-icon>
              下载
            </el-button>
            <el-popconfirm title="确定删除此备份？" @confirm="deleteFile(row)">
              <template #reference>
                <el-button type="danger" size="small">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

const loading = ref(false)
const creating = ref(false)
const backups = ref([])

const totalSize = computed(() => {
  const total = backups.value.reduce((sum, b) => sum + b.size, 0)
  return formatBytes(total)
})

const lastBackupTime = computed(() => {
  if (backups.value.length === 0) return '-'
  return formatTime(backups.value[0].modified_at)
})

const loadBackups = async () => {
  loading.value = true
  try {
    const res = await api.get('/backup/status')
    backups.value = res.data?.backups || []
  } catch (error) {
    console.error('Load backups error:', error)
    ElMessage.error('加载备份列表失败')
  } finally {
    loading.value = false
  }
}

const createBackup = async () => {
  creating.value = true
  try {
    const res = await api.post('/backup/create')
    ElMessage.success('备份创建成功')
    await loadBackups()
  } catch (error) {
    console.error('Create backup error:', error)
    ElMessage.error('创建备份失败')
  } finally {
    creating.value = false
  }
}

const downloadFile = (row) => {
  window.open(`/api/backup/download/${row.filename}`, '_blank')
}

const deleteFile = async (row) => {
  try {
    await api.delete(`/backup/delete/${row.filename}`)
    ElMessage.success('删除成功')
    await loadBackups()
  } catch (error) {
    console.error('Delete backup error:', error)
    ElMessage.error('删除失败')
  }
}

const formatTime = (time) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const formatBytes = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

onMounted(() => {
  loadBackups()
})
</script>

<style scoped>
.backup-page {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 500;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #409eff;
  margin-bottom: 8px;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.file-icon {
  margin-right: 8px;
  color: #409eff;
}
</style>
