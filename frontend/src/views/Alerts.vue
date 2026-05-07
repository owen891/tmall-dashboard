<template>
  <div class="alerts-container page-container">
    <div class="header">
      <h2>异常告警</h2>
      <div class="controls">
        <el-select v-model="status" @change="loadAlerts" placeholder="状态">
          <el-option label="全部" value="all" />
          <el-option label="未处理" value="unresolved" />
          <el-option label="已处理" value="resolved" />
        </el-select>
        <el-select v-model="severity" @change="loadAlerts" placeholder="级别">
          <el-option label="全部" value="" />
          <el-option label="严重" value="critical" />
          <el-option label="警告" value="warning" />
        </el-select>
        <el-button @click="loadAlerts">刷新</el-button>
      </div>
    </div>

    <el-row :gutter="20" class="stats-cards">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.total_alerts }}</div>
          <div class="stat-label">总告警数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card unresolved">
          <div class="stat-value">{{ stats.unresolved }}</div>
          <div class="stat-label">待处理</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card critical">
          <div class="stat-value">{{ stats.critical }}</div>
          <div class="stat-label">严重</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card warning">
          <div class="stat-value">{{ stats.warning }}</div>
          <div class="stat-label">警告</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="rules-card">
      <template #header>
        <div class="card-header">
          <span>告警规则</span>
          <el-button type="primary" size="small" @click="showAddRule = true">添加规则</el-button>
        </div>
      </template>
      <el-table :data="rules" stripe>
        <el-table-column prop="name" label="规则名称" />
        <el-table-column prop="metric" label="监控指标" />
        <el-table-column prop="condition" label="条件" />
        <el-table-column prop="threshold" label="阈值" />
        <el-table-column prop="severity" label="级别">
          <template #default="{ row }">
            <el-tag :type="row.severity === 'critical' ? 'danger' : 'warning'">
              {{ row.severity === 'critical' ? '严重' : '警告' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="状态">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" @change="toggleRule(row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="danger" size="small" @click="deleteRule(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="alerts-card">
      <template #header>
        <span>告警列表</span>
      </template>
      <el-table :data="alerts" stripe>
        <el-table-column prop="created_at" label="时间" width="160" />
        <el-table-column prop="product_name" label="商品" />
        <el-table-column prop="alert_type" label="类型" />
        <el-table-column prop="metric" label="指标" />
        <el-table-column label="当前值/阈值">
          <template #default="{ row }">
            {{ row.current_value }} / {{ row.threshold }}
          </template>
        </el-table-column>
        <el-table-column prop="message" label="消息" />
        <el-table-column prop="severity" label="级别">
          <template #default="{ row }">
            <el-tag :type="row.severity === 'critical' ? 'danger' : 'warning'">
              {{ row.severity === 'critical' ? '严重' : '警告' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态">
          <template #default="{ row }">
            <el-tag :type="row.status === 'resolved' ? 'success' : 'info'">
              {{ row.status === 'resolved' ? '已处理' : '待处理' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button v-if="row.status === 'unresolved'" size="small" type="primary" @click="resolveAlert(row.id)">处理</el-button>
            <el-button v-else size="small" @click="reopenAlert(row.id)">重开</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showAddRule" title="添加规则" width="400px">
      <el-form :model="ruleForm" label-width="100px">
        <el-form-item label="规则名称">
          <el-input v-model="ruleForm.name" />
        </el-form-item>
        <el-form-item label="监控指标">
          <el-select v-model="ruleForm.metric">
            <el-option label="GMV" value="gmv" />
            <el-option label="ROI" value="roi" />
            <el-option label="转化率" value="conversion" />
            <el-option label="退款率" value="refund_rate" />
            <el-option label="访客" value="visitors" />
          </el-select>
        </el-form-item>
        <el-form-item label="条件">
          <el-select v-model="ruleForm.condition">
            <el-option label="大于" value="gt" />
            <el-option label="小于" value="lt" />
            <el-option label="大于等于" value="gte" />
            <el-option label="小于等于" value="lte" />
          </el-select>
        </el-form-item>
        <el-form-item label="阈值">
          <el-input-number v-model="ruleForm.threshold" :min="0" />
        </el-form-item>
        <el-form-item label="级别">
          <el-select v-model="ruleForm.severity">
            <el-option label="严重" value="critical" />
            <el-option label="警告" value="warning" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddRule = false">取消</el-button>
        <el-button type="primary" @click="addRule">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

const status = ref('all')
const severity = ref('')
const alerts = ref([])
const rules = ref([])
const stats = ref({ total_alerts: 0, unresolved: 0, critical: 0, warning: 0 })
const showAddRule = ref(false)

const ruleForm = ref({
  name: '',
  metric: 'gmv',
  condition: 'lt',
  threshold: 0,
  severity: 'warning'
})

const loadAlerts = async () => {
  try {
    const params = new URLSearchParams()
    if (status.value !== 'all') params.append('status', status.value)
    if (severity.value) params.append('severity', severity.value)

    const res = await api.get(`/alerts?${params.toString()}`)
    if (res.code === 200 || res.data) {
      alerts.value = res.data || res
    }

    const statsRes = await api.get('/alerts/statistics')
    if (statsRes.code === 200 || statsRes.data) {
      stats.value = statsRes.data || statsRes
    }
  } catch (error) {
    console.error('加载告警失败:', error)
  }
}

const loadRules = async () => {
  try {
    const res = await api.get('/alerts/rules')
    if (res.code === 200 || res.data) {
      rules.value = res.data || res
    }
  } catch (error) {
    console.error('加载规则失败:', error)
  }
}

const addRule = async () => {
  try {
    await api.post('/alerts/rules', ruleForm.value)
    ElMessage.success('添加成功')
    showAddRule.value = false
    ruleForm.value = { name: '', metric: 'gmv', condition: 'lt', threshold: 0, severity: 'warning' }
    loadRules()
  } catch (error) {
    ElMessage.error('添加失败')
  }
}

const deleteRule = async (id) => {
  try {
    await api.delete(`/alerts/rules/${id}`)
    ElMessage.success('删除成功')
    loadRules()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

const toggleRule = async (rule) => {
  try {
    await api.put(`/alerts/rules/${rule.id}`, { enabled: rule.enabled })
  } catch (error) {
    ElMessage.error('更新失败')
  }
}

const resolveAlert = async (id) => {
  try {
    await api.put(`/alerts/${id}/resolve`)
    ElMessage.success('已处理')
    loadAlerts()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const reopenAlert = async (id) => {
  try {
    await api.put(`/alerts/${id}/reopen`)
    ElMessage.success('已重新打开')
    loadAlerts()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

onMounted(() => {
  loadAlerts()
  loadRules()
})
</script>

<style scoped>
.alerts-container {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header h2 {
  margin: 0;
}

.controls {
  display: flex;
  gap: 10px;
}

.stats-cards {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
}

.stat-label {
  color: #909399;
  margin-top: 5px;
}

.stat-card.unresolved .stat-value { color: #e6a23c; }
.stat-card.critical .stat-value { color: #f56c6c; }
.stat-card.warning .stat-value { color: #e6a23c; }

.rules-card,
.alerts-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
