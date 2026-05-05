<template>
  <div class="pace-monitor">
    <div class="header">
      <h2>Pace 监控</h2>
      <div class="controls">
        <el-select v-model="dimension" @change="loadData" style="width: 120px">
          <el-option label="按周" value="weekly" />
          <el-option label="按月" value="monthly" />
          <el-option label="按年" value="yearly" />
        </el-select>
      </div>
    </div>

    <el-row :gutter="20" class="pace-cards" v-loading="loading">
      <el-col :span="8">
        <el-card class="pace-card">
          <template #header>
            <span>时间进度</span>
          </template>
          <div class="pace-content">
            <el-progress 
              :percentage="timeProgress.progress" 
              :stroke-width="20"
              :color="'#409EFF'"
            />
            <div class="pace-info">
              <div class="pace-value">{{ timeProgress.progress }}%</div>
              <div class="pace-label">
                已过 {{ timeProgress.elapsed_days || '-' }} / {{ timeProgress.total_days || '-' }} 天
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="pace-card" :class="paceStatus.level">
          <template #header>
            <span>销售进度</span>
          </template>
          <div class="pace-content">
            <el-progress 
              :percentage="salesProgress.progress" 
              :stroke-width="20"
              :color="getProgressColor(paceStatus.level)"
            />
            <div class="pace-info">
              <div class="pace-value">¥{{ formatNumber(salesProgress.current) }}</div>
              <div class="pace-label">目标 ¥{{ formatNumber(salesProgress.target) }}</div>
              <div class="pace-gap" :class="paceStatus.level">
                {{ paceStatus.gap > 0 ? '+' : '' }}{{ paceStatus.gap }}% vs 时间进度
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="pace-card" v-if="budgetPace" :class="budgetPace.level">
          <template #header>
            <span>预算消耗</span>
          </template>
          <div class="pace-content">
            <el-progress 
              :percentage="budgetPace.progress" 
              :stroke-width="20"
              :color="getProgressColor(budgetPace.level)"
            />
            <div class="pace-info">
              <div class="pace-value">¥{{ formatNumber(budgetPace.current) }}</div>
              <div class="pace-label">预算 ¥{{ formatNumber(budgetPace.target) }}</div>
              <div class="pace-gap" :class="budgetPace.level">
                {{ budgetPace.gap > 0 ? '+' : '' }}{{ budgetPace.gap }}% vs 时间进度
              </div>
            </div>
          </div>
        </el-card>
        <el-card v-else>
          <el-empty description="未设置预算目标" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="16">
        <el-card v-loading="loading">
          <template #header>
            <div class="card-header">
              <span>Pace 状态</span>
              <el-tag :type="getTagType(paceStatus.level)" size="large">
                {{ paceStatus.message }}
              </el-tag>
            </div>
          </template>
          <div class="status-content">
            <div class="status-item">
              <span class="label">当前状态</span>
              <span class="value" :class="paceStatus.level">{{ getStatusText(paceStatus.status) }}</span>
            </div>
            <div class="status-item">
              <span class="label">差距</span>
              <span class="value">{{ paceStatus.gap }}%</span>
            </div>
            <div class="status-item">
              <span class="label">距离目标</span>
              <span class="value">¥{{ formatNumber(salesProgress.gap_to_target) }}</span>
            </div>
            <div class="status-item">
              <span class="label">日均需完成</span>
              <span class="value">¥{{ formatNumber(salesProgress.daily_needed) }}</span>
            </div>
          </div>
          
          <el-divider />
          
          <div class="alerts-section" v-if="alerts.length">
            <h4>预警提示</h4>
            <el-alert
              v-for="(alert, index) in alerts"
              :key="index"
              :title="alert.message"
              :type="alert.level"
              show-icon
              style="margin-bottom: 10px"
            />
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card v-loading="forecastLoading">
          <template #header>
            <span>达成预测</span>
          </template>
          <div class="forecast-content" v-if="forecast">
            <el-progress 
              type="dashboard"
              :percentage="forecast.achievement_rate"
              :color="getProgressColor(forecast.forecast_level)"
            />
            <div class="forecast-info">
              <div class="forecast-item">
                <span class="label">当前 GMV</span>
                <span class="value">¥{{ formatNumber(forecast.current_gmv) }}</span>
              </div>
              <div class="forecast-item">
                <span class="label">预测 GMV</span>
                <span class="value">¥{{ formatNumber(forecast.projected_gmv) }}</span>
              </div>
              <div class="forecast-item">
                <span class="label">目标 GMV</span>
                <span class="value">¥{{ formatNumber(forecast.target_gmv) }}</span>
              </div>
            </div>
            <el-tag :type="getTagType(forecast.forecast_level)" style="margin-top: 15px">
              {{ forecast.forecast_message }}
            </el-tag>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 20px" v-loading="productLoading">
      <template #header>
        <div class="card-header">
          <span>商品 Pace 排行</span>
          <el-tag>按进度差距排序</el-tag>
        </div>
      </template>
      <el-table :data="productPaces" stripe>
        <el-table-column prop="product_id" label="商品ID" width="120" />
        <el-table-column prop="title" label="商品名称" min-width="200" />
        <el-table-column prop="tier" label="分层" width="100">
          <template #default="{ row }">
            <el-tag :type="getTierType(row.tier)">{{ row.tier || '未分类' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="目标 GMV" width="120" align="right">
          <template #default="{ row }">
            ¥{{ formatNumber(row.target_gmv) }}
          </template>
        </el-table-column>
        <el-table-column label="当前 GMV" width="120" align="right">
          <template #default="{ row }">
            ¥{{ formatNumber(row.current_gmv) }}
          </template>
        </el-table-column>
        <el-table-column label="进度" width="100" align="center">
          <template #default="{ row }">
            <el-progress 
              :percentage="Math.min(100, row.progress)" 
              :color="getProgressColor(row.level)"
              :stroke-width="10"
            />
          </template>
        </el-table-column>
        <el-table-column label="差距" width="100" align="center">
          <template #default="{ row }">
            <span :class="row.level">{{ row.gap > 0 ? '+' : '' }}{{ row.gap }}%</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getTagType(row.level)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/api'
import { formatNumber, getTierType } from '@/utils/format'

const dimension = ref('monthly')
const loading = ref(true)
const forecastLoading = ref(false)
const productLoading = ref(false)

const timeProgress = ref({})
const salesProgress = ref({})
const budgetPace = ref(null)
const paceStatus = ref({})
const alerts = ref([])
const forecast = ref(null)
const productPaces = ref([])

const getProgressColor = (level) => {
  const colors = {
    'success': '#67C23A',
    'info': '#409EFF',
    'warning': '#E6A23C',
    'danger': '#F56C6C'
  }
  return colors[level] || '#409EFF'
}

const getTagType = (level) => {
  const types = {
    'success': 'success',
    'info': 'info',
    'warning': 'warning',
    'danger': 'danger'
  }
  return types[level] || 'info'
}

const getStatusText = (status) => {
  const texts = {
    'ahead': '领先',
    'on_track': '正常',
    'behind': '落后',
    'critical': '严重落后',
    'no_target': '未设置目标'
  }
  return texts[status] || status
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await api.request.get(`/pace/overview?dimension=${dimension.value}`)
    const data = res.data || {}
    
    timeProgress.value = data.time_progress || {}
    salesProgress.value = data.sales_progress || {}
    budgetPace.value = data.budget_pace
    paceStatus.value = data.pace_status || {}
    alerts.value = data.alerts || []
    
    loadForecast()
    loadProducts()
  } catch (error) {
    console.error('Load pace data error:', error)
  } finally {
    loading.value = false
  }
}

const loadForecast = async () => {
  forecastLoading.value = true
  try {
    const res = await api.request.get(`/pace/forecast?dimension=${dimension.value}`)
    forecast.value = res.data
  } catch (error) {
    console.error('Load forecast error:', error)
  } finally {
    forecastLoading.value = false
  }
}

const loadProducts = async () => {
  productLoading.value = true
  try {
    const res = await api.request.get(`/pace/products?dimension=${dimension.value}`)
    productPaces.value = res.data?.products || []
  } catch (error) {
    console.error('Load products error:', error)
  } finally {
    productLoading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.pace-monitor {
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

.pace-cards {
  margin-bottom: 20px;
}

.pace-card {
  cursor: default;
}

.pace-card.success {
  border-left: 4px solid #67C23A;
}

.pace-card.warning {
  border-left: 4px solid #E6A23C;
}

.pace-card.danger {
  border-left: 4px solid #F56C6C;
}

.pace-content {
  padding: 10px 0;
}

.pace-info {
  margin-top: 15px;
  text-align: center;
}

.pace-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.pace-label {
  font-size: 14px;
  color: #909399;
  margin-top: 5px;
}

.pace-gap {
  font-size: 14px;
  font-weight: bold;
  margin-top: 10px;
}

.pace-gap.success {
  color: #67C23A;
}

.pace-gap.warning {
  color: #E6A23C;
}

.pace-gap.danger {
  color: #F56C6C;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status-content {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.status-item {
  text-align: center;
}

.status-item .label {
  display: block;
  font-size: 14px;
  color: #909399;
  margin-bottom: 8px;
}

.status-item .value {
  font-size: 20px;
  font-weight: bold;
  color: #303133;
}

.status-item .value.success {
  color: #67C23A;
}

.status-item .value.warning {
  color: #E6A23C;
}

.status-item .value.danger {
  color: #F56C6C;
}

.alerts-section h4 {
  margin: 0 0 15px 0;
  color: #303133;
}

.forecast-content {
  text-align: center;
}

.forecast-info {
  margin-top: 20px;
}

.forecast-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #EBEEF5;
}

.forecast-item .label {
  color: #909399;
}

.forecast-item .value {
  font-weight: bold;
}

.text-success {
  color: #67C23A;
}

.text-warning {
  color: #E6A23C;
}

.text-danger {
  color: #F56C6C;
}
</style>
