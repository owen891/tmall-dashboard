<template>
  <div class="common-upload">
    <!-- 单文件上传 -->
    <div v-if="!multiple" class="single-upload">
      <el-upload
        :drag="drag"
        :auto-upload="false"
        :show-file-list="true"
        :on-change="handleChange"
        :on-remove="handleRemove"
        :limit="1"
        :accept="accept"
        :disabled="disabled"
        :file-list="fileList"
        class="upload-area"
      >
        <el-icon class="upload-icon" v-if="!fileList.length"><UploadFilled /></el-icon>
        <div class="upload-text" v-if="!fileList.length">
          {{ drag ? '拖拽文件到此处' : '' }}<span class="link">点击上传</span>
        </div>
        <template #tip v-if="tip">
          <div class="el-upload__tip">{{ tip }}</div>
        </template>
      </el-upload>

      <div class="upload-actions" v-if="fileList.length > 0 && !disabled">
        <el-button type="primary" :loading="loading" @click="handleUpload" size="small">
          <el-icon v-if="!loading"><Upload /></el-icon>
          {{ loading ? '上传中...' : '上传' }}
        </el-button>
        <el-button @click="handleClear" size="small">清空</el-button>
      </div>
    </div>

    <!-- 多文件上传 -->
    <div v-else class="multiple-upload">
      <el-upload
        :drag="drag"
        :auto-upload="false"
        :show-file-list="true"
        :on-change="handleChange"
        :on-remove="handleRemove"
        :limit="limit"
        :accept="accept"
        :disabled="disabled"
        :file-list="fileList"
        multiple
        class="upload-area"
      >
        <el-icon class="upload-icon" v-if="fileList.length < limit"><UploadFilled /></el-icon>
        <div class="upload-text" v-if="fileList.length < limit">
          {{ drag ? '拖拽文件到此处' : '' }}<span class="link">点击上传</span>
        </div>
        <template #tip v-if="tip">
          <div class="el-upload__tip">{{ tip }}</div>
        </template>
      </el-upload>

      <div class="upload-actions" v-if="fileList.length > 0 && !disabled">
        <el-button type="primary" :loading="loading" @click="handleUpload" size="small">
          <el-icon v-if="!loading"><Upload /></el-icon>
          {{ loading ? '上传中...' : `上传 ${fileList.length} 个文件` }}
        </el-button>
        <el-button @click="handleClear" size="small">清空</el-button>
      </div>
    </div>

    <!-- 上传结果展示 -->
    <div v-if="uploadResults.length > 0" class="upload-results">
      <div class="result-header">
        <span>上传结果</span>
        <el-tag type="success" size="small">成功: {{ successCount }}</el-tag>
        <el-tag type="danger" size="small" v-if="errorCount > 0">失败: {{ errorCount }}</el-tag>
      </div>
      <el-table :data="uploadResults" stripe size="small" max-height="300">
        <el-table-column prop="file_name" label="文件名" show-overflow-tooltip />
        <el-table-column prop="file_size_human" label="大小" width="100" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'" size="small">
              {{ row.success ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" v-if="showActions">
          <template #default="{ row }">
            <el-button link size="small" @click="handleDownload(row)" v-if="row.success">
              <el-icon><Download /></el-icon>下载
            </el-button>
            <el-button link size="small" type="danger" @click="handleDelete(row)" v-if="row.success && row.id">
              <el-icon><Delete /></el-icon>删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

const props = defineProps({
  multiple: {
    type: Boolean,
    default: false
  },
  drag: {
    type: Boolean,
    default: true
  },
  limit: {
    type: Number,
    default: 10
  },
  accept: {
    type: String,
    default: '' // 默认支持所有类型
  },
  usageType: {
    type: String,
    default: 'default'
  },
  usageId: {
    type: Number,
    default: null
  },
  createdBy: {
    type: String,
    default: null
  },
  disabled: {
    type: Boolean,
    default: false
  },
  tip: {
    type: String,
    default: ''
  },
  showActions: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['success', 'error', 'change', 'upload-complete'])

const fileList = ref([])
const loading = ref(false)
const uploadResults = ref([])

const successCount = computed(() => uploadResults.value.filter(r => r.success).length)
const errorCount = computed(() => uploadResults.value.filter(r => !r.success).length)

const handleChange = (file, files) => {
  fileList.value = files
  emit('change', { file, files })
}

const handleRemove = (file, files) => {
  fileList.value = files
  emit('change', { file, files })
}

const handleClear = () => {
  fileList.value = []
  uploadResults.value = []
}

const handleUpload = async () => {
  if (fileList.value.length === 0) {
    ElMessage.warning('请选择文件')
    return
  }

  loading.value = true
  uploadResults.value = []

  try {
    if (props.multiple && fileList.value.length > 1) {
      // 批量上传
      const files = fileList.value.map(f => f.raw)
      const response = await api.uploadMultipleFiles(
        files,
        props.usageType,
        props.usageId,
        props.createdBy
      )

      response.data.success.forEach(item => {
        uploadResults.value.push({
          ...item,
          success: true
        })
      })

      response.data.errors.forEach(item => {
        uploadResults.value.push({
          file_name: item.file_name,
          error: item.error,
          success: false
        })
      })

      emit('upload-complete', response.data)

      if (response.data.success_count > 0) {
        ElMessage.success(`成功上传 ${response.data.success_count} 个文件`)
      }
      if (response.data.error_count > 0) {
        ElMessage.warning(`${response.data.error_count} 个文件上传失败`)
      }
    } else {
      // 单文件上传
      const file = fileList.value[0].raw
      const response = await api.uploadFile(
        file,
        props.usageType,
        props.usageId,
        props.createdBy
      )

      uploadResults.value.push({
        ...response.data,
        success: true
      })

      emit('success', response.data)
      ElMessage.success('上传成功')
    }
  } catch (error) {
    ElMessage.error(error.message || '上传失败')
    emit('error', error)
  } finally {
    loading.value = false
  }
}

const handleDownload = (fileInfo) => {
  if (!fileInfo.id) return
  
  const url = `/api/upload/download/${fileInfo.id}`
  const link = document.createElement('a')
  link.href = url
  link.download = fileInfo.file_name
  link.click()
}

const handleDelete = async (fileInfo) => {
  if (!fileInfo.id) return

  try {
    await api.deleteFile(fileInfo.id)
    uploadResults.value = uploadResults.value.filter(r => r.id !== fileInfo.id)
    ElMessage.success('删除成功')
  } catch (error) {
    ElMessage.error('删除失败')
  }
}
</script>

<style scoped>
.common-upload {
  width: 100%;
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

.upload-actions {
  margin-top: 16px;
  display: flex;
  gap: 12px;
}

.upload-results {
  margin-top: 24px;
  padding: 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}
</style>
