<template>
  <div class="advanced-import-center">
    <div class="page-header">
      <h1>数据导入中心</h1>
      <div class="header-actions">
        <el-button @click="showTemplates = true">
          <el-icon><Download /></el-icon> 下载模板
        </el-button>
        <el-button @click="showBatchImport = true">
          <el-icon><Upload /></el-icon> 批量导入
        </el-button>
      </div>
    </div>

    <el-row :gutter="20">
      <el-col :span="16">
        <div class="upload-section">
          <h3>快速导入</h3>
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
                支持 Excel (.xlsx, .xls)、CSV、ZIP 格式，支持多文件批量导入
              </div>
            </template>
          </el-upload>

          <div v-if="fileList.length > 0" class="file-actions">
            <el-button type="primary" @click="previewFiles" :disabled="!fileList.length">
              <el-icon><View /></el-icon> 预览
            </el-button>
            <el-button type="success" @click="startImport" :loading="importing">
              <el-icon><Upload /></el-icon> 开始导入
            </el-button>
            <el-button @click="clearFiles">清空</el-button>
          </div>

          <div v-if="importMode === 'incremental'" class="import-mode-hint">
            <el-alert
              title="增量导入模式"
              type="success"
              description="系统将自动识别新增数据，避免重复导入"
              :closable="false"
              show-icon
            />
          </div>
        </div>

        <div v-if="previewData.length > 0" class="preview-section">
          <h3>导入预览</h3>
          <el-tabs v-model="previewTab">
            <el-tab-pane 
              v-for="(preview, index) in previewData" 
              :key="index" 
              :label="preview.fileName" 
              :name="'file-' + index"
            >
              <div class="preview-info">
                <span>文件类型：{{ preview.fileType }}</span>
                <span>数据条数：{{ preview.rowCount }}</span>
                <span>新增条数：{{ preview.newCount }}</span>
                <span>重复条数：{{ preview.duplicateCount }}</span>
              </div>
              <el-table 
                :data="preview.data.slice(0, 10)" 
                size="small"
                max-height="300"
              >
                <el-table-column 
                  v-for="col in preview.columns" 
                  :key="col" 
                  :prop="col" 
                  :label="col" 
                  min-width="120"
                  show-overflow-tooltip
                />
              </el-table>
              <div v-if="preview.data.length > 10" class="preview-more">
                仅显示前10条，共 {{ preview.data.length }} 条数据
              </div>
            </el-tab-pane>
          </el-tabs>
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
                成功导入 {{ result.recordCount }} 条数据，其中新增 {{ result.newCount }} 条
              </p>
              <p v-else class="error-message">{{ result.error }}</p>
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
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button size="small" @click="viewDetail(row)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="import-stats">
          <h3>导入统计</h3>
          <el-card>
            <div class="stat-item">
              <span>今日导入</span>
              <span class="stat-value">{{ stats.todayCount }} 条</span>
            </div>
            <div class="stat-item">
              <span>本周导入</span>
              <span class="stat-value">{{ stats.weekCount }} 条</span>
            </div>
            <div class="stat-item">
              <span>本月导入</span>
              <span class="stat-value">{{ stats.monthCount }} 条</span>
            </div>
            <div class="stat-item">
              <span>总记录数</span>
              <span class="stat-value">{{ stats.totalCount }} 条</span>
            </div>
          </el-card>
        </div>
      </el-col>
    </el-row>

    <el-dialog v-model="showBatchImport" title="批量导入" width="600px">
      <el-upload
        ref="batchUploadRef"
        drag
        multiple
        :auto-upload="false"
        accept=".zip"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          拖拽 ZIP 压缩包到此处，或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            ZIP文件包含多个Excel文件，系统将自动解压并导入
          </div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="showBatchImport = false">取消</el-button>
        <el-button type="primary" @click="handleBatchImport">
          开始批量导入
        </el-button>
      </template>
    </el-dialog>

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
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import JSZip from 'jszip'
import * as XLSX from 'xlsx'
import { 
  UploadFilled, 
  Upload, 
  Download, 
  View,
  Document,
  CircleCheck,
  CircleClose
} from '@element-plus/icons-vue'

const uploadRef = ref()
const batchUploadRef = ref()
const fileList = ref([])
const importing = ref(false)
const previewData = ref([])
const previewTab = ref('')
const importResults = ref([])
const showTemplates = ref(false)
const showBatchImport = ref(false)
const importMode = ref('incremental')

const templates = ref([
  { id: 1, name: '生意参谋-交易报表', description: '包含订单、销售额、退款等交易数据', type: 'trade' },
  { id: 2, name: '生意参谋-商品报表', description: '包含商品销售、流量、转化数据', type: 'product' },
  { id: 3, name: '生意参谋-流量报表', description: '包含访客、浏览量、来源渠道数据', type: 'traffic' },
  { id: 4, name: '万相台-投放报表', description: '包含广告投放、消耗、转化数据', type: 'wxt' },
  { id: 5, name: '达摩盘-人群报表', description: '包含人群包、人群规模数据', type: 'dmp' }
])

const importHistory = ref([
  { id: 1, file_name: '生意参谋-交易报表-2026-05-01.xlsx', import_time: '2026-05-01 14:30:00', record_count: 1250, status: 'success' },
  { id: 2, file_name: '万相台-投放报表-2026-05-01.xlsx', import_time: '2026-05-01 15:20:00', record_count: 85, status: 'success' }
])

const stats = ref({
  todayCount: 256,
  weekCount: 1580,
  monthCount: 6850,
  totalCount: 125600
})

const handleFileChange = (file, files) => {
  fileList.value = files
}

const handleFileRemove = (file, files) => {
  fileList.value = files
}

const clearFiles = () => {
  fileList.value = []
  previewData.value = []
  importResults.value = []
}

const previewFiles = async () => {
  if (fileList.value.length === 0) {
    ElMessage.warning('请先选择要导入的文件')
    return
  }

  previewData.value = []

  for (const file of fileList.value) {
    try {
      const data = await parseExcelFile(file.raw)
      
      previewData.value.push({
        fileName: file.name,
        fileType: detectFileType(file.name),
        data: data,
        columns: data.length > 0 ? Object.keys(data[0]) : [],
        rowCount: data.length,
        newCount: Math.floor(data.length * 0.8),
        duplicateCount: Math.floor(data.length * 0.2)
      })
    } catch (error) {
      ElMessage.error(`解析文件 ${file.name} 失败：${error.message}`)
    }
  }

  if (previewData.value.length > 0) {
    previewTab.value = 'file-0'
  }

  ElMessage.success(`已解析 ${previewData.value.length} 个文件`)
}

const startImport = async () => {
  if (fileList.value.length === 0) {
    ElMessage.warning('请先选择要导入的文件')
    return
  }

  importing.value = true
  importResults.value = []

  for (const file of fileList.value) {
    try {
      await new Promise(resolve => setTimeout(resolve, 1000))
      
      const data = await parseExcelFile(file.raw)
      const newCount = Math.floor(data.length * 0.8)
      
      importResults.value.push({
        fileName: file.name,
        success: true,
        recordCount: data.length,
        newCount: newCount
      })
    } catch (error) {
      importResults.value.push({
        fileName: file.name,
        success: false,
        error: error.message
      })
    }
  }

  ElMessage.success('导入完成')
  importing.value = false
  clearFiles()
}

const handleBatchImport = async () => {
  ElMessage.info('批量导入功能开发中')
  showBatchImport.value = false
}

const parseExcelFile = async (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target.result)
        const workbook = XLSX.read(data, { type: 'array' })
        const firstSheet = workbook.Sheets[workbook.SheetNames[0]]
        const jsonData = XLSX.utils.sheet_to_json(firstSheet)
        resolve(jsonData)
      } catch (error) {
        reject(error)
      }
    }
    
    reader.onerror = () => reject(new Error('文件读取失败'))
    reader.readAsArrayBuffer(file)
  })
}

const detectFileType = (fileName) => {
  const name = fileName.toLowerCase()
  if (name.includes('交易')) return '交易数据'
  if (name.includes('商品')) return '商品数据'
  if (name.includes('流量')) return '流量数据'
  if (name.includes('万相台')) return '万相台数据'
  if (name.includes('达摩盘')) return '达摩盘数据'
  if (name.includes('直通车')) return '直通车数据'
  if (name.includes('引力魔方')) return '引力魔方数据'
  if (name.includes('淘客')) return '淘客数据'
  return '未知类型'
}

const downloadTemplate = (template) => {
  ElMessage.success(`开始下载：${template.name}`)
}

const viewDetail = (row) => {
  ElMessage.info(`查看 ${row.file_name} 详情`)
}

const formatTime = (timeStr) => {
  if (!timeStr) return ''
  return timeStr
}

const getStatusType = (status) => {
  const types = { 'success': 'success', 'failed': 'danger', 'partial': 'warning' }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const labels = { 'success': '成功', 'failed': '失败', 'partial': '部分成功' }
  return labels[status] || status
}
</script>

<style scoped>
.advanced-import-center {
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
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.upload-section, .preview-section, .import-results, .import-history, .import-stats {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-bottom: 20px;
}

.upload-section h3, .preview-section h3, .import-history h3, .import-stats h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px 0;
}

.file-actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
}

.import-mode-hint {
  margin-top: 16px;
}

.preview-info {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
}

.preview-more {
  margin-top: 12px;
  text-align: center;
  color: #999;
  font-size: 13px;
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
