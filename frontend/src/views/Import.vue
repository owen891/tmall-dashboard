<template>
  <div class="import-page">
    <el-card class="import-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-icon><Upload /></el-icon>
            <span>数据导入</span>
          </div>
        </div>
      </template>

      <div class="import-content">
        <el-steps :active="currentStep" finish-status="success" align-center>
          <el-step title="上传文件" />
          <el-step title="数据预览" />
          <el-step title="导入完成" />
        </el-steps>

        <div class="step-content">
          <div v-if="currentStep === 0" class="upload-step">
            <el-alert
              type="info"
              :closable="false"
              show-icon
              style="margin-bottom: 20px"
            >
              <template #title>
                <span>支持格式：.xlsx, .xls</span>
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
                  accept=".xlsx,.xls"
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
                  @click="handleImport" 
                  :disabled="!file"
                  size="large"
                >
                  <el-icon v-if="!loading"><Upload /></el-icon>
                  {{ loading ? '导入中...' : '开始导入' }}
                </el-button>
                <el-button @click="handleReset" :disabled="loading">
                  重置
                </el-button>
              </el-form-item>
            </el-form>
          </div>

          <div v-if="currentStep === 1" class="preview-step">
            <el-icon class="preview-icon"><Loading /></el-icon>
            <p>正在解析数据，请稍候...</p>
          </div>

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

    <el-card class="history-card" v-if="recentImports.length > 0">
      <template #header>
        <div class="card-header">
          <span>最近导入记录</span>
        </div>
      </template>
      <el-table :data="recentImports" stripe>
        <el-table-column prop="date" label="导入时间" />
        <el-table-column prop="fileName" label="文件名" show-overflow-tooltip />
        <el-table-column prop="products" label="商品数" align="center" />
        <el-table-column prop="status" label="状态" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === '成功' ? 'success' : 'danger'">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'

const router = useRouter()
const uploadRef = ref(null)
const file = ref(null)
const loading = ref(false)
const result = ref(null)
const errorMessage = ref('')
const currentStep = ref(0)
const recentImports = ref([])

const form = ref({
  week_start: ''
})

const disabledFutureDate = (date) => {
  return date.getTime() > Date.now()
}

const handleChange = (fileObj) => {
  file.value = fileObj.raw
}

const handleImport = async () => {
  if (!file.value) {
    ElMessage.warning('请选择文件')
    return
  }

  loading.value = true
  currentStep.value = 1
  
  try {
    const res = await api.importExcel(file.value, form.value.week_start)
    result.value = {
      saved: true,
      ...res.data
    }
    recentImports.value.unshift({
      date: new Date().toLocaleString('zh-CN'),
      fileName: file.value.name,
      products: res.data?.parsed?.products || 0,
      status: '成功'
    })
    currentStep.value = 2
  } catch (error) {
    result.value = { saved: false }
    errorMessage.value = error.response?.data?.detail || error.message || '导入失败'
    currentStep.value = 2
  } finally {
    loading.value = false
  }
}

const handleReset = () => {
  file.value = null
  result.value = null
  errorMessage.value = ''
  currentStep.value = 0
  form.value.week_start = ''
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
}

const goToProducts = () => {
  router.push('/products')
}
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
  text-align: center;
  padding: 60px 0;
}

.preview-icon {
  font-size: 48px;
  color: var(--el-color-primary);
  animation: rotate 1s linear infinite;
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

.result {
  margin-top: 20px;
}

.stats {
  display: flex;
  justify-content: center;
  gap: 40px;
  margin-top: 20px;
}
</style>
