<template>
  <div class="import-page page-container">
    <el-card class="import-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-icon><Upload /></el-icon>
            <span>数据导入</span>
          </div>
          <el-button type="primary" @click="downloadTemplate">
            <el-icon><Download /></el-icon>
            下载模板
          </el-button>
        </div>
      </template>

      <div class="import-content">
        <el-steps :active="currentStep" finish-status="success" :align-center="true">
          <el-step title="上传文件" />
          <el-step title="数据预览" />
          <el-step title="导入完成" />
        </el-steps>

        <div class="step-content">
          <!-- 上传文件 -->
          <div v-if="currentStep === 0" class="upload-step">
            <el-alert
              type="info"
              :closable="false"
              show-icon
              style="margin-bottom: 20px"
            >
              <template #title>
                <span>支持格式: .xlsx, .xls, .csv</span>
              </template>
            </el-alert>

            <el-form :model="form" label-width="120px" style="max-width: 600px">
              <el-form-item label="选择文件">
                <el-upload
                  ref="uploadRef"
                  drag
                  :auto-upload="false"
                  :show-file-list="true"
                  :on-change="handleChange"
                  :limit="1"
                  accept=".xlsx,.xls,.csv"
                  class="upload-area"
                >
                  <el-icon class="upload-icon"><UploadFilled /></el-icon>
                  <div class="upload-text">
                    拖拽文件到此处，或<span class="link">点击上传</span>
                  </div>
                  <template #tip>
                    <div class="el-upload__tip">
                      单个文件不超过 50MB
                    </div>
                  </template>
                </el-upload>
              </el-form-item>
              <el-form-item label="周开始日期">
                <el-date-picker
                  v-model="form.week_start"
                  type="date"
                  placeholder="选择周开始日期"
                  format="YYYY-MM-DD"
                  value-format="YYYY-MM-DD"
                  style="width: 100%"
                  :disabled-date="disabledFutureDate"
                />
              </el-form-item>
              <el-form-item>
                <el-button 
                  type="primary" 
                  :loading="loading" 
                  @click="handlePreview" 
                  :disabled="!file"
                  size="large"
                >
                  <el-icon v-if="!loading"><View /></el-icon>
                  {{ loading ? '预览中...' : '预览数据' }}
                </el-button>
                <el-button @click="handleReset" :disabled="loading">
                  重置
                </el-button>
              </el-form-item>
            </el-form>
          </div>

          <!-- 数据预览 -->
          <div v-if="currentStep === 1" class="preview-step">
            <div v-if="previewData" class="preview-content">
              <el-alert
                type="success"
                :closable="false"
                show-icon
                style="margin-bottom: 20px"
              >
                <template #title>
                  <span>文件解析成功，共 {{ previewData.totalRows }} 条数据</span>
                </template>
              </el-alert>

              <el-tabs v-model="activeSheet" type="border-card">
                <el-tab-pane
                  v-for="(sheet, sheetName) in previewData.data"
                  :key="sheetName"
                  :label="`${sheetName} (${sheet.totalRows}条)`"
                  :name="sheetName"
                >
                  <div class="table-wrapper">
                    <el-table :data="sheet.sampleData" border stripe size="small" max-height="400">
                      <el-table-column
                        v-for="col in sheet.columns"
                        :key="col"
                        :prop="col"
                        :label="col"
                        :min-width="120"
                        show-overflow-tooltip
                      />
                    </el-table>
                  </div>
                </el-tab-pane>
              </el-tabs>

              <div class="preview-actions">
                <el-button type="primary" :loading="importLoading" @click="handleImport" size="large">
                  <el-icon v-if="!importLoading"><Upload /></el-icon>
                  {{ importLoading ? '导入中...' : '确认导入' }}
                </el-button>
                <el-button @click="currentStep = 0" :disabled="importLoading">
                  返回修改
                </el-button>
              </div>
            </div>
            <div v-else class="loading-preview">
              <el-icon class="preview-icon" :size="48"><Loading /></el-icon>
              <p>正在解析数据，请稍候...</p>
            </div>
          </div>

          <!-- 导入结果 -->
          <div v-if="currentStep === 2" class="result-step">
            <div v-if="result?.saved" class="success-result">
              <el-result
                icon="success"
                title="导入成功"
                :sub-title="`成功导入 ${result.parsed?.products || 0} 个商品`"
              >
                <template #extra>
                  <el-button type="primary" @click="goToProducts">
                    查看商品列表
                  </el-button>
                  <el-button @click="handleReset">继续导入</el-button>
                </template>
              </el-result>
              <div class="import-stats">
                <el-row :gutter="20">
                  <el-col :span="8">
                    <el-statistic title="商品数" :value="result.parsed?.products || 0">
                      <template #prefix><el-icon><Goods /></el-icon></template>
                    </el-statistic>
                  </el-col>
                  <el-col :span="8">
                    <el-statistic title="周度数据" :value="result.parsed?.weekly_data || 0">
                      <template #prefix><el-icon><Calendar /></el-icon></template>
                    </el-statistic>
                  </el-col>
                  <el-col :span="8">
                    <el-statistic title="操作记录" :value="result.parsed?.actions || 0">
                      <template #prefix><el-icon><Operation /></el-icon></template>
                    </el-statistic>
                  </el-col>
                </el-row>
              </div>
            </div>
            <div v-else class="error-result">
              <el-result
                icon="error"
                title="导入失败"
                :sub-title="errorMessage"
              >
                <template #extra>
                  <el-button type="primary" @click="currentStep = 0">
                    重新导入
                  </el-button>
                </template>
              </el-result>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 导入历史 -->
    <el-card class="history-card">
      <template #header>
        <div class="card-header">
          <span>导入历史</span>
          <el-button size="small" @click="loadHistory">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>
      <el-table :data="historyList" stripe v-loading="historyLoading">
        <el-table-column prop="created_at" label="导入时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="file_name" label="文件名" show-overflow-tooltip />
        <el-table-column prop="import_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.import_type === 'weekly' ? '周度数据' : row.import_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="product_count" label="商品数" width="100" align="center" />
        <el-table-column prop="data_count" label="数据条数" width="100" align="center" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
              {{ row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="error_message" label="错误信息" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'

const router = useRouter()
const uploadRef = ref(null)
const file = ref(null)
const loading = ref(false)
const importLoading = ref(false)
const historyLoading = ref(false)
const result = ref(null)
const errorMessage = ref('')
const currentStep = ref(0)
const previewData = ref(null)
const activeSheet = ref('')
const historyList = ref([])

const form = ref({
  week_start: ''
})

const disabledFutureDate = (date) => {
  return date.getTime() > Date.now()
}

const handleChange = (fileObj) => {
  file.value = fileObj.raw
}

const downloadTemplate = async () => {
  try {
    const link = document.createElement('a')
    link.href = '/api/import/template/weekly'
    link.download = '周度数据导入模板.xlsx'
    link.click()
    ElMessage.success('模板下载开始')
  } catch (error) {
    ElMessage.error('下载模板失败: ' + (error.message || '未知错误'))
  }
}

const handlePreview = async () => {
  if (!file.value) {
    ElMessage.warning('请选择文件')
    return
  }

  loading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file.value)
    
    const response = await api.previewImport(formData)
    previewData.value = response.data
    if (previewData.value.sheets && previewData.value.sheets.length > 0) {
      activeSheet.value = previewData.value.sheets[0]
    }
    currentStep.value = 1
  } catch (error) {
    ElMessage.error('预览失败: ' + (error.response?.data?.detail || error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

const handleImport = async () => {
  importLoading.value = true
  try {
    const response = await api.importExcel(file.value, form.value.week_start)
    result.value = {
      saved: true,
      ...response.data
    }
    currentStep.value = 2
    await loadHistory()
  } catch (error) {
    result.value = { saved: false }
    errorMessage.value = error.response?.data?.detail || error.message || '导入失败'
    currentStep.value = 2
    await loadHistory()
  } finally {
    importLoading.value = false
  }
}

const handleReset = () => {
  file.value = null
  result.value = null
  errorMessage.value = ''
  currentStep.value = 0
  previewData.value = null
  form.value.week_start = ''
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
}

const goToProducts = () => {
  router.push('/products')
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

const loadHistory = async () => {
  historyLoading.value = true
  try {
    const response = await api.getImportHistory()
    historyList.value = response.data?.items || []
  } catch (error) {
    ElMessage.error('加载历史失败: ' + (error.message || '未知错误'))
  } finally {
    historyLoading.value = false
  }
}

onMounted(() => {
  loadHistory()
})
</script>

<style scoped>
.import-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.import-card {
  flex-shrink: 0;
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

.import-content {
  padding: 20px 0;
}

.step-content {
  margin-top: 30px;
}

.upload-step {
  max-width: 600px;
  margin: 0 auto;
}

.upload-area {
  width: 100%;
}

.upload-icon {
  font-size: 48px;
  color: var(--el-text-color-secondary);
  margin-bottom: 10px;
}

.upload-text {
  color: var(--el-text-color-regular);
}

.upload-text .link {
  color: var(--el-color-primary);
  cursor: pointer;
}

.preview-step {
  padding: 20px 0;
}

.loading-preview {
  text-align: center;
  padding: 60px 0;
}

.preview-icon {
  color: var(--el-color-primary);
  animation: rotate 1s linear infinite;
}

.preview-content {
  max-width: 100%;
}

.table-wrapper {
  overflow-x: auto;
}

.preview-actions {
  margin-top: 20px;
  display: flex;
  justify-content: center;
  gap: 12px;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.result-step {
  max-width: 800px;
  margin: 0 auto;
}

.import-stats {
  margin-top: 30px;
  padding: 20px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.history-card {
  margin-top: 0;
}
</style>
