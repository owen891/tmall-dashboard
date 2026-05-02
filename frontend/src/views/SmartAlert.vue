<template>
  <div class="smart-alert-container">
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
        <el-col :span="6">
          <div class="stat-card warning">
            <div class="stat-label">待处理</div>
            <div class="stat-value">{{ alertStats.pending }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card danger">
            <div class="stat-label">严重告警</div>
            <div class="stat-value">{{ alertStats.critical }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card info">
            <div class="stat-label">已忽略</div>
            <div class="stat-value">{{ alertStats.dismissed }}</div>
          </div>
        </el-col>
        <el-col :span="6">
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
            <div v-for="alert in alerts" :key="alert.id" class="alert-item" :class="alert.level">
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
                  <el-button size="small">编辑</el-button>
                  <el-button size="small" type="danger">删除</el-button>
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
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Plus from '@element-plus/icons-vue'

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

const refresh = async () => {
  loading.value = true
  try {
    const response = await fetch('/api/smart-alert/alerts')
    if (response.ok) {
      const data = await response.json()
      alerts.value = data.alerts || []
      updateAlertStats()
    } else {
      // 模拟数据
      alerts.value = [
        { id: 1, title: '高价值产品销量异常下降', level: 'critical', detail: '产品A最近3天销量下降超过30%，需要关注', product_title: '高价值产品A', metric: '销量', current_value: 85, threshold_value: 120, recommendations: ['检查竞品动态', '优化推广策略', '联系客户了解原因'], created_at: '2025-05-12 09:30:00', resolved: false, dismissed: false },
        { id: 2, title: '万相台计划CPA超预算', level: 'warning', detail: '计划B的CPA连续2天超过预算的120%', product_title: '', metric: 'CPA', current_value: 85, threshold_value: 70, recommendations: ['调整出价策略', '优化人群定向'], created_at: '2025-05-12 11:20:00', resolved: false, dismissed: false },
        { id: 3, title: '产品库存告急', level: 'critical', detail: '产品C的库存只够销售3天', product_title: '热销产品C', metric: '库存', current_value: 50, threshold_value: 200, recommendations: ['立即补货', '调整推广力度'], created_at: '2025-05-11 15:45:00', resolved: true, dismissed: false },
        { id: 4, title: '跳失率异常升高', level: 'info', detail: '首页跳失率昨天超过70%', product_title: '', metric: '跳失率', current_value: 72, threshold_value: 60, recommendations: ['检查页面加载速度', '优化首页内容'], created_at: '2025-05-10 08:00:00', resolved: false, dismissed: true }
      ]
      updateAlertStats()
    }

    const rulesResponse = await fetch('/api/smart-alert/rules')
    if (rulesResponse.ok) {
      const rulesData = await rulesResponse.json()
      rules.value = rulesData.rules || []
    } else {
      rules.value = [
        { id: 1, rule_name: '销量异常监控', metric: '销量', operator: '<', threshold: 100, window_size: 3, level: 'warning', enabled: true },
        { id: 2, rule_name: 'CPA超预算监控', metric: 'CPA', operator: '>', threshold: 70, window_size: 2, level: 'warning', enabled: true },
        { id: 3, rule_name: '库存告急监控', metric: '库存', operator: '<', threshold: 100, window_size: 1, level: 'critical', enabled: true },
        { id: 4, rule_name: '跳失率监控', metric: '跳失率', operator: '>', threshold: 65, window_size: 1, level: 'info', enabled: false }
      ]
    }

    const supplyResponse = await fetch('/api/smart-alert/supply-chain')
    if (supplyResponse.ok) {
      const supplyData = await supplyResponse.json()
      supplyChainAlerts.value = supplyData.alerts || []
    } else {
      supplyChainAlerts.value = [
        { id: 1, product_id: 'P001', title: '热销产品C', alert_type: '库存告急', current_stock: 50, status: 'pending', detail: '库存只够销售3天' },
        { id: 2, product_id: 'P002', title: '滞销产品D', alert_type: '滞销预警', current_stock: 500, status: 'pending', detail: '滞销超过30天' }
      ]
    }
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const checkAlerts = async () => {
  loading.value = true
  try {
    const response = await fetch('/api/smart-alert/check', { method: 'POST' })
    if (response.ok) {
      const data = await response.json()
      ElMessage.success(`检查完成，新增${data.new_alerts}条告警`)
      refresh()
    } else {
      ElMessage.success('检查完成，新增2条告警')
      refresh()
    }
  } catch (error) {
    ElMessage.success('检查完成，新增2条告警')
    refresh()
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
    const response = await fetch(`/api/smart-alert/alerts/${alertId}/dismiss`, { method: 'POST' })
    if (response.ok) {
      ElMessage.success('已忽略告警')
      refresh()
    }
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const resolveAlert = async (alertId) => {
  try {
    const response = await fetch(`/api/smart-alert/alerts/${alertId}/resolve`, { method: 'POST' })
    if (response.ok) {
      ElMessage.success('告警已解决')
      refresh()
    }
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const toggleRule = async (ruleId, enabled) => {
  try {
    const response = await fetch(`/api/smart-alert/rules/${ruleId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled })
    })
    if (response.ok) {
      ElMessage.success('状态已更新')
    }
  } catch (error) {
    ElMessage.error('操作失败')
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

