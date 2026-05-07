<template>
  <div class="page-container profit-page">
    <div class="header">
      <h2>利润分析</h2>
      <div class="controls">
        <el-select v-model="dimension" @change="loadData" style="width: 120px">
          <el-option label="按日" value="daily" />
          <el-option label="按周" value="weekly" />
          <el-option label="按月" value="monthly" />
        </el-select>
      </div>
    </div>

    <el-card class="rates-card">
      <template #header>
        <span>费用参数设置</span>
      </template>
      <el-form inline>
        <el-form-item label="成本系数">
          <el-input-number v-model="costRate" :min="0" :max="1" :step="0.05" @change="loadData" />
        </el-form-item>
        <el-form-item label="佣金系数">
          <el-input-number v-model="commissionRate" :min="0" :max="1" :step="0.01" @change="loadData" />
        </el-form-item>
        <el-form-item label="运费系数">
          <el-input-number v-model="freightRate" :min="0" :max="1" :step="0.01" @change="loadData" />
        </el-form-item>
      </el-form>
    </el-card>

    <el-row :gutter="20" class="kpi-cards" v-loading="loading">
      <el-col :span="6">
        <el-card class="kpi-card">
          <div class="kpi-content">
            <div class="kpi-icon" style="background: #409eff">
              <el-icon><TrendCharts /></el-icon>
            </div>
            <div class="kpi-info">
              <div class="kpi-value">¥{{ formatNumber(summary.payment) }}</div>
              <div class="kpi-label">销售额</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="kpi-card">
          <div class="kpi-content">
            <div class="kpi-icon" style="background: #67c23a">
              <el-icon><Money /></el-icon>
            </div>
            <div class="kpi-info">
              <div class="kpi-value" :class="getProfitClass(summary.metrics?.gross_profit)">
                ¥{{ formatNumber(summary.metrics?.gross_profit) }}
              </div>
              <div class="kpi-label">毛利</div>
              <div class="kpi-sub">{{ summary.metrics?.gross_margin || 0 }}%</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="kpi-card">
          <div class="kpi-content">
            <div class="kpi-icon" style="background: #e6a23c">
              <el-icon><Wallet /></el-icon>
            </div>
            <div class="kpi-info">
              <div class="kpi-value" :class="getProfitClass(summary.metrics?.net_profit)">
                ¥{{ formatNumber(summary.metrics?.net_profit) }}
              </div>
              <div class="kpi-label">净利</div>
              <div class="kpi-sub">{{ summary.metrics?.net_margin || 0 }}%</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="kpi-card">
          <div class="kpi-content">
            <div class="kpi-icon" style="background: #f56c6c">
              <el-icon><DataLine /></el-icon>
            </div>
            <div class="kpi-info">
              <div class="kpi-value">{{ summary.metrics?.roi || 0 }}%</div>
              <div class="kpi-label">广告 ROI</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="charts-row">
      <el-col :span="12">
        <el-card v-loading="loading">
          <template #header>
            <span>利润趋势</span>
          </template>
          <div ref="trendChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card v-loading="loading">
          <template #header>
            <span>分层利润分布</span>
          </template>
          <div ref="tierChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-card v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>商品利润排行 TOP50</span>
          <ExportButton :data="productProfits" :columns="exportColumns" filename="利润排行" />
        </div>
      </template>
      <el-table :data="productProfits" stripe empty-text="暂无利润数据">
        <el-table-column prop="product_id" label="商品ID" width="120" />
        <el-table-column prop="title" label="商品名称" min-width="200" />
        <el-table-column prop="tier" label="分层" width="100">
          <template #default="{ row }">
            <el-tag :type="getTierType(row.tier)">{{ row.tier }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="payment" label="销售额" width="120" align="right">
          <template #default="{ row }">
            ¥{{ formatNumber(row.payment) }}
          </template>
        </el-table-column>
        <el-table-column prop="metrics.gross_profit" label="毛利" width="120" align="right">
          <template #default="{ row }">
            <span :class="getProfitClass(row.metrics?.gross_profit)">
              ¥{{ formatNumber(row.metrics?.gross_profit) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="metrics.net_profit" label="净利" width="120" align="right">
          <template #default="{ row }">
            <span :class="getProfitClass(row.metrics?.net_profit)">
              ¥{{ formatNumber(row.metrics?.net_profit) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="metrics.gross_margin" label="毛利率" width="100" align="right">
          <template #default="{ row }">
            {{ row.metrics?.gross_margin || 0 }}%
          </template>
        </el-table-column>
        <el-table-column prop="metrics.net_margin" label="净利率" width="100" align="right">
          <template #default="{ row }">
            {{ row.metrics?.net_margin || 0 }}%
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import api from '@/api'
import { useChartManager } from '@/composables/useChartManager'
import ExportButton from '@/components/ExportButton.vue'
import { TrendCharts, Money, Wallet, DataLine } from '@element-plus/icons-vue'
import { formatNumber, getTierType } from '@/utils/format'

const dimension = ref('weekly')
const loading = ref(true)
const summary = ref({})
const productProfits = ref([])
const trends = ref([])
const tierData = ref([])
const trendChartRef = ref(null)
const tierChartRef = ref(null)
const chartManager = useChartManager()

const costRate = ref(0.5)
const commissionRate = ref(0.06)
const freightRate = ref(0.02)

const exportColumns = [
  { key: 'product_id', label: '商品ID' },
  { key: 'title', label: '商品名称' },
  { key: 'tier', label: '分层' },
  { key: 'payment', label: '销售额' },
  { key: 'gross_profit', label: '毛利' },
  { key: 'net_profit', label: '净利' },
  { key: 'gross_margin', label: '毛利率' },
  { key: 'net_margin', label: '净利率' },
]

const getProfitClass = (value) => {
  if (!value) return ''
  return value >= 0 ? 'text-success' : 'text-danger'
}

const loadData = async () => {
  loading.value = true
  try {
    const params = {
      dimension: dimension.value,
      cost_rate: costRate.value,
      commission_rate: commissionRate.value,
      freight_rate: freightRate.value
    }

    const [summaryRes, productsRes, trendsRes, tierRes] = await Promise.all([
      api.getProfitSummary(params),
      api.getProductProfits({ ...params, limit: 50 }),
      api.getProfitTrends(params),
      api.getProfitByTier(params)
    ])

    summary.value = summaryRes.data || {}
    productProfits.value = productsRes.data?.products || []
    trends.value = trendsRes.data?.trends || []
    tierData.value = tierRes.data?.tiers || []

    nextTick(() => {
      initTrendChart()
      initTierChart()
    })
  } catch (error) {
    console.error('Load data error:', error)
    const errorMsg = error.response?.data?.detail || error.message || '网络错误'
    ElMessage.error(`加载利润数据失败: ${errorMsg}`)
    summary.value = {}
    productProfits.value = []
    trends.value = []
    tierData.value = []
  } finally {
    loading.value = false
  }
}

const initTrendChart = () => {
  if (trends.value.length === 0) {
    chartManager.showEmpty(trendChartRef, '暂无趋势数据')
    return
  }

  const periods = trends.value.map(t => t.period || '')
  const grossProfits = trends.value.map(t => t.metrics?.gross_profit || 0)
  const netProfits = trends.value.map(t => t.metrics?.net_profit || 0)

  chartManager.setOption(trendChartRef, {
    tooltip: { trigger: 'axis' },
    legend: { data: ['毛利', '净利'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
    xAxis: { type: 'category', data: periods },
    yAxis: { type: 'value', name: '金额(元)' },
    series: [
      { name: '毛利', type: 'bar', data: grossProfits, itemStyle: { color: '#67c23a' } },
      { name: '净利', type: 'bar', data: netProfits, itemStyle: { color: '#e6a23c' } }
    ]
  })
}

const initTierChart = () => {
  if (tierData.value.length === 0) {
    chartManager.showEmpty(tierChartRef, '暂无分层数据')
    return
  }

  const tiers = tierData.value.map(t => t.tier || '未知')
  const profits = tierData.value.map(t => t.metrics?.net_profit || 0)

  chartManager.setOption(tierChartRef, {
    tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      label: { show: true, formatter: '{b}\n¥{c}' },
      data: tiers.map((t, i) => ({ value: profits[i], name: t }))
    }]
  })
}

onMounted(() => {
  chartManager.initChart(trendChartRef)
  chartManager.initChart(tierChartRef)
  loadData()
  chartManager.setupResize()
})
</script>

<style scoped>
.profit-page {
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

.rates-card {
  margin-bottom: 20px;
}

.kpi-cards {
  margin-bottom: 20px;
}

.kpi-card {
  cursor: default;
}

.kpi-content {
  display: flex;
  align-items: center;
  gap: 15px;
}

.kpi-icon {
  width: 50px;
  height: 50px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 24px;
}

.kpi-info {
  flex: 1;
}

.kpi-value {
  font-size: 20px;
  font-weight: bold;
  color: #303133;
}

.kpi-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.kpi-sub {
  font-size: 12px;
  color: #c0c4cc;
}

.charts-row {
  margin-bottom: 20px;
}

.chart-container {
  height: 300px;
}

.text-success {
  color: #67c23a;
}

.text-danger {
  color: #f56c6c;
}
</style>
