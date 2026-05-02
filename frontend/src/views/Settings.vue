<template>
  <div class="settings-page">
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-icon><Setting /></el-icon>
            <span>系统设置</span>
          </div>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="基本设置" name="basic">
          <el-form label-position="right" label-width="120px">
            <el-form-item label="系统名称">
              <el-input v-model="settings.systemName" placeholder="数据仪表盘" />
            </el-form-item>
            <el-form-item label="显示语言">
              <el-select v-model="settings.language" style="width: 200px;">
                <el-option label="简体中文" value="zh-CN" />
                <el-option label="English" value="en-US" />
              </el-select>
            </el-form-item>
            <el-form-item label="默认时间范围">
              <el-select v-model="settings.defaultDateRange" style="width: 200px;">
                <el-option label="今日" value="day" />
                <el-option label="本周" value="week" />
                <el-option label="本月" value="month" />
              </el-select>
            </el-form-item>
            <el-form-item label="自动刷新">
              <el-switch v-model="settings.autoRefresh" />
              <span style="margin-left: 12px; color: #909399;">
                每 {{ settings.refreshInterval }} 分钟自动刷新数据
              </span>
            </el-form-item>
            <el-form-item v-if="settings.autoRefresh" label="刷新间隔">
              <el-slider v-model="settings.refreshInterval" :min="1" :max="60" style="width: 250px;" />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="告警设置" name="alerts">
          <el-form label-position="right" label-width="160px">
            <el-divider content-position="left">GMV 告警</el-divider>
            <el-form-item label="GMV 下降阈值">
              <el-input-number v-model="settings.gmvDropThreshold" :min="0" :max="100" :precision="1" suffix="%" />
            </el-form-item>
            <el-form-item label="最低 GMV 金额">
              <el-input-number v-model="settings.minGmvAmount" :min="0" :precision="0" style="width: 200px;" />
            </el-form-item>
            
            <el-divider content-position="left">转化率告警</el-divider>
            <el-form-item label="最低转化率">
              <el-input-number v-model="settings.minConversionRate" :min="0" :max="100" :precision="2" suffix="%" />
            </el-form-item>
            <el-form-item label="最低 ROI">
              <el-input-number v-model="settings.minROI" :min="0" :precision="2" />
            </el-form-item>
            
            <el-divider content-position="left">退款告警</el-divider>
            <el-form-item label="退款率阈值">
              <el-input-number v-model="settings.refundRateThreshold" :min="0" :max="100" :precision="1" suffix="%" />
            </el-form-item>
            
            <el-form-item>
              <el-button type="primary" @click="testAlerts">测试告警</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="通知设置" name="notifications">
          <el-form label-position="right" label-width="160px">
            <el-form-item label="弹窗通知">
              <el-switch v-model="settings.popupNotifications" />
            </el-form-item>
            <el-form-item label="浏览器通知">
              <el-switch v-model="settings.browserNotifications" />
            </el-form-item>
            <el-form-item label="告警邮件">
              <el-switch v-model="settings.emailAlerts" />
            </el-form-item>
            <el-form-item v-if="settings.emailAlerts" label="收件邮箱">
              <el-input v-model="settings.emailRecipient" placeholder="admin@example.com" style="width: 300px;" />
            </el-form-item>
            <el-form-item label="告警频率">
              <el-select v-model="settings.alertFrequency" style="width: 200px;">
                <el-option label="实时" value="real-time" />
                <el-option label="每小时" value="hourly" />
                <el-option label="每天" value="daily" />
              </el-select>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="导出设置" name="export">
          <el-form label-position="right" label-width="160px">
            <el-form-item label="默认导出格式">
              <el-select v-model="settings.exportFormat" style="width: 200px;">
                <el-option label="Excel (.xlsx)" value="xlsx" />
                <el-option label="CSV" value="csv" />
                <el-option label="PDF" value="pdf" />
              </el-select>
            </el-form-item>
            <el-form-item label="导出日期格式">
              <el-select v-model="settings.exportDateFormat" style="width: 200px;">
                <el-option label="YYYY-MM-DD" value="YYYY-MM-DD" />
                <el-option label="MM/DD/YYYY" value="MM/DD/YYYY" />
              </el-select>
            </el-form-item>
            <el-form-item label="导出编码">
              <el-select v-model="settings.exportEncoding" style="width: 200px;">
                <el-option label="UTF-8" value="utf-8" />
                <el-option label="GBK" value="gbk" />
              </el-select>
            </el-form-item>
            <el-form-item label="包含图表">
              <el-switch v-model="settings.exportWithCharts" />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="关于系统" name="about">
          <el-descriptions :column="2" border style="margin-bottom: 20px;">
            <el-descriptions-item label="系统名称">数据仪表盘</el-descriptions-item>
            <el-descriptions-item label="版本号">2.0.0</el-descriptions-item>
            <el-descriptions-item label="前端框架">Vue 3 + Element Plus</el-descriptions-item>
            <el-descriptions-item label="后端框架">FastAPI</el-descriptions-item>
            <el-descriptions-item label="数据存储">SQLite</el-descriptions-item>
            <el-descriptions-item label="图表库">ECharts</el-descriptions-item>
          </el-descriptions>
          
          <el-card>
            <template #header>
              <span>功能模块</span>
            </template>
            <el-tag 
              v-for="feature in features" 
              :key="feature"
              style="margin: 4px;"
              size="small"
              type="success"
            >
              {{ feature }}
            </el-tag>
          </el-card>
        </el-tab-pane>
      </el-tabs>

      <div class="settings-actions">
        <el-button @click="resetSettings">重置默认</el-button>
        <el-button type="primary" @click="saveSettings" :loading="saving">保存设置</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const activeTab = ref('basic')
const saving = ref(false)

const features = [
  '数据概览', '商品管理', '数据导入', 'KPI分析', '趋势分析', '广告投放',
  '健康度评分', '退款分析', '异常告警', '评价分析', '市场分析',
  '四象限分析', '目标管理', '智能选品', '自动报告', '预测分析',
  '数据质量', '操作统计'
]

const settings = ref({
  systemName: '数据仪表盘',
  language: 'zh-CN',
  defaultDateRange: 'month',
  autoRefresh: false,
  refreshInterval: 10,
  gmvDropThreshold: 20,
  minGmvAmount: 10000,
  minConversionRate: 2,
  minROI: 1.5,
  refundRateThreshold: 15,
  popupNotifications: true,
  browserNotifications: true,
  emailAlerts: false,
  emailRecipient: '',
  alertFrequency: 'real-time',
  exportFormat: 'csv',
  exportDateFormat: 'YYYY-MM-DD',
  exportEncoding: 'utf-8',
  exportWithCharts: false
})

const loadSettings = () => {
  const saved = localStorage.getItem('dashboardSettings')
  if (saved) {
    try {
      settings.value = { ...settings.value, ...JSON.parse(saved) }
    } catch (e) {
      console.error('Load settings error:', e)
    }
  }
}

const saveSettings = async () => {
  saving.value = true
  try {
    localStorage.setItem('dashboardSettings', JSON.stringify(settings.value))
    ElMessage.success('设置已保存')
  } catch (e) {
    ElMessage.error('保存设置失败')
  } finally {
    saving.value = false
  }
}

const resetSettings = () => {
  settings.value = {
    systemName: '数据仪表盘',
    language: 'zh-CN',
    defaultDateRange: 'month',
    autoRefresh: false,
    refreshInterval: 10,
    gmvDropThreshold: 20,
    minGmvAmount: 10000,
    minConversionRate: 2,
    minROI: 1.5,
    refundRateThreshold: 15,
    popupNotifications: true,
    browserNotifications: true,
    emailAlerts: false,
    emailRecipient: '',
    alertFrequency: 'real-time',
    exportFormat: 'csv',
    exportDateFormat: 'YYYY-MM-DD',
    exportEncoding: 'utf-8',
    exportWithCharts: false
  }
  ElMessage.info('已重置为默认设置')
}

const testAlerts = () => {
  ElMessage.warning('测试告警：GMV 下降超过阈值！')
}

onMounted(() => {
  loadSettings()
})
</script>

<style scoped>
.settings-page {
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

.settings-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #ebeef5;
}

:deep(.el-divider) {
  margin: 16px 0;
}

:deep(.el-divider__text) {
  font-size: 14px;
  font-weight: 500;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .settings-actions {
    justify-content: center;
  }
  
  :deep(.el-form-item__label) {
    width: auto !important;
  }
  
  :deep(.el-form-item__content) {
    margin-left: 0 !important;
  }
}
</style>
