<template>
  <div class="settings-page page-container">
    <el-card class="settings-card">
      <template #header>
        <div class="card-header">
          <el-icon><Tools /></el-icon>
          <span>系统设置</span>
        </div>
      </template>

      <el-tabs v-model="activeTab" class="settings-tabs">
        <el-tab-pane label="主题设置" name="theme">
          <div class="theme-preview">
            <div 
              v-for="t in themes" 
              :key="t.id"
              class="theme-card"
              :class="{ active: settings.theme === t.id }"
              @click="selectTheme(t.id)"
            >
              <div class="theme-preview-box" :class="`preview-${t.id}`">
                <div class="preview-sidebar"></div>
                <div class="preview-content"></div>
              </div>
              <span class="theme-label">{{ t.label }}</span>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="通用设置" name="general">
          <el-form label-width="160px">
            <el-form-item label="系统名称">
              <el-input v-model="settings.system_name" placeholder="输入系统名称" />
            </el-form-item>
            <el-form-item label="显示语言">
              <el-select v-model="settings.language" style="width: 100%">
                <el-option label="简体中文" value="zh-CN" />
                <el-option label="English" value="en-US" />
              </el-select>
            </el-form-item>
            <el-form-item label="默认时间范围">
              <el-select v-model="settings.default_date_range" style="width: 100%">
                <el-option label="今日" value="today" />
                <el-option label="本周" value="week" />
                <el-option label="本月" value="month" />
                <el-option label="最近30天" value="30days" />
                <el-option label="最近90天" value="90days" />
              </el-select>
            </el-form-item>
            <el-form-item label="自动刷新">
              <el-switch v-model="settings.auto_refresh" />
            </el-form-item>
            <el-form-item label="刷新间隔（分钟）" v-if="settings.auto_refresh">
              <el-input-number v-model="settings.refresh_interval" :min="1" :max="60" />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="KPI阈值设置" name="kpi">
          <el-form label-width="180px">
            <el-form-item label="GMV下降阈值（%）">
              <el-input-number v-model="settings.gmv_drop_threshold" :min="1" :max="100" />
            </el-form-item>
            <el-form-item label="最低GMV金额">
              <el-input-number v-model="settings.min_gmv_amount" :min="0" style="width: 100%" />
            </el-form-item>
            <el-form-item label="最低转化率（%）">
              <el-input-number v-model="settings.min_conversion_rate" :min="0" :max="100" :step="0.1" />
            </el-form-item>
            <el-form-item label="最低ROI">
              <el-input-number v-model="settings.min_roi" :min="0" :step="0.1" />
            </el-form-item>
            <el-form-item label="退款率阈值（%）">
              <el-input-number v-model="settings.refund_rate_threshold" :min="0" :max="100" :step="0.1" />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="通知设置" name="notifications">
          <el-form label-width="180px">
            <el-form-item label="弹窗通知">
              <el-switch v-model="settings.popup_notifications" />
            </el-form-item>
            <el-form-item label="浏览器通知">
              <el-switch v-model="settings.browser_notifications" />
            </el-form-item>
            <el-form-item label="告警邮件">
              <el-switch v-model="settings.email_alerts" />
            </el-form-item>
            <el-form-item label="收件邮箱" v-if="settings.email_alerts">
              <el-input v-model="settings.email_recipient" placeholder="example@company.com" />
            </el-form-item>
            <el-form-item label="告警频率">
              <el-select v-model="settings.alert_frequency" style="width: 100%">
                <el-option label="实时" value="real-time" />
                <el-option label="每小时" value="hourly" />
                <el-option label="每天" value="daily" />
                <el-option label="每周" value="weekly" />
              </el-select>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="数据导出设置" name="export">
          <el-form label-width="180px">
            <el-form-item label="默认导出格式">
              <el-select v-model="settings.export_format" style="width: 100%">
                <el-option label="CSV" value="csv" />
                <el-option label="Excel" value="xlsx" />
                <el-option label="JSON" value="json" />
              </el-select>
            </el-form-item>
            <el-form-item label="导出日期格式">
              <el-select v-model="settings.export_date_format" style="width: 100%">
                <el-option label="YYYY-MM-DD" value="YYYY-MM-DD" />
                <el-option label="MM/DD/YYYY" value="MM/DD/YYYY" />
                <el-option label="DD/MM/YYYY" value="DD/MM/YYYY" />
              </el-select>
            </el-form-item>
            <el-form-item label="导出编码">
              <el-select v-model="settings.export_encoding" style="width: 100%">
                <el-option label="UTF-8" value="utf-8" />
                <el-option label="GBK" value="gbk" />
                <el-option label="UTF-16" value="utf-16" />
              </el-select>
            </el-form-item>
            <el-form-item label="包含图表">
              <el-switch v-model="settings.export_with_charts" />
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <div class="actions">
        <el-button @click="handleReset">重置</el-button>
        <el-button type="primary" @click="handleSave" :loading="loading">
          保存设置
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload, Tools } from '@element-plus/icons-vue'
import api from '@/api'

const activeTab = ref('theme')
const loading = ref(false)
const initialized = ref(false)

const themes = [
  { id: 'light', label: '明亮' },
  { id: 'dark', label: '暗黑' }
]

const defaultSettings = {
  system_name: '数据仪表盘',
  language: 'zh-CN',
  theme: 'light',
  default_date_range: 'month',
  auto_refresh: false,
  refresh_interval: 10,
  gmv_drop_threshold: 20,
  min_gmv_amount: 10000,
  min_conversion_rate: 2,
  min_roi: 1.5,
  refund_rate_threshold: 15,
  popup_notifications: true,
  browser_notifications: true,
  email_alerts: false,
  email_recipient: '',
  alert_frequency: 'real-time',
  export_format: 'csv',
  export_date_format: 'YYYY-MM-DD',
  export_encoding: 'utf-8',
  export_with_charts: false
}

const settings = ref({ ...defaultSettings })

const selectTheme = (themeId) => {
  settings.value.theme = themeId
  document.body.className = ''
  if (themeId === 'dark') {
    document.body.classList.add('dark-theme')
  }
  localStorage.setItem('theme', themeId)
}

const loadSettings = async () => {
  try {
    const response = await api.getSettings()
    if (response.data && Object.keys(response.data).length > 0) {
      settings.value = { ...defaultSettings, ...response.data }
    } else {
      await initializeDefaultSettings()
    }
  } catch (error) {
    console.error('加载设置失败:', error)
    await initializeDefaultSettings()
  }
  
  // 应用主题
  if (settings.value.theme === 'dark') {
    document.body.classList.add('dark-theme')
  }
}

const initializeDefaultSettings = async () => {
  try {
    await api.initializeSettings()
    settings.value = { ...defaultSettings }
  } catch (error) {
    console.error('初始化默认设置失败:', error)
  }
}

const handleSave = async () => {
  loading.value = true
  try {
    await api.updateSettings(settings.value)
    ElMessage.success('设置已保存')
  } catch (error) {
    ElMessage.error('保存失败: ' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

const handleReset = () => {
  settings.value = { ...defaultSettings }
  selectTheme('light')
  ElMessage.info('已重置为默认设置')
}

onMounted(() => {
  loadSettings()
})
</script>

<style scoped>
.settings-page {
  padding: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 500;
}

.theme-preview {
  display: flex;
  gap: 20px;
}

.theme-card {
  cursor: pointer;
  text-align: center;
  transition: transform 0.2s;
}

.theme-card:hover {
  transform: translateY(-2px);
}

.theme-card.active .theme-label {
  color: var(--el-color-primary);
  font-weight: 600;
}

.theme-preview-box {
  width: 200px;
  height: 140px;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  box-shadow: 0 2px 12px rgba(0,0,0,0.1);
  border: 2px solid transparent;
  transition: border-color 0.2s;
}

.theme-card.active .theme-preview-box {
  border-color: var(--el-color-primary);
}

.preview-light {
  background-color: #f5f7fa;
}

.preview-light .preview-sidebar {
  width: 60px;
  background-color: #303133;
}

.preview-light .preview-content {
  flex: 1;
  padding: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.preview-light .preview-content::before,
.preview-light .preview-content::after {
  content: '';
  width: 38px;
  height: 26px;
  background-color: white;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}

.preview-dark {
  background-color: #1f1f1f;
}

.preview-dark .preview-sidebar {
  width: 60px;
  background-color: #0f0f0f;
}

.preview-dark .preview-content {
  flex: 1;
  padding: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.preview-dark .preview-content::before,
.preview-dark .preview-content::after {
  content: '';
  width: 38px;
  height: 26px;
  background-color: #2d2d2d;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.1);
}

.theme-label {
  display: block;
  margin-top: 12px;
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.actions {
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid var(--el-border-color-lighter);
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
