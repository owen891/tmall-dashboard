<template>
  <div class="backup-management page-container">
    <div class="page-header">
      <h1>数据备份与恢复</h1>
      <el-button type="primary" @click="createBackup">
        <el-icon><Plus /></el-icon>
        创建备份
      </el-button>
    </div>

    <el-row :gutter="20">
      <el-col :span="16">
        <div class="backup-list">
          <div class="card-header">
            <h3>备份列表</h3>
            <el-button size="small" @click="loadBackups">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>

          <el-table :data="backups" style="width: 100%" v-loading="loading">
            <el-table-column prop="file_name" label="备份文件" min-width="250" />
            <el-table-column label="大小" width="120">
              <template #default="{ row }">
                {{ formatFileSize(row.file_size) }}
              </template>
            </el-table-column>
            <el-table-column label="类型" width="100">
              <template #default="{ row }">
                <el-tag :type="row.backup_type === 'auto' ? 'info' : 'primary'" size="small">
                  {{ row.backup_type === 'auto' ? '自动' : '手动' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="180">
              <template #default="{ row }">
                {{ formatTime(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="250" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="restoreBackup(row)">恢复</el-button>
                <el-button size="small" @click="downloadBackup(row)">下载</el-button>
                <el-button size="small" type="danger" @click="deleteBackup(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>

      <el-col :span="8">
        <div class="backup-info">
          <h3>备份说明</h3>
          <el-card>
            <div class="info-item">
              <el-icon><InfoFilled /></el-icon>
              <div>
                <div class="info-title">自动备份</div>
                <div class="info-desc">系统每天自动备份一次，保留最近30天的备份</div>
              </div>
            </div>
            <div class="info-item">
              <el-icon><WarningFilled /></el-icon>
              <div>
                <div class="info-title">恢复注意</div>
                <div class="info-desc">恢复备份前会自动创建当前数据库的备份</div>
              </div>
            </div>
            <div class="info-item">
              <el-icon><Download /></el-icon>
              <div>
                <div class="info-title">下载备份</div>
                <div class="info-desc">可以将备份文件下载到本地进行异地备份</div>
              </div>
            </div>
          </el-card>

          <el-card style="margin-top: 20px;">
            <h4>备份统计</h4>
            <div class="stat-item">
              <span>总备份数：</span>
              <span class="stat-value">{{ backups.length }}</span>
            </div>
            <div class="stat-item">
              <span>手动备份：</span>
              <span class="stat-value">{{ manualBackups }}</span>
            </div>
            <div class="stat-item">
              <span>自动备份：</span>
              <span class="stat-value">{{ autoBackups }}</span>
            </div>
            <div class="stat-item">
              <span>总大小：</span>
              <span class="stat-value">{{ formatFileSize(totalSize) }}</span>
            </div>
          </el-card>
        </div>
      </el-col>
    </el-row>

    <el-dialog v-model="showCreateDialog" title="创建备份" width="500px">
      <el-form :model="backupForm" label-width="80px">
        <el-form-item label="备份类型">
          <el-radio-group v-model="backupForm.backup_type">
            <el-radio label="manual">手动备份</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="backupForm.note"
            type="textarea"
            :rows="3"
            placeholder="可选：添加备份说明"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmCreateBackup" :loading="creating">
          创建备份
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showRestoreDialog" title="确认恢复" width="500px">
      <el-alert
        title="警告"
        type="warning"
        description="恢复备份将覆盖当前数据库，此操作不可逆。系统会先创建当前数据库的备份。"
        :closable="false"
        show-icon
        style="margin-bottom: 20px;"
      />
      <p>确定要恢复备份 <strong>{{ selectedBackup?.file_name }}</strong> 吗？</p>
      <template #footer>
        <el-button @click="showRestoreDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmRestoreBackup" :loading="restoring">
          确认恢复
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, InfoFilled, WarningFilled, Download } from '@element-plus/icons-vue'
import api from '@/api'

const loading = ref(false)
const creating = ref(false)
const restoring = ref(false)
const backups = ref([])
const showCreateDialog = ref(false)
const showRestoreDialog = ref(false)
const selectedBackup = ref(null)

const backupForm = ref({
  backup_type: 'manual',
  note: ''
})

const manualBackups = computed(() => 
  backups.value.filter(b => b.backup_type === 'manual').length
)

const autoBackups = computed(() => 
  backups.value.filter(b => b.backup_type === 'auto').length
)

const totalSize = computed(() => 
  backups.value.reduce((sum, b) => sum + b.file_size, 0)
)

const loadBackups = async () => {
  loading.value = true
  try {
    const result = await api.backupApi.getList()
    if (result?.code === 200) {
      backups.value = (result.data?.backups || []).map(b => ({
        id: b.id,
        file_name: b.file_name || '',
        file_size: b.file_size || 0,
        backup_type: b.backup_type || 'manual',
        created_at: b.created_at || ''
      }))
    } else {
      backups.value = []
      ElMessage.error('加载备份列表失败')
    }
  } catch (error) {
    console.error('加载备份列表失败:', error)
    ElMessage.error('加载备份列表失败')
    backups.value = []
  } finally {
    loading.value = false
  }
}

const createBackup = () => {
  backupForm.value = {
    backup_type: 'manual',
    note: ''
  }
  showCreateDialog.value = true
}

const confirmCreateBackup = async () => {
  creating.value = true
  try {
    await api.backupApi.create(backupForm.value)
    ElMessage.success('备份创建成功')
    showCreateDialog.value = false
    loadBackups()
  } catch (error) {
    console.error('备份创建失败:', error)
    ElMessage.error('备份创建失败')
  } finally {
    creating.value = false
  }
}

const restoreBackup = (backup) => {
  selectedBackup.value = backup
  showRestoreDialog.value = true
}

const confirmRestoreBackup = async () => {
  restoring.value = true
  try {
    await api.backupApi.restore(selectedBackup.value.id)
    ElMessage.success('备份恢复成功，请刷新页面')
    showRestoreDialog.value = false
    setTimeout(() => {
      window.location.reload()
    }, 1500)
  } catch (error) {
    console.error('备份恢复失败:', error)
    ElMessage.error('备份恢复失败')
  } finally {
    restoring.value = false
  }
}

const downloadBackup = async (backup) => {
  try {
    const blob = await api.backupApi.download(backup.id)
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = backup.file_name
    a.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('下载成功')
  } catch (error) {
    console.error('下载失败:', error)
    ElMessage.error('下载失败')
  }
}

const deleteBackup = async (backup) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除备份 ${backup.file_name} 吗？`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await api.backupApi.delete(backup.id)
    ElMessage.success('删除成功')
    loadBackups()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

const formatFileSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

const formatTime = (timeStr) => {
  if (!timeStr) return ''
  return timeStr
}

onMounted(() => {
  loadBackups()
})
</script>

<style scoped>
.backup-management {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 600;
  margin: 0;
}

.backup-list, .backup-info {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-header h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.backup-info h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px 0;
}

.backup-info h4 {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 12px 0;
}

.info-item {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.info-item:last-child {
  margin-bottom: 0;
}

.info-item .el-icon {
  font-size: 20px;
  color: #409EFF;
  margin-top: 2px;
}

.info-title {
  font-weight: 500;
  margin-bottom: 4px;
}

.info-desc {
  font-size: 13px;
  color: #999;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.stat-item:last-child {
  border-bottom: none;
}

.stat-value {
  font-weight: 600;
  color: #409EFF;
}
</style>
