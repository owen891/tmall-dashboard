<template>
  <div class="import-center">
    <div class="page-header">
      <h1>数据导入中心</h1>
      <div class="header-actions">
        <el-button @click="showTemplates = true">
          <el-icon><Download /></el-icon> 下载模板
        </el-button>
      </div>
    </div>

    <el-row :gutter="20">
      <el-col :span="16">
        <div class="upload-section">
          <el-upload
            ref="uploadRef"
            drag
            multiple
            :auto-upload="false"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            :file-list="fileList"
            accept=".xlsx,.xls,.csv,.zip"
            :limit="10"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">
              拖拽文件到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持 Excel (.xlsx, .xls)、CSV、ZIP 格式，单个文件不超过50MB，最多上传10个文件
              </div>
            </template>
          </el-upload>

          <div v-if="fileList.length > 0" class="file-actions">
            <el-button type="primary" @click="uploadFiles" :loading="uploading">
              <el-icon><Upload /></el-icon> 开始导入
            </el-button>
            <el-button @click="clearFiles">清空文件</el-button>
          </div>
        </div>

        <div v-if="importResults.length > 0" class="import-results">
          <h3>导入结果</h3>
          <div v-for="(result, index) in importResults" :key="index" class="result-item">
            <div class="result-header">
              <el-icon :class="result.success ? 'success' : 'error'">
                <component :is="result.success ? 'CircleCheck' : 'CircleClose'" />
              </el-icon>
              <span class="file-name">{{ result.fileName }}</span>
              <el-tag :type="result.success ? 'success' : 'danger'" size="small">
                {{ result.success ? '成功' : '失败' }}
              </el-tag>
            </div>
            <div class="result-detail">
              <p v-if="result.success">
                成功导入 {{ result.recordCount }} 条数据
              </p>
              <p v-else class="error-message">
                {{ result.error }}
              </p>
            </div>
          </div>
        </div>
      </el-col>

      <el-col :span="8">
        <div class="import-history">
          <h3>导入历史</h3>
          <el-table :data="importHistory" style="width: 100%" max-height="600">
            <el-table-column prop="import_time" label="时间" width="150">
              <template #default="{ row }">
                {{ formatTime(row.import_time) }}
              </template>
            </el-table-column>
            <el-table-column prop="file_name" label="文件" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">
                  {{ getStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="viewDetail(row)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
    </el-row>

    <el-dialog v-model="showTemplates" title="下载导入模板" width="600px">
      <div class="template-list">
        <div v-for="template in templates" :key="template.id" class="template-item">
          <div class="template-info">
            <el-icon><Document /></el-icon>
            <div>
              <div class="template-name">{{ template.name }}</div>
              <div class="template-desc">{{ template.description }}</div>
            </div>
          </div>
          <el-button size="small" @click="downloadTemplate(template)">
            <el-icon><Download /></el-icon> 下载
          </el-button>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="showDetail" title="导入详情" width="700px">
      <div v-if="currentDetail" class="import-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="文件名">{{ currentDetail.file_name }}</el-descriptions-item>
          <el-descriptions-item label="数据类型">{{ currentDetail.data_type }}</el-descriptions-item>
          <el-descriptions-item label="导入时间">{{ formatTime(currentDetail.import_time) }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentDetail.status)">
              {{ getStatusLabel(currentDetail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="记录数">{{ currentDetail.record_count }}</el-descriptions-item>
          <el-descriptions-item label="成功数">{{ currentDetail.success_count }}</el-descriptions-item>
          <el-descriptions-item label="失败数">{{ currentDetail.error_count }}</el-descriptions-item>
        </el-descriptions>
        
        <div v-if="currentDetail.error_details" class="error-details">
          <h4>错误详情</h4>
          <pre>{{ currentDetail.error_details }}</pre>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { 
  UploadFilled, 
  Upload, 
  Download, 
  Document,
  CircleCheck,
  CircleClose
} from '@element-plus/icons-vue'

const uploadRef = ref()
const fileList = ref([])
const uploading = ref(false)
const importResults = ref([])
const importHistory = ref([])
const showTemplates = ref(false)
const showDetail = ref(false)
const currentDetail = ref(null)

const templates = ref([
  { id: 1, name: '生意参谋-交易报表', description: '包含订单、销售额、退款等交易数据', type: 'trade' },
  { id: 2, name: '生意参谋-商品报表', description: '包含商品销售、流量、转化数据', type: 'product' },
  { id: 3, name: '生意参谋-流量报表', description: '包含访客、浏览量、来源渠道数据', type: 'traffic' },
  { id: 4, name: '万相台-投放报表', description: '包含广告投放、消耗、转化数据', type: 'wxt' },
  { id: 5, name: '达摩盘-人群报表', description: '包含人群包、人群规模数据', type: 'dmp' }
])

const handleFileChange = (file, files) => {
  fileList.value = files
}

const handleFileRemove = (file, files) => {
  fileList.value = files
}

const uploadFiles = async () => {
  if (fileList.value.length === 0) {
    ElMessage.warning('请先选择要导入的文件')
    return
  }

  uploading.value = true
  importResults.value = []

  try {
    for (const file of fileList.value) {
      const formData = new FormData()
      formData.append('file', file.raw)

      const response = await fetch('/api/imports/upload', {
        method: 'POST',
        body: formData
      })

      if (response.ok) {
        const result = await response.json()
        importResults.value.push({
          fileName: file.name,
          success: true,
          recordCount: result.record_count || 0
        })
      } else {
        const error = await response.json()
        importResults.value.push({
          fileName: file.name,
          success: false,
          error: error.detail || '导入失败'
        })
      }
    }

    ElMessage.success('文件导入完成')
    loadImportHistory()
    fileList.value = []
  } catch (error) {
    ElMessage.error('导入失败：' + error.message)
  } finally {
    uploading.value = false
  }
}

const clearFiles = () => {
  fileList.value = []
  importResults.value = []
}

const loadImportHistory = async () => {
  try {
    const response = await fetch('/api/imports/history')
    if (response.ok) {
      const data = await response.json()
      importHistory.value = data.history || []
    } else {
      // 使用模拟数据
      importHistory.value = [
        {
          id: 1,
          file_name: '生意参谋-交易报表-2026-05-01.xlsx',
          data_type: '交易数据',
          import_time: '2026-05-01 14:30:00',
          record_count: 1250,
          success_count: 1248,
          error_count: 2,
          status: 'success'
        },
        {
          id: 2,
          file_name: '万相台-投放报表-2026-05-01.xlsx',
          data_type: '推广数据',
          import_time: '2026-05-01 15:20:00',
          record_count: 85,
          success_count: 85,
          error_count: 0,
          status: 'success'
        },
        {
          id: 3,
          file_name: '商品数据-错误.xlsx',
          data_type: '商品数据',
          import_time: '2026-05-02 09:15:00',
          record_count: 0,
          success_count: 0,
          error_count: 1,
          status: 'failed',
          error_details: '第3行：缺少必填字段"商品ID"'
        }
      ]
    }
  } catch (error) {
    // 使用模拟数据
    importHistory.value = [
      {
        id: 1,
        file_name: '生意参谋-交易报表-2026-05-01.xlsx',
        data_type: '交易数据',
        import_time: '2026-05-01 14:30:00',
        record_count: 1250,
        success_count: 1248,
        error_count: 2,
        status: 'success'
      }
    ]
  }
}

const viewDetail = (row) => {
  currentDetail.value = row
  showDetail.value = true
}

const downloadTemplate = (template) => {
  ElMessage.success(`开始下载：${template.name}`)
  // 实际项目中这里会调用后端API下载模板文件
}

const formatTime = (timeStr) => {
  if (!timeStr) return ''
  return timeStr
}

const getStatusType = (status) => {
  const types = {
    'success': 'success',
    'failed': 'danger',
    'partial': 'warning',
    'pending': 'info'
  }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const labels = {
    'success': '成功',
    'failed': '失败',
    'partial': '部分成功',
    'pending': '处理中'
  }
  return labels[status] || status
}

onMounted(() => {
  loadImportHistory()
})
</script>

<style scoped>
.import-center {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.upload-section {
  background: white;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-bottom: 20px;
}

.file-actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
}

.import-results {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.import-results h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px 0;
}

.result-item {
  padding: 16px;
  border-bottom: 1px solid #eee;
}

.result-item:last-child {
  border-bottom: none;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.result-header .success {
  color: #67C23A;
  font-size: 20px;
}

.result-header .error {
  color: #F56C6C;
  font-size: 20px;
}

.file-name {
  flex: 1;
  font-weight: 500;
}

.result-detail {
  margin-left: 32px;
  color: #666;
  font-size: 14px;
}

.error-message {
  color: #F56C6C;
}

.import-history {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.import-history h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px 0;
}

.template-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.template-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border: 1px solid #eee;
  border-radius: 8px;
}

.template-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.template-info .el-icon {
  font-size: 32px;
  color: #409EFF;
}

.template-name {
  font-weight: 500;
  margin-bottom: 4px;
}

.template-desc {
  font-size: 13px;
  color: #999;
}

.import-detail {
  padding: 20px 0;
}

.error-details {
  margin-top: 20px;
  padding: 16px;
  background: #fef0f0;
  border-radius: 8px;
}

.error-details h4 {
  margin: 0 0 12px 0;
  color: #F56C6C;
}

.error-details pre {
  margin: 0;
  white-space: pre-wrap;
  font-size: 13px;
  color: #666;
}
</style>
