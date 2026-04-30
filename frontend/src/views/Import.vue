<template>
  <div class="import">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>导入 Excel 数据</span>
        </div>
      </template>
      <el-alert
        type="info"
        :closable="false"
        style="margin-bottom: 20px"
      >
        <template #title>
          请确保 Excel 文件包含以下 Sheet：
          <ul>
            <li><strong>单品-新</strong> - 商品基本信息和周度数据</li>
          </ul>
        </template>
      </el-alert>

      <el-form :model="form" label-width="120px" style="max-width: 600px">
        <el-form-item label="数据文件">
          <el-upload
            ref="uploadRef"
            drag
            :auto-upload="false"
            :show-file-list="true"
            :on-change="handleChange"
            :limit="1"
            accept=".xlsx,.xls"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">
              将文件拖到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                只能上传 .xlsx/.xls 文件
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
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handleImport" :disabled="!file">
            开始导入
          </el-button>
        </el-form-item>
      </el-form>

      <el-divider v-if="result" />

      <div v-if="result" class="result">
        <el-alert
          :title="result.saved ? '导入成功' : '导入失败'"
          :type="result.saved ? 'success' : 'error'"
        />
        <div v-if="result.saved" class="stats">
          <el-statistic title="商品数" :value="result.parsed?.products || 0" />
          <el-divider direction="vertical" />
          <el-statistic title="周度数据" :value="result.parsed?.weekly_data || 0" />
          <el-divider direction="vertical" />
          <el-statistic title="操作记录" :value="result.parsed?.actions || 0" />
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

const uploadRef = ref(null)
const file = ref(null)
const loading = ref(false)
const result = ref(null)
const form = ref({
  week_start: ''
})

const handleChange = (fileObj) => {
  file.value = fileObj.raw
}

const handleImport = async () => {
  if (!file.value) {
    ElMessage.warning('请选择文件')
    return
  }

  loading.value = true
  try {
    const res = await api.importExcel(file.value, form.value.week_start)
    result.value = {
      saved: true,
      ...res.data
    }
    ElMessage.success('导入成功')
  } catch (error) {
    result.value = {
      saved: false
    }
    ElMessage.error(error.response?.data?.detail || '导入失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.import {
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
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
