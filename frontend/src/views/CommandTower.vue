<template>
  <div class="page-container command-tower-page">
    <div class="tower-header">
      <div class="header-left">
        <h1>🎯 运营指挥塔</h1>
        <span class="subtitle">电商运营核心工作台</span>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="refresh">
          <el-icon><Refresh /></el-icon>
          刷新数据
        </el-button>
      </div>
    </div>

    <CoreIndicators :indicators="coreIndicators" />

    <AlertBar :alerts="alerts" />

    <div class="quick-access">
      <h3 class="section-title">快捷入口</h3>
      <div class="quick-grid">
        <router-link to="/products" class="quick-card">
          <div class="quick-icon" style="background: #e8f5e9; color: #4caf50;">
            <el-icon size="28"><Goods /></el-icon>
          </div>
          <div class="quick-info">
            <span class="quick-name">商品列表</span>
            <span class="quick-desc">查看所有商品数据</span>
          </div>
        </router-link>

        <router-link to="/lifecycle" class="quick-card">
          <div class="quick-icon" style="background: #fff3e0; color: #ff9800;">
            <el-icon size="28"><Odometer /></el-icon>
          </div>
          <div class="quick-info">
            <span class="quick-name">生命周期</span>
            <span class="quick-desc">管理商品生命周期</span>
          </div>
        </router-link>

        <router-link to="/profit" class="quick-card">
          <div class="quick-icon" style="background: #e3f2fd; color: #2196f3;">
            <el-icon size="28"><DataLine /></el-icon>
          </div>
          <div class="quick-info">
            <span class="quick-name">利润分析</span>
            <span class="quick-desc">查看利润报表</span>
          </div>
        </router-link>

        <router-link to="/ads" class="quick-card">
          <div class="quick-icon" style="background: #fce4ec; color: #e91e63;">
            <el-icon size="28"><TrendCharts /></el-icon>
          </div>
          <div class="quick-info">
            <span class="quick-name">广告投放</span>
            <span class="quick-desc">管理广告数据</span>
          </div>
        </router-link>
      </div>
    </div>

    <div class="bottom-section">
      <el-row :gutter="20">
        <el-col :span="16">
          <div class="chart-card">
            <div class="chart-header">
              <h3>📊 GMV趋势</h3>
              <el-radio-group v-model="trendPeriod" size="small">
                <el-radio-button value="daily">今日</el-radio-button>
                <el-radio-button value="weekly">本周</el-radio-button>
                <el-radio-button value="monthly">本月</el-radio-button>
              </el-radio-group>
            </div>
            <div ref="trendChartRef" class="chart-container"></div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="chart-card">
            <div class="chart-header">
              <h3> 目标完成情况</h3>
            </div>
            <div ref="gaugeChartRef" class="chart-container"></div>
          </div>
        </el-col>
      </el-row>

      <el-row :gutter="20" style="margin-top: 20px">
        <el-col :span="24">
          <div class="chart-card">
            <div class="chart-header">
              <h3> 热销TOP10</h3>
              <el-button type="primary" text @click="$router.push('/products')">
                查看全部
              </el-button>
            </div>
            <el-table :data="topProducts" stripe>
              <el-table-column type="index" label="排名" width="60" align="center" />
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
              <el-table-column label="操作" width="100">
                <template #default="{ row }">
                  <el-button size="small" text @click="viewProduct(row)">查看</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { Refresh } from '@element-plus/icons-vue'
import CoreIndicators from '@/components/tower/CoreIndicators.vue'
import AlertBar from '@/components/tower/AlertBar.vue'
import HexagonCard from '@/components/tower/HexagonCard.vue'
import api from '@/api'
import { formatNumber, formatCurrency, getTierType } from '@/utils/format'

const router = useRouter()
const trendPeriod = ref('daily')
const trendChartRef = ref(null)
const gaugeChartRef = ref(null)
const charts = reactive({ trend: null, gauge: null })
const loading = ref(false)

const coreIndicators = ref([
  { label: 'GMV', value: '--', change: 0, color: '#409eff', icon: 'DataLine' },
  { label: '访客数', value: '--', change: 0, color: '#67c23a', icon: 'User' },
  { label: 'ROI', value: '--', change: 0, color: '#e6a23c', icon: 'DataAnalysis' },
  { label: '转化率', value: '--', change: 0, color: '#00bcd4', icon: 'TrendCharts' }
])

const alerts = ref([])
const topProducts = ref([])

const loadDashboard = async () => {
  loading.value = true
  try {
    const [summaryRes, topRes, alertsRes] = await Promise.all([
      api.getDashboardSummary({ dimension: trendPeriod.value }),
      api.getTopProducts({ dimension: trendPeriod.value, limit: 10 }),
      api.getAlerts({ limit: 5 })
    ])

    if (summaryRes?.data?.kpi) {
      const kpi = summaryRes.data.kpi
      coreIndicators.value = [
        { label: 'GMV', value: formatCurrency(kpi.total_gmv?.value), change: kpi.total_gmv?.change || 0, color: '#409eff', icon: 'DataLine' },
        { label: '访客数', value: formatNumber(kpi.visitors?.value), change: kpi.visitors?.change || 0, color: '#67c23a', icon: 'User' },
        { label: 'ROI', value: (kpi.roi?.value || 0).toFixed(2), change: 0, color: '#e6a23c', icon: 'DataAnalysis' },
        { label: '转化率', value: (kpi.conversion?.value || 0).toFixed(1) + '%', change: 0, color: '#00bcd4', icon: 'TrendCharts' }
      ]

      if (summaryRes.data.trends?.length) {
        updateTrendChart(summaryRes.data.trends)
      }
    }

    if (topRes?.data?.products) {
      topProducts.value = topRes.data.products.map(p => ({
        id: p.product_id,
        product_id: p.product_id,
        title: p.product_name,
        tier: p.tier,
        net_sales: p.value,
        visitors: p.visitors,
        conversion: (p.conversion || 0) / 100,
        image_url: p.image_url
      }))
    }

    if (alertsRes?.data) {
      const alertList = alertsRes.data.records || (Array.isArray(alertsRes.data) ? alertsRes.data : [])
      alerts.value = alertList.map(a => ({
        id: a.id,
        level: a.status === 'pending' ? 'urgent' : 'warning',
        title: a.title,
        desc: a.detail || a.message || '',
        time: a.created_at || ''
      }))
    }
  } catch (err) {
    console.error('加载仪表盘数据失败:', err)
    const errorMsg = err.response?.data?.detail || err.message || '网络错误'
    ElMessage.error(`数据加载失败: ${errorMsg}`)
    coreIndicators.value = [
      { label: 'GMV', value: '--', change: 0, color: '#409eff', icon: 'DataLine' },
      { label: '访客数', value: '--', change: 0, color: '#67c23a', icon: 'User' },
      { label: 'ROI', value: '--', change: 0, color: '#e6a23c', icon: 'DataAnalysis' },
      { label: '转化率', value: '--', change: 0, color: '#00bcd4', icon: 'TrendCharts' }
    ]
    topProducts.value = []
    alerts.value = []
  } finally {
    loading.value = false
  }
}

const refresh = () => {
  ElMessage.info('正在刷新数据...')
  loadDashboard()
}

const viewProduct = (product) => {
  router.push(`/product/${product.product_id || product.id}`)
}

const initCharts = () => {
  if (charts.trend) {
    charts.trend.dispose()
    charts.trend = null
  }
  if (charts.gauge) {
    charts.gauge.dispose()
    charts.gauge = null
  }
  if (trendChartRef.value) charts.trend = echarts.init(trendChartRef.value)
  if (gaugeChartRef.value) charts.gauge = echarts.init(gaugeChartRef.value)
}

const updateTrendChart = (trendsData) => {
  if (!charts.trend) return

  if (trendsData?.length) {
    const dates = trendsData.map(t => t.period?.slice(-5) || '')
    const gmvData = trendsData.map(t => t.payment_amount || 0)
    const visitorData = trendsData.map(t => t.visitors || 0)

    charts.trend.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['GMV', '访客数'], bottom: 0 },
      grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
      xAxis: { type: 'category', data: dates },
      yAxis: [
        { type: 'value', name: 'GMV', position: 'left' },
        { type: 'value', name: '访客数', position: 'right' }
      ],
      series: [
        { name: 'GMV', type: 'line', data: gmvData, smooth: true, itemStyle: { color: '#409eff' }, areaStyle: { opacity: 0.3 } },
        { name: '访客数', type: 'line', yAxisIndex: 1, data: visitorData, smooth: true, itemStyle: { color: '#67c23a' } }
      ]
    })
    return
  }

  charts.trend.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['GMV', '访客数'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
    xAxis: { type: 'category', data: [] },
    yAxis: [
      { type: 'value', name: 'GMV', position: 'left' },
      { type: 'value', name: '访客数', position: 'right' }
    ],
    series: [
      { name: 'GMV', type: 'line', data: [], smooth: true, itemStyle: { color: '#409eff' } },
      { name: '访客数', type: 'line', yAxisIndex: 1, data: [], smooth: true, itemStyle: { color: '#67c23a' } }
    ]
  })
}

const updateGaugeChart = () => {
  if (!charts.gauge) return
  charts.gauge.setOption({
    tooltip: { formatter: '{a} <br/>{b} : {c}%' },
    series: [{
      type: 'gauge',
      progress: { show: true, width: 18 },
      axisLine: { lineStyle: { width: 18 } },
      axisTick: { show: false },
      splitLine: { length: 15, lineStyle: { width: 2, color: '#999' } },
      axisLabel: { distance: 25, fontSize: 12 },
      anchor: { show: true, showAbove: true, size: 25, itemStyle: { borderWidth: 10 } },
      detail: { valueAnimation: true, fontSize: 32, offsetCenter: [0, '70%'] },
      data: [{ value: 0, name: '加载中...' }]
    }]
  })
}

const updateCharts = () => {
  updateTrendChart()
  updateGaugeChart()
}

const handleResize = () => {
  if (charts.trend) charts.trend.resize()
  if (charts.gauge) charts.gauge.resize()
}

watch(trendPeriod, () => {
  loadDashboard()
})

onMounted(async () => {
  await nextTick()
  initCharts()
  updateCharts()
  window.addEventListener('resize', handleResize)
  loadDashboard()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (charts.trend) {
    charts.trend.dispose()
    charts.trend = null
  }
  if (charts.gauge) {
    charts.gauge.dispose()
    charts.gauge = null
  }
})
</script>

<style scoped>
.command-tower-page {
  background: #f5f7fa;
}

.tower-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  background: white;
  padding: 20px 24px;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.header-left h1 {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 4px 0;
  color: #303133;
}

.subtitle {
  font-size: 14px;
  color: #909399;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.quick-access {
  margin: 24px 0;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 16px 0;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
}

.quick-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  text-decoration: none;
  transition: all 0.3s ease;
}

.quick-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
}

.quick-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.quick-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.quick-name {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.quick-desc {
  font-size: 13px;
  color: #909399;
}

.bottom-section {
  margin-top: 24px;
}

.chart-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.chart-header h3 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: #303133;
}

.chart-container {
  height: 300px;
}
</style>
