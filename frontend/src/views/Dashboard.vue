<template>
  <div class="dashboard page-container">
    <div class="dashboard-header">
      <div class="header-left">
        <h1 class="page-title">
          <el-icon class="title-icon"><DataAnalysis /></el-icon>
          销售数据看板
        </h1>
        <p class="page-subtitle">实时监控店铺销售数据和商品表现</p>
      </div>
      <div class="header-right">
        <div class="time-info">
          <el-icon><Clock /></el-icon>
          <span>{{ currentTime }}</span>
        </div>
        <div class="data-status" :class="{ 'status-good': dataFresh, 'status-outdated': !dataFresh }">
          <el-icon><SuccessFilled v-if="dataFresh" /><WarningFilled v-else /></el-icon>
          <span>{{ dataFresh ? '数据已更新' : '数据待更新' }}</span>
        </div>
      </div>
    </div>

    <div v-if="error" class="error-banner">
      <el-alert
        :title="error"
        type="error"
        :closable="false"
        show-icon
      >
        <template #default>
          <el-button type="primary" size="small" @click="loadData" :loading="loading">
            <el-icon><RefreshRight /></el-icon>
            重新加载
          </el-button>
        </template>
      </el-alert>
    </div>

    <div class="quick-actions">
      <el-button-group>
        <el-button 
          v-for="dim in dimensions" 
          :key="dim.value"
          :type="activeDim === dim.value ? 'primary' : 'default'"
          @click="changeDim(dim.value)"
          :class="{ 'active-btn': activeDim === dim.value }"
        >
          <el-icon><component :is="dim.icon" /></el-icon>
          {{ dim.label }}
        </el-button>
      </el-button-group>
      <el-button type="success" :loading="loading" @click="loadData" circle>
        <el-icon><RefreshRight /></el-icon>
      </el-button>
    </div>

    <el-row :gutter="20" class="kpi-cards">
      <el-col :xs="24" :sm="12" :lg="6" v-for="(kpi, index) in kpiCards" :key="index">
        <el-card class="kpi-card" shadow="hover" :body-style="{ padding: '0' }">
          <div class="kpi-content" :style="{ background: kpi.gradient }">
            <div class="kpi-icon-wrapper" :style="{ background: kpi.iconBg }">
              <el-icon :size="32"><component :is="kpi.icon" /></el-icon>
            </div>
            <div class="kpi-data">
              <p class="kpi-label">{{ kpi.label }}</p>
              <p class="kpi-value" :class="kpi.valueClass">{{ kpi.displayValue }}</p>
              <p class="kpi-change" :class="kpi.changeClass">
                <el-icon><CaretTop v-if="kpi.change > 0" /><CaretBottom v-else-if="kpi.change < 0" /></el-icon>
                {{ kpi.changeText }}
              </p>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="summary-cards" v-if="showSummaryCards">
      <el-col :xs="24" :sm="8" v-for="stat in summaryStats" :key="stat.key">
        <el-card class="summary-card" shadow="hover">
          <div class="summary-content">
            <div class="summary-icon" :style="{ color: stat.color }">
              <el-icon :size="40"><component :is="stat.icon" /></el-icon>
            </div>
            <div class="summary-data">
              <p class="summary-label">{{ stat.label }}</p>
              <p class="summary-value">{{ stat.value }}</p>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="charts-row">
      <el-col :xs="24" :md="16">
        <el-card shadow="hover" class="chart-card">
          <template #header>
            <div class="card-header">
              <span class="card-title">
                <el-icon><TrendCharts /></el-icon>
                GMV 趋势分析
              </span>
              <el-segmented v-model="trendType" :options="trendOptions" size="small" />
            </div>
          </template>
          <div ref="trendChartRef" class="chart-container" v-loading="chartLoading.trend"></div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card shadow="hover" class="chart-card">
          <template #header>
            <div class="card-header">
              <span class="card-title">
                <el-icon><PieChart /></el-icon>
                商品分层占比
              </span>
            </div>
          </template>
          <div ref="categoryChartRef" class="chart-container" v-loading="chartLoading.category"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="products-row">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span class="card-title">
                <el-icon><Goods /></el-icon>
                热销商品 TOP{{ topProducts.length }}
              </span>
              <div class="header-actions">
                <el-input
                  v-model="productSearch"
                  placeholder="搜索商品ID或名称..."
                  size="small"
                  style="width: 220px; margin-right: 12px;"
                  clearable
                  @input="filterProducts"
                >
                  <template #prefix><el-icon><Search /></el-icon></template>
                </el-input>
                <el-button type="primary" @click="$router.push('/products')">
                  查看全部 <el-icon><ArrowRight /></el-icon>
                </el-button>
              </div>
            </div>
          </template>
          
          <el-table 
            :data="filteredProducts" 
            stripe
            :default-sort="{ prop: 'net_sales', order: 'descending' }"
            @sort-change="handleProductSort"
            empty-text="暂无热销商品数据，请先导入商品"
            max-height="450"
            border
          >
            <el-table-column type="index" label="排名" width="70" align="center">
              <template #default="{ $index }">
                <el-tag 
                  :type="$index < 3 ? 'danger' : 'info'" 
                  effect="dark" 
                  size="small"
                  round
                >
                  {{ $index + 1 }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="商品图片" width="90" align="center">
              <template #default="{ row }">
                <el-avatar 
                  :src="row.image_url" 
                  :size="55" 
                  shape="square"
                  :error-icon="Picture"
                  class="product-avatar"
                />
              </template>
            </el-table-column>
            <el-table-column prop="product_id" label="商品ID" width="140" sortable />
            <el-table-column prop="title" label="商品名称" min-width="220" show-overflow-tooltip />
            <el-table-column prop="tier" label="分层" width="100" align="center" sortable>
              <template #default="{ row }">
                <el-tag :type="getTierType(row.tier)" size="small" effect="plain" round>
                  {{ row.tier || '未分层' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="net_sales" label="销售额" width="130" align="right" sortable>
              <template #default="{ row }">
                <span class="money-value" :class="getSalesClass(row.net_sales)">
                  ¥{{ formatMoney(row.net_sales) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="visitors" label="访客数" width="110" align="right" sortable>
              <template #default="{ row }">
                {{ formatNumber(row.visitors) }}
              </template>
            </el-table-column>
            <el-table-column prop="conversion" label="转化率" width="100" align="right" sortable>
              <template #default="{ row }">
                <el-progress 
                  :percentage="((row.conversion || 0) * 100).toFixed(1)" 
                  :color="getConversionColor(row.conversion)"
                  :stroke-width="12"
                  :show-text="false"
                />
                <span :class="getConversionClass(row.conversion)">
                  {{ ((row.conversion || 0) * 100).toFixed(1) }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="roi" label="ROI" width="100" align="right" sortable>
              <template #default="{ row }">
                <span :class="getRoiClass(row.roi)">
                  {{ (row.roi || 0).toFixed(2) }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, nextTick, computed } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { 
  TrendCharts, User, Money, DataAnalysis, ArrowRight, Picture, 
  RefreshRight, PieChart, Goods, Search, Clock, SuccessFilled,
  WarningFilled, CaretTop, CaretBottom
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { useTimeStore } from '@/stores/time'
import { formatNumber, getTierType } from '@/utils/format'

const router = useRouter()
const timeStore = useTimeStore()
const loading = ref(true)
const error = ref(null)
const summary = ref({})
const topProducts = ref([])
const filteredProducts = ref([])
const productSearch = ref('')
const activeDim = ref('weekly')
const trendType = ref('gmv')
const trendOptions = [
  { label: '销售额', value: 'gmv' },
  { label: '访客数', value: 'visitors' },
  { label: '转化率', value: 'conversion' }
]
const chartLoading = reactive({ trend: false, category: false })
const currentTime = ref('')
const dataFresh = ref(false)

const dimensions = [
  { label: '按日', value: 'daily', icon: 'Calendar' },
  { label: '按周', value: 'weekly', icon: 'TrendCharts' },
  { label: '按月', value: 'monthly', icon: 'Histogram' }
]

const kpiCards = reactive([
  { 
    key: 'gmv', 
    label: '总 GMV', 
    value: 0,
    displayValue: '¥0',
    change: 0,
    changeText: '-',
    changeClass: '',
    valueClass: '',
    icon: 'Money',
    gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    iconBg: 'rgba(255,255,255,0.2)'
  },
  { 
    key: 'visitors', 
    label: '总访客数', 
    value: 0,
    displayValue: '0',
    change: 0,
    changeText: '-',
    changeClass: '',
    valueClass: '',
    icon: 'User',
    gradient: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
    iconBg: 'rgba(255,255,255,0.2)'
  },
  { 
    key: 'ad_spend', 
    label: '广告支出', 
    value: 0,
    displayValue: '¥0',
    change: 0,
    changeText: '-',
    changeClass: '',
    valueClass: '',
    icon: 'Wallet',
    gradient: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
    iconBg: 'rgba(255,255,255,0.2)'
  },
  { 
    key: 'roi', 
    label: '平均 ROI', 
    value: 0,
    displayValue: '0.00',
    change: 0,
    changeText: '-',
    changeClass: '',
    valueClass: '',
    icon: 'DataLine',
    gradient: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
    iconBg: 'rgba(255,255,255,0.2)'
  },
])

const trendChartRef = ref(null)
const categoryChartRef = ref(null)
const charts = reactive({ trend: null, category: null })

const showSummaryCards = computed(() => {
  return summary.value && Object.keys(summary.value).length > 0
})

const summaryStats = computed(() => {
  const kpi = summary.value.kpi || {}
  return [
    {
      key: 'net_sales',
      label: '净销售额',
      value: '¥' + formatNumber(kpi.net_sales?.value || 0),
      color: '#409eff',
      icon: 'Coin'
    },
    {
      key: 'refund',
      label: '退款率',
      value: (kpi.refund_rate?.value || 0).toFixed(2) + '%',
      color: '#e6a23c',
      icon: 'RefreshLeft'
    },
    {
      key: 'total_products',
      label: '商品总数',
      value: topProducts.value.length + '+',
      color: '#67c23a',
      icon: 'Box'
    }
  ]
})

const changeDim = async (dim) => {
  activeDim.value = dim
  await loadData()
}

const formatMoney = (val) => {
  if (!val) return '0'
  if (val >= 10000) {
    return (val / 10000).toFixed(2) + 'W'
  }
  return val.toFixed(2)
}

const filterProducts = () => {
  if (!productSearch.value) {
    filteredProducts.value = [...topProducts.value]
    return
  }
  const keyword = productSearch.value.toLowerCase()
  filteredProducts.value = topProducts.value.filter(p => 
    p.product_id?.toLowerCase().includes(keyword) ||
    p.title?.toLowerCase().includes(keyword)
  )
}

const handleProductSort = ({ prop, order }) => {
  if (!prop) {
    filteredProducts.value = [...topProducts.value]
    return
  }
  const sorted = [...topProducts.value].sort((a, b) => {
    const valA = a[prop] ?? 0
    const valB = b[prop] ?? 0
    return order === 'ascending' ? valA - valB : valB - valA
  })
  filteredProducts.value = sorted
}

const getSalesClass = (value) => {
  if (!value || value <= 0) return 'text-muted'
  return value >= 10000 ? 'text-success' : 'text-primary'
}

const getConversionClass = (value) => {
  if (!value || value <= 0) return 'text-muted'
  return value >= 0.05 ? 'text-success' : value >= 0.02 ? 'text-warning' : 'text-danger'
}

const getConversionColor = (value) => {
  if (!value || value <= 0) return '#c0c4cc'
  return value >= 0.05 ? '#67c23a' : value >= 0.02 ? '#e6a23c' : '#f56c6c'
}

const getRoiClass = (value) => {
  if (!value || value <= 0) return 'text-muted'
  return value >= 3 ? 'text-success' : value >= 1.5 ? 'text-warning' : 'text-danger'
}

const updateCurrentTime = () => {
  const now = new Date()
  currentTime.value = now.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const updateKPICards = () => {
  const kpi = summary.value.kpi || {}
  
  kpiCards[0].value = kpi.total_gmv?.value || 0
  kpiCards[0].displayValue = '¥' + formatNumber(kpiCards[0].value)
  kpiCards[0].change = kpi.total_gmv?.percent || 0
  kpiCards[0].changeText = getChangeText(kpiCards[0].change)
  kpiCards[0].changeClass = getChangeClass(kpiCards[0].change)
  
  kpiCards[1].value = kpi.visitors?.value || 0
  kpiCards[1].displayValue = formatNumber(kpiCards[1].value)
  kpiCards[1].change = kpi.visitors?.percent || 0
  kpiCards[1].changeText = getChangeText(kpiCards[1].change)
  kpiCards[1].changeClass = getChangeClass(kpiCards[1].change)
  
  kpiCards[2].value = kpi.ad_spend?.value || 0
  kpiCards[2].displayValue = '¥' + formatNumber(kpiCards[2].value)
  kpiCards[2].change = kpi.ad_spend?.percent || 0
  kpiCards[2].changeText = getChangeText(kpiCards[2].change)
  kpiCards[2].changeClass = getChangeClass(kpiCards[2].change)
  
  kpiCards[3].value = kpi.roi?.value || 0
  kpiCards[3].displayValue = kpiCards[3].value.toFixed(2)
  kpiCards[3].change = kpi.roi?.percent || 0
  kpiCards[3].changeText = getChangeText(kpiCards[3].change)
  kpiCards[3].changeClass = getChangeClass(kpiCards[3].change)
}

const getChangeClass = (change) => {
  if (!change) return ''
  return change > 0 ? 'change-up' : change < 0 ? 'change-down' : 'change-flat'
}

const getChangeText = (change) => {
  if (!change || change === 0) return '0%'
  const prefix = change > 0 ? '+' : ''
  return `${prefix}${change.toFixed(1)}%`
}

const initCharts = () => {
  if (charts.trend) charts.trend.dispose()
  if (charts.category) charts.category.dispose()

  if (trendChartRef.value) charts.trend = echarts.init(trendChartRef.value)
  if (categoryChartRef.value) charts.category = echarts.init(categoryChartRef.value)
}

const updateCharts = () => {
  if (charts.trend) {
    const trends = summary.value.trends || []
    const periods = trends.map(t => t.period || t.date || '')
    const values = trends.map(t => {
      if (trendType.value === 'gmv') return t.payment_amount || t.net_sales || 0
      if (trendType.value === 'visitors') return t.visitors || 0
      if (trendType.value === 'conversion') return ((t.conversion || 0) * 100).toFixed(2)
      return 0
    })
    
    const chartColors = {
      gmv: { color: '#667eea', name: '销售额', unit: '¥' },
      visitors: { color: '#f5576c', name: '访客数', unit: '' },
      conversion: { color: '#43e97b', name: '转化率', unit: '%' }
    }
    const { color, name, unit } = chartColors[trendType.value]
    
    charts.trend.setOption({
      tooltip: { 
        trigger: 'axis',
        backgroundColor: 'rgba(255,255,255,0.95)',
        borderColor: '#eee',
        textStyle: { color: '#333' },
        formatter: (params) => {
          const data = params[0]
          return `<b>${data.name}</b><br/>${name}: ${unit}${formatNumber(data.value)}`
        }
      },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { 
        type: 'category', 
        data: periods,
        axisLabel: { rotate: 30, color: '#666' }
      },
      yAxis: { 
        type: 'value', 
        name: name + (unit ? ` (${unit})` : ''),
        nameTextStyle: { color: '#666' },
        axisLabel: { 
          color: '#666',
          formatter: (val) => {
            if (val >= 10000) return (val / 10000).toFixed(1) + 'W'
            return val
          }
        }
      },
      series: [{
        name,
        type: 'line',
        data: values,
        smooth: true,
        areaStyle: { 
          opacity: 0.3,
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: color },
            { offset: 1, color: color + '20' }
          ])
        },
        itemStyle: { color },
        lineStyle: { width: 3 }
      }]
    })
  }

  if (charts.category) {
    const products = topProducts.value.slice(0, 10)
    const chartData = products.map(p => ({
      name: p.title?.substring(0, 15) || p.product_id,
      value: p.net_sales || 0
    }))

    charts.category.setOption({
      tooltip: { 
        trigger: 'item', 
        backgroundColor: 'rgba(255,255,255,0.95)',
        borderColor: '#eee',
        textStyle: { color: '#333' },
        formatter: (params) => {
          return `${params.name}<br/>销售额: ¥${formatNumber(params.value)}<br/>占比: ${params.percent}%`
        }
      },
      color: ['#667eea', '#764ba2', '#f093fb', '#4facfe', '#43e97b', '#38f9d7', '#f5576c', '#00f2fe', '#e6a23c', '#67c23a'],
      series: [{
        type: 'pie',
        radius: ['45%', '75%'],
        center: ['50%', '45%'],
        label: { show: true, formatter: '{b}\n{d}%', color: '#333' },
        labelLine: { show: true },
        data: chartData,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.3)'
          }
        }
      }]
    })
  }
}

const loadData = async () => {
  loading.value = true
  error.value = null
  dataFresh.value = false
  
  try {
    const params = { dim: activeDim.value }
    if (timeStore.selectedPeriod) {
      params.period = timeStore.selectedPeriod
    }

    const [summaryRes, topRes] = await Promise.all([
      api.getKPI(params),
      api.getTopProducts({ dimension: activeDim.value, limit: 10 })
    ])
    
    summary.value = summaryRes.data || {}
    topProducts.value = (topRes.data?.products || []).map(p => ({
      product_id: p.product_id,
      title: p.product_name || p.title || '未知商品',
      image_url: p.image_url,
      tier: p.tier || '',
      net_sales: p.value || p.payment_amount || 0,
      visitors: p.visitors || 0,
      conversion: p.conversion || 0,
      roi: p.roi || 0
    }))
    
    filteredProducts.value = [...topProducts.value]
    updateKPICards()
    dataFresh.value = true
    
    await nextTick()
    chartLoading.trend = true
    chartLoading.category = true
    initCharts()
    updateCharts()
    chartLoading.trend = false
    chartLoading.category = false

    if (topProducts.value.length === 0) {
      ElMessage.info('暂无商品数据，请先导入数据')
    }
  } catch (err) {
    console.error('Load data error:', err)
    error.value = err.response?.data?.detail || err.message || '加载数据失败，请检查网络连接'
    ElMessage.error(error.value)
    dataFresh.value = false
  } finally {
    loading.value = false
  }
}

const handleResize = () => {
  if (charts.trend) charts.trend.resize()
  if (charts.category) charts.category.resize()
}

let timeInterval = null
onMounted(() => {
  updateCurrentTime()
  timeInterval = setInterval(updateCurrentTime, 60000)
  loadData()
  window.addEventListener('resize', handleResize)
})

watch(() => trendType.value, () => {
  updateCharts()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (timeInterval) clearInterval(timeInterval)
  if (charts.trend) { charts.trend.dispose(); charts.trend = null }
  if (charts.category) { charts.category.dispose(); charts.category = null }
})
</script>

<style scoped>
.dashboard {
  padding: 24px;
  min-height: calc(100vh - 60px);
  background: #f5f7fa;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e4e7ed;
}

.header-left {
  flex: 1;
}

.page-title {
  margin: 0 0 8px 0;
  font-size: 28px;
  font-weight: 700;
  color: #1a1a1a;
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-icon {
  font-size: 32px;
  color: #409eff;
}

.page-subtitle {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.header-right {
  display: flex;
  gap: 16px;
  align-items: center;
}

.time-info {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #606266;
  font-size: 14px;
}

.data-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  padding: 4px 12px;
  border-radius: 12px;
}

.status-good {
  color: #67c23a;
  background: #f0f9eb;
}

.status-outdated {
  color: #e6a23c;
  background: #fdf6ec;
}

.error-banner {
  margin-bottom: 20px;
  animation: slideDown 0.3s ease-out;
}

@keyframes slideDown {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}

.quick-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  align-items: center;
}

.active-btn {
  font-weight: 600;
}

.kpi-cards {
  margin-bottom: 24px;
}

.kpi-card {
  border-radius: 12px;
  overflow: hidden;
  transition: transform 0.3s, box-shadow 0.3s;
  height: 140px;
}

.kpi-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
}

.kpi-content {
  padding: 20px;
  height: 100%;
  display: flex;
  align-items: center;
  gap: 16px;
}

.kpi-icon-wrapper {
  width: 60px;
  height: 60px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.kpi-data {
  flex: 1;
}

.kpi-label {
  margin: 0;
  font-size: 14px;
  color: rgba(255,255,255,0.8);
  font-weight: 500;
}

.kpi-value {
  margin: 8px 0;
  font-size: 24px;
  font-weight: 700;
  color: white;
}

.kpi-change {
  margin: 0;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.change-up { color: rgba(255,255,255,0.9); }
.change-down { color: rgba(255,255,255,0.7); }
.change-flat { color: rgba(255,255,255,0.8); }

.summary-cards {
  margin-bottom: 24px;
}

.summary-card {
  border-radius: 8px;
  margin-bottom: 0;
}

.summary-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.summary-icon {
  width: 50px;
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.summary-label {
  margin: 0;
  font-size: 13px;
  color: #909399;
}

.summary-value {
  margin: 4px 0 0 0;
  font-size: 20px;
  font-weight: 700;
  color: #303133;
}

.charts-row {
  margin-bottom: 24px;
}

.chart-card {
  border-radius: 12px;
  margin-bottom: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 16px;
  color: #303133;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chart-container {
  height: 350px;
  width: 100%;
}

.product-avatar {
  border: 1px solid #ebeef5;
}

.money-value {
  font-weight: 600;
  font-family: 'Consolas', monospace;
}

.text-muted { color: #c0c4cc; }
.text-primary { color: #409eff; }
.text-success { color: #67c23a; }
.text-warning { color: #e6a23c; }
.text-danger { color: #f56c6c; }

@media (max-width: 768px) {
  .dashboard { padding: 12px; }
  .dashboard-header { flex-direction: column; align-items: flex-start; gap: 12px; }
  .header-right { width: 100%; justify-content: space-between; }
  .chart-container { height: 250px; }
  .kpi-card { height: 120px; margin-bottom: 12px; }
  .kpi-icon-wrapper { width: 45px; height: 45px; }
  .kpi-value { font-size: 20px; }
  .card-header { flex-direction: column; align-items: flex-start; gap: 10px; }
  .header-actions { width: 100%; }
  .header-actions .el-input { width: 100% !important; margin-right: 0 !important; margin-bottom: 8px; }
}

:deep(.el-card__header) {
  padding: 16px 20px;
  border-bottom: 1px solid #ebeef5;
  background: #fafafa;
}

:deep(.el-table) {
  --el-table-header-bg-color: #fafafa;
}

:deep(.el-progress__text) {
  display: none;
}
</style>
