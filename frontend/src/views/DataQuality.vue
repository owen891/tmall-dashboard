<template>
  <div class="data-quality-page">
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-icon><SetUp /></el-icon>
            <span>数据质量监控</span>
          </div>
          <el-button type="primary" @click="loadData">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <div v-loading="loading">
        <el-row :gutter="20" class="kpi-row">
          <el-col :span="6">
            <el-card class="kpi-card">
              <div class="kpi-value primary">{{ overview?.active_products || 0 }}</div>
              <div class="kpi-label">活跃商品</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card class="kpi-card">
              <div class="kpi-value">{{ overview?.weekly_data_count || 0 }}</div>
              <div class="kpi-label">周度数据</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card class="kpi-card">
              <div class="kpi-value success">{{ overview?.coverage_rate || 0 }}%</div>
              <div class="kpi-label">数据覆盖率</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card class="kpi-card">
              <div class="kpi-value warning">{{ missingFields?.length || 0 }}</div>
              <div class="kpi-label">缺失字段</div>
            </el-card>
          </el-col>
        </el-row>

        <el-tabs v-model="activeTab">
          <el-tab-pane label="缺失值检测" name="missing">
            <el-table :data="missingFields" stripe>
              <el-table-column prop="label" label="字段" width="150" />
              <el-table-column prop="total" label="总数" width="100" align="center" />
              <el-table-column prop="null_count" label="空值" width="100" align="center" />
              <el-table-column prop="zero_count" label="零值" width="100" align="center" />
              <el-table-column prop="missing_rate" label="缺失率" width="120">
                <template #default="{ row }">
                  <el-progress 
                    :percentage="row.missing_rate" 
                    :color="getColor(row.missing_rate)"
                    :stroke-width="12"
                  />
                </template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="100" align="center">
                <template #default="{ row }">
                  <el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="异常值检测" name="anomaly">
            <el-table :data="anomalies" stripe>
              <el-table-column prop="title" label="商品" min-width="200" show-overflow-tooltip />
              <el-table-column prop="issues" label="问题" min-width="250">
                <template #default="{ row }">
                  <el-tag 
                    v-for="issue in row.issues" 
                    :key="issue.field"
                    size="small" 
                    type="danger"
                    style="margin-right: 4px"
                  >
                    {{ issue.field }}: {{ issue.issue }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="severity" label="严重程度" width="100" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.severity === 'critical' ? 'danger' : 'warning'">
                    {{ row.severity === 'critical' ? '严重' : '警告' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="数据新鲜度" name="freshness">
            <el-row :gutter="20">
              <el-col :span="8">
                <el-card class="freshness-card">
                  <template #header>
                    <span>周度数据</span>
                  </template>
                  <el-descriptions :column="1" border>
                    <el-descriptions-item label="最新日期">{{ freshness?.weekly?.latest_date }}</el-descriptions-item>
                    <el-descriptions-item label="更新时间">{{ freshness?.weekly?.imported_at }}</el-descriptions-item>
                    <el-descriptions-item label="数据年龄">{{ freshness?.weekly?.age_hours }} 小时</el-descriptions-item>
                    <el-descriptions-item label="状态">
                      <el-tag :type="freshness?.weekly?.status === 'fresh' ? 'success' : 'warning'">
                        {{ freshness?.weekly?.status === 'fresh' ? '最新' : '需更新' }}
                      </el-tag>
                    </el-descriptions-item>
                  </el-descriptions>
                </el-card>
              </el-col>
              <el-col :span="8">
                <el-card class="freshness-card">
                  <template #header>
                    <span>日度数据</span>
                  </template>
                  <el-descriptions :column="1" border>
                    <el-descriptions-item label="最新日期">{{ freshness?.daily?.latest_date }}</el-descriptions-item>
                    <el-descriptions-item label="更新时间">{{ freshness?.daily?.imported_at }}</el-descriptions-item>
                    <el-descriptions-item label="数据年龄">{{ freshness?.daily?.age_hours }} 小时</el-descriptions-item>
                    <el-descriptions-item label="状态">
                      <el-tag :type="freshness?.daily?.status === 'fresh' ? 'success' : 'warning'">
                        {{ freshness?.daily?.status === 'fresh' ? '最新' : '需更新' }}
                      </el-tag>
                    </el-descriptions-item>
                  </el-descriptions>
                </el-card>
              </el-col>
              <el-col :span="8">
                <el-card class="freshness-card">
                  <template #header>
                    <span>月度数据</span>
                  </template>
                  <el-descriptions :column="1" border>
                    <el-descriptions-item label="最新日期">{{ freshness?.monthly?.latest_date }}</el-descriptions-item>
                    <el-descriptions-item label="更新时间">{{ freshness?.monthly?.imported_at }}</el-descriptions-item>
                    <el-descriptions-item label="数据年龄">{{ freshness?.monthly?.age_hours }} 小时</el-descriptions-item>
                    <el-descriptions-item label="状态">
                      <el-tag :type="freshness?.monthly?.status === 'fresh' ? 'success' : 'warning'">
                        {{ freshness?.monthly?.status === 'fresh' ? '最新' : '需更新' }}
                      </el-tag>
                    </el-descriptions-item>
                  </el-descriptions>
                </el-card>
              </el-col>
            </el-row>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

const activeTab = ref('missing')
const loading = ref(false)
const overview = ref(null)
const missingFields = ref([])
const anomalies = ref([])
const freshness = ref(null)

const loadData = async () => {
  loading.value = true
  try {
    const [overviewRes, missingRes, anomalyRes] = await Promise.all([
      api.getDataQualityOverview(),
      api.getMissingValues(),
      api.getDataAnomalies()
    ])
    
    overview.value = overviewRes.data
    missingFields.value = missingRes.data?.fields || []
    anomalies.value = anomalyRes.data?.anomalies || []
    
  } catch (error) {
    console.error('Load data quality error:', error)
    ElMessage.error('加载数据质量信息失败')
  } finally {
    loading.value = false
  }
}

const getColor = (rate) => {
  if (rate > 30) return '#f56c6c'
  if (rate > 10) return '#e6a23c'
  return '#67c23a'
}

const getStatusType = (status) => {
  const types = { critical: 'danger', warning: 'warning', good: 'success' }
  return types[status] || 'info'
}

const getStatusText = (status) => {
  const texts = { critical: '严重', warning: '警告', good: '正常' }
  return texts[status] || status
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.data-quality-page {
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

.kpi-row {
  margin-bottom: 20px;
}

.kpi-card {
  text-align: center;
}

.kpi-value {
  font-size: 28px;
  font-weight: 600;
  margin-bottom: 8px;
}

.kpi-value.primary { color: #409eff; }
.kpi-value.success { color: #67c23a; }
.kpi-value.warning { color: #e6a23c; }

.kpi-label {
  font-size: 14px;
  color: #909399;
}

.freshness-card {
  height: 100%;
}
</style>
