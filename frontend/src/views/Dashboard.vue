<template>
  <div class="dashboard">
    <el-row :gutter="20" class="kpi-cards">
      <el-col :span="6" v-for="(kpi, index) in kpiCards" :key="index">
        <el-card class="kpi-card" v-loading="loading">
          <div class="kpi-content">
            <div class="kpi-icon" :style="{ background: kpi.color }">
              <el-icon><component :is="kpi.icon" /></el-icon>
            </div>
            <div class="kpi-info">
              <div class="kpi-value">{{ kpi.value }}</div>
              <div class="kpi-label">{{ kpi.label }}</div>
              <div class="kpi-change" v-if="kpi.change" :class="kpi.changeClass">
                <span v-if="kpi.change > 0">↑</span>
                <span v-else-if="kpi.change < 0">↓</span>
                {{ Math.abs(kpi.change) }}%
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="charts-row">
      <el-col :span="16">
        <el-card v-loading="loading">
          <template #header>
            <div class="card-header">
              <span>GMV 趋势</span>
            </div>
          </template>
          <div ref="trendChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card v-loading="loading">
          <template #header>
            <span>分类销售占比</span>
          </template>
          <div ref="categoryChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card v-loading="loading">
          <template #header>
            <div class="card-header">
              <span>热销商品 TOP10</span>
              <el-button type="primary" text @click="$router.push('/products')">
                查看更多 <el-icon><ArrowRight /></el-icon>
              </el-button>
            </div>
          </template>
          <el-table :data="topProducts" stripe v-loading="loading">
            <el-table-column type="index" label="排名" width="60" />
            <el-table-column prop="product_id" label="商品ID" width="120" />
            <el-table-column prop="title" label="商品名称" min-width="200" />
            <el-table-column prop="tier" label="分层" width="100">
              <template #default="{ row }">
                <el-tag :type="getTierType(row.tier)">{{ row.tier || '未分类' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="net_sales" label="销售额" width="120" align="right">
              <template #default="{ row }">
                ¥{{ formatNumber(row.net_sales) }}
              </template>
            </el-table-column>
            <el-table-column prop="visitors" label="访客数" width="100" align="right">
              <template #default="{ row }">
                {{ formatNumber(row.visitors) }}
              </template>
            </el-table-column>
            <el-table-column prop="conversion" label="转化率" width="100" align="right">
              <template #default="{ row }">
                {{ row.conversion ? (row.conversion * 100).toFixed(2) : 0 }}%
              </template>
            </el-table-column>
            <el-table-column prop="roi" label="ROI" width="80" align="right">
              <template #default="{ row }">
                {{ row.roi || 0 }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import { TrendCharts, User, Money, DataAnalysis, ArrowRight } from '@element-plus/icons-vue'
import api from '@/api'

const loading = ref(true)
const error = ref(null)
const summary = ref({})
const topProducts = ref([])

const kpiCards = reactive([
  { key: 'gmv', label: '总 GMV', icon: 'TrendCharts', color: '#409eff', value: '0', change: 0, changeClass: '' },
  { key: 'visitors', label: '总访客数', icon: 'User', color: '#67c23a', value: '0', change: 0, changeClass: '' },
  { key: 'ad_spend', label: '广告支出', icon: 'Money', color: '#e6a23c', value: '0', change: 0, changeClass: '' },
  { key: 'roi', label: '平均 ROI', icon: 'DataAnalysis', color: '#f56c6c', value: '0', change: 0, changeClass: '' },
])

const trendChartRef = ref(null)
const categoryChartRef = ref(null)
const charts = reactive({ trend: null, category: null })

const formatNumber = (num) => {
  if (!num && num !== 0) return '0'
  num = Number(num)
  if (num >= 10000) {
    return (num / 10000).toFixed(2) + '万'
  }
  return num.toLocaleString()
}

const getTierType = (tier) => {
  const types = { '引流款': 'success', '利润款': 'primary', '潜力款': 'warning' }
  return types[tier] || 'info'
}

const updateKPICards = () => {
  const kpi = summary.value.kpi || {}
  
  kpiCards[0].value = '¥' + formatNumber(kpi.total_gmv?.value)
  kpiCards[0].change = kpi.total_gmv?.change_percent || 0
  kpiCards[0].changeClass = getChangeClass(kpi.total_gmv?.change_percent)
  
  kpiCards[1].value = formatNumber(kpi.visitors?.value)
  kpiCards[1].change = kpi.visitors?.change_percent || 0
  kpiCards[1].changeClass = getChangeClass(kpi.visitors?.change_percent)
  
  kpiCards[2].value = '¥' + formatNumber(kpi.ad_spend?.value)
  kpiCards[2].change = kpi.ad_spend?.change_percent || 0
  kpiCards[2].changeClass = getChangeClass(kpi.ad_spend?.change_percent)
  
  kpiCards[3].value = (kpi.roi?.value || 0).toFixed(2)
  kpiCards[3].change = kpi.roi?.change_percent || 0
  kpiCards[3].changeClass = getChangeClass(kpi.roi?.change_percent)
}

const getChangeClass = (change) => {
  if (!change) return ''
  return change > 0 ? 'text-success' : change < 0 ? 'text-danger' : ''
}

const initCharts = () => {
  if (charts.trend) {
    charts.trend.dispose()
    charts.trend = null
  }
  if (charts.category) {
    charts.category.dispose()
    charts.category = null
  }

  if (trendChartRef.value) {
    charts.trend = echarts.init(trendChartRef.value)
  }
  if (categoryChartRef.value) {
    charts.category = echarts.init(categoryChartRef.value)
  }
}

const updateCharts = () => {
  if (charts.trend) {
    const trends = summary.value.trends || []
    const periods = trends.map(t => t.period || t.date)
    const payments = trends.map(t => t.payment_amount || t.net_sales || 0)
    
    charts.trend.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'category', data: periods },
      yAxis: { type: 'value', name: '金额' },
      series: [{
        name: '销售额',
        type: 'line',
        data: payments,
        smooth: true,
        areaStyle: { opacity: 0.3 },
        itemStyle: { color: '#409eff' }
      }]
    })
  }

  if (charts.category) {
    const categoryData = summary.value.category_distribution || []
    
    charts.category.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
      legend: { bottom: 0 },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        label: { show: true, formatter: '{b}\n{d}%' },
        data: categoryData
      }]
    })
  }
}

const loadData = async () => {
  loading.value = true
  error.value = null
  
  try {
    const [summaryRes, topRes] = await Promise.all([
      api.getKPI({ dim: 'weekly' }),
      api.getTopProducts({ dimension: 'weekly', limit: 10 })
    ])
    
    summary.value = summaryRes.data || {}
    topProducts.value = (topRes.data?.products || []).map(p => ({
      product_id: p.product_id,
      title: p.product_name || p.title,
      image_url: p.image_url,
      tier: p.tier || '',
      net_sales: p.value || p.payment_amount || 0,
      visitors: p.visitors || 0,
      conversion: p.conversion || 0,
      roi: p.roi || 0
    }))
    
    updateKPICards()
    
    await nextTick()
    initCharts()
    updateCharts()
  } catch (err) {
    console.error('Load data error:', err)
    error.value = err.message || '加载数据失败'
  } finally {
    loading.value = false
  }
}

const handleResize = () => {
  if (charts.trend) charts.trend.resize()
  if (charts.category) charts.category.resize()
}

onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (charts.trend) {
    charts.trend.dispose()
    charts.trend = null
  }
  if (charts.category) {
    charts.category.dispose()
    charts.category = null
  }
})
</script>

<style scoped>
.dashboard {
  padding: 20px;
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

.kpi-change {
  font-size: 12px;
  margin-top: 4px;
}

.text-success {
  color: #67c23a;
}

.text-danger {
  color: #f56c6c;
}

.charts-row {
  margin-bottom: 20px;
}

.chart-container {
  height: 300px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
