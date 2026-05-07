<template>
  <div class="smart-alert-container page-container">
    <div class="page-header">
      <h1>智能告警中心</h1>
      <div class="header-actions">
        <el-button type="primary" @click="checkAlerts">
          <el-icon><Refresh /></el-icon> 检查告警
        </el-button>
      </div>
    </div>

    <div v-loading="loading" class="content-area">
      <el-row :gutter="20" class="summary-cards">
        <el-col :xs="12" :sm="6" :md="6" :lg="6">
          <div class="stat-card warning">
            <div class="stat-label">待处理</div>
            <div class="stat-value">{{ alertStats.pending }}</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6" :md="6" :lg="6">
          <div class="stat-card danger">
            <div class="stat-label">严重告警</div>
            <div class="stat-value">{{ alertStats.critical }}</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6" :md="6" :lg="6">
          <div class="stat-card info">
            <div class="stat-label">已忽略</div>
            <div class="stat-value">{{ alertStats.dismissed }}</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6" :md="6" :lg="6">
          <div class="stat-card success">
            <div class="stat-label">已解决</div>
            <div class="stat-value">{{ alertStats.resolved }}</div>
          </div>
        </el-col>
      </el-row>

      <el-tabs v-model="activeTab" type="border-card">
        <el-tab-pane label="告警列表" name="alerts">
          <div class="filter-bar">
            <el-select v-model="filterLevel" placeholder="告警级别" clearable style="width: 120px; margin-right: 12px">
              <el-option label="全部" value=""></el-option>
              <el-option label="严重" value="critical"></el-option>
              <el-option label="警告" value="warning"></el-option>
              <el-option label="提示" value="info"></el-option>
            </el-select>
            <el-checkbox v-model="filterUnresolved" style="margin-right: 12px">仅显示未解决</el-checkbox>
            <el-button type="primary" size="small" @click="showCreateRule = true">
              <el-icon><Plus /></el-icon> 新增规则
            </el-button>
          </div>

          <div class="alert-list">
            <div v-for="alert in filteredAlerts" :key="alert.id" class="alert-item" :class="alert.level">
              <div class="alert-header">
                <div class="alert-title">
                  <el-tag size="small" :type="getLevelType(alert.level)">{{ getLevelLabel(alert.level) }}</el-tag>
                  <span>{{ alert.title }}</span>
                </div>
                <div class="alert-time">{{ formatTime(alert.created_at) }}</div>
              </div>
              <div class="alert-body">
                <p class="alert-detail">{{ alert.detail }}</p>
                <div v-if="alert.product_title" class="alert-product">
                  <span>产品: {{ alert.product_title }}</span>
                </div>
                <div class="alert-metrics">
                  <span v-if="alert.metric">指标: {{ alert.metric }}</span>
                  <span v-if="alert.current_value != null">当前值: {{ alert.current_value }}</span>
                  <span v-if="alert.threshold_value != null">阈值: {{ alert.threshold_value }}</span>
                </div>
                <div v-if="alert.recommendations" class="alert-recommendations">
                  <strong>建议:</strong>
                  <ul>
                    <li v-for="(rec, idx) in alert.recommendations" :key="idx">{{ rec }}</li>
                  </ul>
                </div>
              </div>
              <div class="alert-footer">
                <template v-if="!alert.resolved && !alert.dismissed">
                  <el-button size="small" @click="dismissAlert(alert.id)">忽略</el-button>
                  <el-button size="small" type="primary" @click="resolveAlert(alert.id)">解决</el-button>
                </template>
                <template v-else>
                  <el-tag v-if="alert.resolved" type="success" size="small">已解决</el-tag>
                  <el-tag v-if="alert.dismissed" type="info" size="small">已忽略</el-tag>
                </template>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="告警规则" name="rules">
          <div class="table-card">
            <div class="card-header">
              <h3>告警规则配置</h3>
              <el-button type="primary" size="small" @click="showCreateRule = true">
                <el-icon><Plus /></el-icon> 新增规则
              </el-button>
            </div>
            <el-table :data="rules" style="width: 100%">
              <el-table-column prop="rule_name" label="规则名称" width="200"></el-table-column>
              <el-table-column label="规则" width="300">
                <template #default="{ row }">
                  {{ row.metric }} {{ row.operator }} {{ row.threshold }} (连续{{ row.window_size }}天)
                </template>
              </el-table-column>
              <el-table-column prop="level" label="级别" width="100">
                <template #default="{ row }">
                  <el-tag size="small" :type="getLevelType(row.level)">{{ getLevelLabel(row.level) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-switch v-model="row.enabled" @change="toggleRule(row.id, row.enabled)" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="150" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" @click="handleEditRule(row)">编辑</el-button>
                  <el-button size="small" type="danger" @click="handleDeleteRule(row.id)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <el-tab-pane label="供应链告警" name="supply">
          <div class="table-card">
            <div class="card-header">
              <h3>供应链告警</h3>
            </div>
            <el-table :data="supplyChainAlerts" style="width: 100%">
              <el-table-column prop="product_id" label="产品ID" width="120"></el-table-column>
              <el-table-column prop="title" label="标题" width="200"></el-table-column>
              <el-table-column prop="alert_type" label="类型" width="120">
                <template #default="{ row }">
                  <el-tag size="small">{{ row.alert_type }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="current_stock" label="当前库存" width="100"></el-table-column>
              <el-table-column prop="status" label="状态" width="100">
                <template #default="{ row }">
                  <el-tag size="small">{{ row.status }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="detail" label="详情"></el-table-column>
            </el-table>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Plus } from '@element-plus/icons-vue'
import api from '@/api'

const loading = ref(false)
const activeTab = ref('alerts')
const filterLevel = ref('')
const filterUnresolved = ref(false)
const showCreateRule = ref(false)

const alertStats = ref({
  pending: 0,
  critical: 0,
  dismissed: 0,
  resolved: 0
})

const alerts = ref([])
const rules = ref([])
const supplyChainAlerts = ref([])

const filteredAlerts = computed(() => {
  return alerts.value.filter(a => {
    if (filterLevel.value && a.level !== filterLevel.value) return false
    if (filterUnresolved.value && (a.resolved || a.dismissed)) return false
    return true
  })
})

const refresh = async () => {
  loading.value = true
  try {
    const [alertsRes, rulesRes, supplyRes] = await Promise.allSettled([
      api.request.get('/smart-alert/alerts'),
      api.request.get('/smart-alert/rules'),
      api.request.get('/smart-alert/supply-chain')
    ])

    if (alertsRes.status === 'fulfilled') {
      alerts.value = alertsRes.value.alerts || alertsRes.value.data || []
    }
    if (rulesRes.status === 'fulfilled') {
      rules.value = rulesRes.value.rules || rulesRes.value.data || []
    }
    if (supplyRes.status === 'fulfilled') {
      supplyChainAlerts.value = supplyRes.value.alerts || supplyRes.value.data || []
    }

    updateAlertStats()
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const checkAlerts = async () => {
  loading.value = true
  try {
    const data = await api.request.post('/smart-alert/check')
    ElMessage.success(`检查完成，新增${data.new_alerts || 0}条告警`)
    refresh()
  } catch (error) {
    ElMessage.error('检查告警失败，请重试')
  } finally {
    loading.value = false
  }
}

const updateAlertStats = () => {
  alertStats.value.pending = alerts.value.filter(a => !a.resolved && !a.dismissed).length
  alertStats.value.critical = alerts.value.filter(a => a.level === 'critical' && !a.resolved).length
  alertStats.value.dismissed = alerts.value.filter(a => a.dismissed).length
  alertStats.value.resolved = alerts.value.filter(a => a.resolved).length
}

const dismissAlert = async (alertId) => {
  try {
    await api.request.post(`/smart-alert/alerts/${alertId}/dismiss`)
    ElMessage.success('已忽略告警')
    refresh()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const resolveAlert = async (alertId) => {
  try {
    await api.request.post(`/smart-alert/alerts/${alertId}/resolve`)
    ElMessage.success('告警已解决')
    refresh()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const toggleRule = async (ruleId, enabled) => {
  try {
    await api.request.post(`/smart-alert/rules/${ruleId}`, { enabled })
    ElMessage.success('状态已更新')
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const handleEditRule = (rule) => {
  ElMessage.info('编辑功能开发中')
}

const handleDeleteRule = async (ruleId) => {
  try {
    await ElMessageBox.confirm('确定要删除此规则吗？', '确认删除', {
      type: 'warning'
    })
    await api.request.delete(`/smart-alert/rules/${ruleId}`)
    ElMessage.success('规则已删除')
    refresh()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const getLevelType = (level) => {
  const types = { 'critical': 'danger', 'warning': 'warning', 'info': 'info' }
  return types[level] || ''
}

const getLevelLabel = (level) => {
  const labels = { 'critical': '严重', 'warning': '警告', 'info': '提示' }
  return labels[level] || level
}

const formatTime = (timeStr) => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  if (isNaN(date.getTime())) return timeStr
  return date.toLocaleString()
}

onMounted(() => {
  refresh()
})
</script>

<style scoped>
.smart-alert-container {
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

.summary-cards {
  margin-bottom: 20px;
}

.stat-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.stat-card.warning .stat-value { color: #E6A23C; }
.stat-card.danger .stat-value { color: #F56C6C; }
.stat-card.info .stat-value { color: #409EFF; }
.stat-card.success .stat-value { color: #67C23A; }

.stat-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
}

.filter-bar {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
}

.alert-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.alert-item {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  border-left: 4px solid #ccc;
}

.alert-item.critical { border-left-color: #F56C6C; }
.alert-item.warning { border-left-color: #E6A23C; }
.alert-item.info { border-left-color: #409EFF; }

.alert-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.alert-title {
  display: flex;
  align-items: center;
  gap: 12px;
  font-weight: 600;
}

.alert-time {
  color: #999;
  font-size: 13px;
}

.alert-body {
  color: #666;
}

.alert-detail {
  margin-bottom: 12px;
}

.alert-product {
  margin-bottom: 8px;
  color: #409EFF;
}

.alert-metrics {
  display: flex;
  gap: 24px;
  margin-bottom: 12px;
  font-size: 13px;
}

.alert-recommendations {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-size: 13px;
}

.alert-recommendations ul {
  margin: 8px 0 0 16px;
  padding: 0;
}

.alert-footer {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #eee;
}

.table-card {
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
</style>
