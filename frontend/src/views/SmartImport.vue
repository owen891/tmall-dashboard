<template>
  <div class="smart-import-page page-container">
    <el-card class="config-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-icon><MagicStick /></el-icon>
            <span>AI智能导入</span>
          </div>
          <el-tag type="success" v-if="scannerRunning">扫描服务运行中</el-tag>
          <el-tag type="info" v-else>扫描服务未启动</el-tag>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="手动扫描" name="manual">
          <el-form :model="scanForm" label-width="140px">
            <el-form-item label="扫描文件夹">
              <el-input v-model="scanForm.folder_path" placeholder="输入要扫描的文件夹路径">
                <template #append>
                  <el-button @click="selectFolder">选择</el-button>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item label="文件类型筛选">
              <el-select v-model="scanForm.file_types" multiple placeholder="不筛选则扫描所有类型" style="width: 100%">
                <el-option label="周度数据" value="weekly_data" />
                <el-option label="市场分析" value="market_analysis" />
                <el-option label="评价数据" value="reviews" />
                <el-option label="订单数据" value="orders" />
                <el-option label="商品数据" value="products" />
              </el-select>
            </el-form-item>
            <el-form-item label="自动导入">
              <el-switch v-model="scanForm.auto_import" />
              <span class="form-tip">开启后，识别置信度高的文件将自动导入</span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleScan" :loading="scanning">
                <el-icon><Search /></el-icon>
                {{ scanning ? '扫描中...' : '开始扫描' }}
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="定时任务" name="scheduled">
          <el-form :model="scheduleForm" label-width="140px">
            <el-form-item label="任务名称">
              <el-input v-model="scheduleForm.job_name" placeholder="输入任务名称" />
            </el-form-item>
            <el-form-item label="扫描文件夹">
              <el-input v-model="scheduleForm.folder_path" placeholder="输入要扫描的文件夹路径" />
            </el-form-item>
            <el-form-item label="Cron表达式">
              <el-input v-model="scheduleForm.cron_expression" placeholder="例如: 0 9 * * 1 (每周一早上9点)">
                <template #append>
                  <el-button @click="showCronHelper = true">帮助</el-button>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item label="文件类型筛选">
              <el-select v-model="scheduleForm.file_types" multiple placeholder="不筛选则扫描所有类型" style="width: 100%">
                <el-option label="周度数据" value="weekly_data" />
                <el-option label="市场分析" value="market_analysis" />
                <el-option label="评价数据" value="reviews" />
                <el-option label="订单数据" value="orders" />
                <el-option label="商品数据" value="products" />
              </el-select>
            </el-form-item>
            <el-form-item label="自动导入">
              <el-switch v-model="scheduleForm.auto_import" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleCreateJob">创建任务</el-button>
            </el-form-item>
          </el-form>

          <el-divider />

          <h4>已创建的任务</h4>
          <el-table :data="scheduledJobs" stripe v-if="scheduledJobs.length > 0">
            <el-table-column prop="job_id" label="任务ID" />
            <el-table-column prop="folder_path" label="文件夹" show-overflow-tooltip />
            <el-table-column prop="cron_expression" label="Cron表达式" width="120" />
            <el-table-column prop="next_run" label="下次执行" width="180" />
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button link type="danger" @click="handleRemoveJob(row.job_id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无定时任务" />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-card class="results-card" v-if="scanResults">
      <template #header>
        <div class="card-header">
          <span>扫描结果</span>
          <el-button type="primary" size="small" @click="handleImportAll" 
                     :disabled="!importableFiles.length" :loading="importing">
            批量导入 ({{ importableFiles.length }}个文件)
          </el-button>
        </div>
      </template>

      <el-table :data="scanResults.files" stripe>
        <el-table-column prop="filename" label="文件名" show-overflow-tooltip />
        <el-table-column prop="file_type" label="识别类型" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ getFileTypeName(row.file_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="confidence" label="置信度" width="100" align="center">
          <template #default="{ row }">
            <el-progress :percentage="Math.round(row.confidence * 100)" :stroke-width="6" />
          </template>
        </el-table-column>
        <el-table-column prop="sheets" label="Sheet数" width="80" align="center">
          <template #default="{ row }">
            {{ row.sheets?.length || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="数据预览" width="100">
          <template #default="{ row }">
            <el-button link size="small" @click="showPreview(row)" v-if="row.preview">
              查看
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="AI分析" width="100">
          <template #default="{ row }">
            <el-button link size="small" @click="handleAIAnalyze(row)">
              分析
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button 
              link 
              type="primary" 
              @click="handleImportFile(row)" 
              :disabled="!row.can_import"
              :loading="row.importing"
            >
              导入
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="history-card">
      <template #header>
        <div class="card-header">
          <span>执行历史</span>
          <el-button size="small" @click="loadHistory">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>
      <el-table :data="jobHistory" stripe>
        <el-table-column prop="started_at" label="执行时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.started_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="folder_path" label="文件夹" show-overflow-tooltip />
        <el-table-column prop="files_found" label="发现文件" width="100" align="center" />
        <el-table-column prop="files_imported" label="已导入" width="100" align="center" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : 'danger'" size="small">
              {{ row.status === 'completed' ? '完成' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="errors" label="错误信息" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.errors?.join('; ') }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="previewVisible" title="数据预览" width="80%">
      <el-table :data="previewData" border stripe max-height="400" v-if="previewData">
        <el-table-column
          v-for="col in previewColumns"
          :key="col"
          :prop="col"
          :label="col"
          :min-width="120"
          show-overflow-tooltip
        />
      </el-table>
    </el-dialog>

    <el-dialog v-model="showCronHelper" title="Cron表达式帮助" width="600px">
      <div class="cron-help">
        <p>Cron表达式格式：分 时 日 月 周</p>
        <el-table :data="cronExamples" stripe>
          <el-table-column prop="expression" label="表达式" width="150" />
          <el-table-column prop="description" label="说明" />
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

const activeTab = ref('manual')
const scanning = ref(false)
const importing = ref(false)
const scannerRunning = ref(false)
const previewVisible = ref(false)
const showCronHelper = ref(false)
const previewData = ref([])
const previewColumns = ref([])
const scanResults = ref(null)
const scheduledJobs = ref([])
const jobHistory = ref([])

const scanForm = ref({
  folder_path: '',
  file_types: [],
  auto_import: false
})

const scheduleForm = ref({
  job_name: '',
  folder_path: '',
  cron_expression: '',
  file_types: [],
  auto_import: false
})

const cronExamples = [
  { expression: '0 9 * * *', description: '每天早上9点' },
  { expression: '0 9 * * 1', description: '每周一早上9点' },
  { expression: '0 9 * * 1-5', description: '周一到周五早上9点' },
  { expression: '0 */2 * * *', description: '每2小时' },
  { expression: '0 0 * * 0', description: '每周日凌晨' }
]

const importableFiles = computed(() => {
  if (!scanResults.value?.files) return []
  return scanResults.value.files.filter(f => f.can_import)
})

const getFileTypeName = (type) => {
  const names = {
    weekly_data: '周度数据',
    market_analysis: '市场分析',
    reviews: '评价数据',
    orders: '订单数据',
    products: '商品数据',
    unknown: '未知'
  }
  return names[type] || type
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const selectFolder = () => {
  ElMessage.info('请直接输入文件夹路径')
}

const handleScan = async () => {
  if (!scanForm.value.folder_path) {
    ElMessage.warning('请输入文件夹路径')
    return
  }

  scanning.value = true
  try {
    const response = await api.post('/smart-import/scan', null, {
      params: { folder_path: scanForm.value.folder_path }
    })
    scanResults.value = response.data
    ElMessage.success(`扫描完成，发现 ${response.data.total} 个文件`)
  } catch (error) {
    ElMessage.error('扫描失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    scanning.value = false
  }
}

const showPreview = (file) => {
  if (file.preview) {
    previewColumns.value = file.preview.columns || []
    previewData.value = file.preview.sample_data || []
    previewVisible.value = true
  }
}

const handleAIAnalyze = async (file) => {
  try {
    ElMessage.info('AI分析中...')
    const response = await api.post(`/smart-import/analyze/${encodeURIComponent(file.filepath)}`, null, {
      params: { use_ai: true }
    })
    
    if (response.data.ai_analysis) {
      const analysis = response.data.ai_analysis
      ElMessage.success(`AI识别: ${analysis.file_type} (置信度: ${Math.round((analysis.confidence || 0) * 100)}%)`)
    }
  } catch (error) {
    ElMessage.error('AI分析失败: ' + (error.message || '未知错误'))
  }
}

const handleImportFile = async (file) => {
  file.importing = true
  try {
    const response = await api.post('/smart-import/import', null, {
      params: {
        filepath: file.filepath,
        file_type: file.file_type
      }
    })
    
    if (response.data.success) {
      ElMessage.success(response.data.message)
      await loadHistory()
    } else {
      ElMessage.error(response.data.message)
    }
  } catch (error) {
    ElMessage.error('导入失败: ' + (error.response?.data?.message || error.message))
  } finally {
    file.importing = false
  }
}

const handleImportAll = async () => {
  importing.value = true
  try {
    const response = await api.post('/smart-import/batch-import', null, {
      params: {
        folder_path: scanForm.value.folder_path,
        auto_confirm: scanForm.value.auto_import
      }
    })
    
    ElMessage.success(`批量导入完成: 成功 ${response.data.success_count} 个，失败 ${response.data.failed_count} 个`)
    await loadHistory()
  } catch (error) {
    ElMessage.error('批量导入失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    importing.value = false
  }
}

const handleCreateJob = async () => {
  if (!scheduleForm.value.job_name || !scheduleForm.value.folder_path || !scheduleForm.value.cron_expression) {
    ElMessage.warning('请填写完整的任务信息')
    return
  }

  try {
    await api.post('/smart-import/jobs', scheduleForm.value)
    ElMessage.success('定时任务创建成功')
    await loadJobs()
  } catch (error) {
    ElMessage.error('创建失败: ' + (error.response?.data?.detail || error.message))
  }
}

const handleRemoveJob = async (jobId) => {
  try {
    await api.delete(`/smart-import/jobs/${jobId}`)
    ElMessage.success('任务已删除')
    await loadJobs()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

const loadJobs = async () => {
  try {
    const response = await api.get('/smart-import/jobs')
    scheduledJobs.value = response.data || []
  } catch (error) {
    console.error('加载任务失败', error)
  }
}

const loadHistory = async () => {
  try {
    const response = await api.get('/smart-import/history')
    jobHistory.value = response.data || []
  } catch (error) {
    console.error('加载历史失败', error)
  }
}

onMounted(() => {
  loadJobs()
  loadHistory()
})
</script>

<style scoped>
.smart-import-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
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

.form-tip {
  margin-left: 12px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.cron-help {
  padding: 20px;
}

.cron-help p {
  margin-bottom: 16px;
  font-weight: 500;
}
</style>
