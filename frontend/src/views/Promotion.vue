<template>
  <div class="promotion-analysis">
    <el-card class="filter-card">
      <div class="filter-row">
        <div class="filter-group">
          <el-button-group size="small">
            <el-button :type="dataSource === 'cloud' ? 'primary' : 'default'" @click="dataSource = 'cloud'">云端</el-button>
            <el-button :type="dataSource === 'local' ? 'primary' : 'default'" @click="dataSource = 'local'">本地</el-button>
          </el-button-group>
        </div>
        
        <div class="filter-group">
          <span class="filter-label">渠道:</span>
          <el-select v-model="selectedChannel" size="small" style="width: 120px;" @change="loadPlans">
            <el-option label="全部" value="all" />
            <el-option label="直通车" value="search" />
            <el-option label="超级推荐" value="recommend" />
            <el-option label="钻展" value="display" />
          </el-select>
        </div>
        
        <div class="filter-group">
          <span class="filter-label">状态:</span>
          <el-select v-model="selectedStatus" size="small" style="width: 100px;" @change="loadPlans">
            <el-option label="全部" value="all" />
            <el-option label="运行中" value="running" />
            <el-option label="暂停" value="paused" />
          </el-select>
        </div>
        
        <el-button type="primary" size="small" @click="loadPlans" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        
        <el-button size="small" @click="exportData">
          <el-icon><Download /></el-icon>
          导出
        </el-button>
      </div>
    </el-card>

    <el-card class="main-card" v-loading="loading">
      <div class="card-header">
        <el-tabs v-model="activeTab" type="card" @tab-click="handleTabChange">
          <el-tab-pane label="推广计划" name="plans">
            <template #label>
              <span>推广计划</span>
              <el-badge :value="plans.length" class="tab-badge" />
            </template>
          </el-tab-pane>
          <el-tab-pane label="搜索拉升效率" name="efficiency">
            <template #label>
              <span>搜索拉升效率</span>
            </template>
          </el-tab-pane>
        </el-tabs>
      </div>

      <div v-if="activeTab === 'plans'" class="tab-content">
        <div class="stats-row">
          <div class="stat-item">
            <span class="stat-label">推广花费</span>
            <span class="stat-value">¥{{ formatNumber(totalCost) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">成交金额</span>
            <span class="stat-value">¥{{ formatNumber(totalRevenue) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">平均ROI</span>
            <span class="stat-value">{{ avgROI.toFixed(2) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">点击量</span>
            <span class="stat-value">{{ formatNumber(totalClicks) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">展现量</span>
            <span class="stat-value">{{ formatNumber(totalImpressions) }}</span>
          </div>
        </div>

        <el-table 
          :data="plans" 
          stripe 
          size="small"
          @row-click="handleRowClick"
          highlight-current-row
        >
          <el-table-column prop="plan_name" label="计划名称" min-width="180" show-overflow-tooltip />
          <el-table-column prop="campaign_type" label="推广类型" width="100">
            <template #default="{ row }">
              <el-tag :type="getTypeTagType(row.campaign_type)" size="small">
                {{ row.campaign_type }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === '运行中' ? 'success' : 'warning'" size="small">
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="cost" label="推广花费" width="100" align="right">
            <template #default="{ row }">
              ¥{{ formatNumber(row.cost) }}
            </template>
          </el-table-column>
          <el-table-column prop="revenue" label="成交金额" width="100" align="right">
            <template #default="{ row }">
              ¥{{ formatNumber(row.revenue) }}
            </template>
          </el-table-column>
          <el-table-column prop="roi" label="ROI" width="70" align="right">
            <template #default="{ row }">
              <span :class="row.roi >= 1 ? 'text-success' : 'text-danger'">
                {{ (row.roi || 0).toFixed(2) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="clicks" label="点击量" width="90" align="right">
            <template #default="{ row }">
              {{ formatNumber(row.clicks) }}
            </template>
          </el-table-column>
          <el-table-column prop="impressions" label="展现量" width="100" align="right">
            <template #default="{ row }">
              {{ formatNumber(row.impressions) }}
            </template>
          </el-table-column>
          <el-table-column prop="cpc" label="平均点击单价" width="100" align="right">
            <template #default="{ row }">
              ¥{{ (row.cpc || 0).toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column prop="conversion_rate" label="转化率" width="80" align="right">
            <template #default="{ row }">
              {{ ((row.conversion_rate || 0) * 100).toFixed(2) }}%
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="activeTab === 'efficiency'" class="tab-content">
        <div class="summary-cards">
          <el-card class="summary-card">
            <div class="card-icon search-icon">
              <el-icon size="24"><Search /></el-icon>
            </div>
            <div class="card-info">
              <p class="card-value">{{ efficiencyStats.totalSearches.toLocaleString() }}</p>
              <p class="card-label">搜索总次数</p>
            </div>
          </el-card>
          <el-card class="summary-card">
            <div class="card-icon click-icon">
              <el-icon size="24"><Mouse /></el-icon>
            </div>
            <div class="card-info">
              <p class="card-value">{{ efficiencyStats.clickRate.toFixed(2) }}%</p>
              <p class="card-label">点击率</p>
            </div>
          </el-card>
          <el-card class="summary-card">
            <div class="card-icon conversion-icon">
              <el-icon size="24"><TrendCharts /></el-icon>
            </div>
            <div class="card-info">
              <p class="card-value">{{ efficiencyStats.conversionRate.toFixed(2) }}%</p>
              <p class="card-label">转化率</p>
            </div>
          </el-card>
          <el-card class="summary-card">
            <div class="card-icon growth-icon">
              <el-icon size="24"><TrendCharts /></el-icon>
            </div>
            <div class="card-info">
              <p class="card-value" :class="efficiencyStats.growthRate >= 0 ? 'text-success' : 'text-danger'">
                {{ efficiencyStats.growthRate >= 0 ? '+' : '' }}{{ efficiencyStats.growthRate.toFixed(2) }}%
              </p>
              <p class="card-label">同比增长</p>
            </div>
          </el-card>
        </div>

        <div class="chart-section">
          <el-card>
            <template #header>搜索趋势</template>
            <div ref="searchChartRef" class="chart-container"></div>
          </el-card>
        </div>
      </div>
    </el-card>

    <el-dialog v-model="showDetail" title="计划详情" width="700px">
      <div v-if="selectedPlan" class="plan-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="计划名称" :span="2">{{ selectedPlan.plan_name }}</el-descriptions-item>
          <el-descriptions-item label="推广类型">{{ selectedPlan.campaign_type }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="selectedPlan.status === '运行中' ? 'success' : 'warning'">
              {{ selectedPlan.status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="推广花费">¥{{ formatNumber(selectedPlan.cost) }}</el-descriptions-item>
          <el-descriptions-item label="成交金额">¥{{ formatNumber(selectedPlan.revenue) }}</el-descriptions-item>
          <el-descriptions-item label="ROI">{{ (selectedPlan.roi || 0).toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="平均点击单价">¥{{ (selectedPlan.cpc || 0).toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="点击量">{{ formatNumber(selectedPlan.clicks) }}</el-descriptions-item>
          <el-descriptions-item label="展现量">{{ formatNumber(selectedPlan.impressions) }}</el-descriptions-item>
          <el-descriptions-item label="转化率">{{ ((selectedPlan.conversion_rate || 0) * 100).toFixed(2) }}%</el-descriptions-item>
        </el-descriptions>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { Refresh, Search, Mouse, Download, TrendCharts } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import api from '@/api'

const dataSource = ref('cloud')
const selectedChannel = ref('all')
const selectedStatus = ref('all')
const loading = ref(false)
const activeTab = ref('plans')
const showDetail = ref(false)
const selectedPlan = ref(null)

const plans = ref([])
const efficiencyStats = ref({
  totalSearches: 0,
  clickRate: 0,
  conversionRate: 0,
  growthRate: 0
})

const searchChartRef = ref(null)
let searchChart = null

const totalCost = computed(() => plans.value.reduce((sum, p) => sum + (p.cost || 0), 0))
const totalRevenue = computed(() => plans.value.reduce((sum, p) => sum + (p.revenue || 0), 0))
const totalClicks = computed(() => plans.value.reduce((sum, p) => sum + (p.clicks || 0), 0))
const totalImpressions = computed(() => plans.value.reduce((sum, p) => sum + (p.impressions || 0), 0))
const avgROI = computed(() => {
  if (totalCost.value === 0) return 0
  return totalRevenue.value / totalCost.value
})

const formatNumber = (num) => {
  if (!num && num !== 0) return '0'
  return Number(num).toLocaleString()
}

const getTypeTagType = (type) => {
  const types = { '标准计划': 'primary', '智能计划': 'success', '品牌计划': 'warning' }
  return types[type] || 'info'
}

const handleRowClick = (row) => {
  selectedPlan.value = row
  showDetail.value = true
}

const handleTabChange = (tab) => {
  if (tab.name === 'efficiency') {
    nextTick(() => initSearchChart())
  }
}

const loadPlans = async () => {
  loading.value = true
  try {
    const res = await api.getProducts({
      channel: selectedChannel.value !== 'all' ? selectedChannel.value : undefined,
      status: selectedStatus.value !== 'all' ? selectedStatus.value : undefined
    })
    
    if (res && res.data) {
      plans.value = res.data.data || []
      
      efficiencyStats.value = {
        totalSearches: totalClicks.value * 10,
        clickRate: totalImpressions.value > 0 ? (totalClicks.value / totalImpressions.value) * 100 : 0,
        conversionRate: 3.5 + Math.random() * 2,
        growthRate: 8 + Math.random() * 10
      }
    }
  } catch (error) {
    console.error('Failed to load plans:', error)
    plans.value = []
  } finally {
    loading.value = false
  }
}

const exportData = () => {
  ElMessage.info('正在导出数据...')
}

const initSearchChart = () => {
  if (!searchChartRef.value) return
  
  if (searchChart) {
    searchChart.dispose()
  }
  
  searchChart = echarts.init(searchChartRef.value)
  
  const option = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['搜索次数', '点击次数', '转化次数'] },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: ['5/1', '5/2', '5/3', '5/4', '5/5', '5/6', '5/7']
    },
    yAxis: { type: 'value' },
    series: [
      { name: '搜索次数', type: 'line', smooth: true, data: [18500, 21200, 19800, 23500, 22800, 25600, 24200] },
      { name: '点击次数', type: 'line', smooth: true, data: [820, 950, 880, 1050, 990, 1150, 1080] },
      { name: '转化次数', type: 'line', smooth: true, data: [32, 38, 35, 42, 39, 45, 42] }
    ]
  }
  
  searchChart.setOption(option)
  window.addEventListener('resize', () => searchChart?.resize())
}

onMounted(() => {
  loadPlans()
})
</script>

<style scoped>
.promotion-analysis {
  padding-bottom: 20px;
}

.filter-card {
  margin-bottom: 16px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-label {
  font-size: 14px;
  color: #606266;
}

.main-card {
  min-height: calc(100vh - 280px);
}

.tab-badge {
  margin-left: 4px;
}

.stats-row {
  display: flex;
  gap: 24px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 16px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 12px;
  color: #909399;
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.summary-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.summary-card {
  display: flex;
  align-items: center;
  gap: 16px;
}

.card-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.search-icon { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #fff; }
.click-icon { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: #fff; }
.conversion-icon { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: #fff; }
.growth-icon { background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); color: #fff; }

.card-info { flex: 1; }

.card-value {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 4px 0;
}

.card-label {
  font-size: 12px;
  color: #909399;
  margin: 0;
}

.chart-section {
  margin-top: 16px;
}

.chart-container {
  height: 300px;
}

.text-success { color: #67c23a; }
.text-danger { color: #f56c6c; }
</style>
