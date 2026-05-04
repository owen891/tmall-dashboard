<template>
  <div class="lifecycle-analysis">
    <el-card class="filter-card">
      <div class="filter-row">
        <div class="filter-group">
          <span class="filter-label">周期:</span>
          <el-select v-model="selectedCycle" size="small" class="cycle-select" @change="refreshData">
            <el-option label="日" value="day" />
            <el-option label="周" value="week" />
            <el-option label="月" value="month" />
          </el-select>
        </div>
        
        <div class="filter-group">
          <span class="filter-label">商品状态:</span>
          <el-select v-model="selectedStatus" size="small" class="status-select" @change="handleStatusChange">
            <el-option label="全部" value="all" />
            <el-option label="新品" value="new" />
            <el-option label="成长" value="growing" />
            <el-option label="成熟" value="mature" />
            <el-option label="衰退" value="declining" />
          </el-select>
        </div>
        
        <div class="filter-group">
          <el-button type="primary" size="small" @click="refreshData" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </div>
    </el-card>

    <el-tabs v-model="activeTab" class="main-tabs">
      <el-tab-pane label="生命周期分布" name="distribution">
        <div class="chart-row">
          <el-card class="chart-card">
            <template #header>
              <span>生命周期分布</span>
              <el-radio-group v-model="chartType" size="small" style="float: right;">
                <el-radio-button label="bar">柱状图</el-radio-button>
                <el-radio-button label="line">折线图</el-radio-button>
              </el-radio-group>
            </template>
            <div ref="distributionChartRef" class="chart-container"></div>
          </el-card>
          
          <el-card class="chart-card">
            <template #header>各阶段占比</template>
            <div ref="pieChartRef" class="chart-container"></div>
          </el-card>
        </div>

        <div class="stats-row">
          <el-card class="stat-card" :class="{ 'active': selectedStatus === 'new' }" @click="selectStatus('new')">
            <div class="stat-icon new-icon">
              <el-icon size="24"><Star /></el-icon>
            </div>
            <div class="stat-info">
              <p class="stat-value">{{ lifecycleStats.new || 0 }}</p>
              <p class="stat-label">新品</p>
            </div>
          </el-card>
          
          <el-card class="stat-card" :class="{ 'active': selectedStatus === 'growing' }" @click="selectStatus('growing')">
            <div class="stat-icon growing-icon">
              <el-icon size="24"><ArrowUp /></el-icon>
            </div>
            <div class="stat-info">
              <p class="stat-value">{{ lifecycleStats.growing || 0 }}</p>
              <p class="stat-label">成长中</p>
            </div>
          </el-card>
          
          <el-card class="stat-card" :class="{ 'active': selectedStatus === 'mature' }" @click="selectStatus('mature')">
            <div class="stat-icon mature-icon">
              <el-icon size="24"><Sunny /></el-icon>
            </div>
            <div class="stat-info">
              <p class="stat-value">{{ lifecycleStats.mature || 0 }}</p>
              <p class="stat-label">成熟期</p>
            </div>
          </el-card>
          
          <el-card class="stat-card" :class="{ 'active': selectedStatus === 'declining' }" @click="selectStatus('declining')">
            <div class="stat-icon declining-icon">
              <el-icon size="24"><ArrowDown /></el-icon>
            </div>
            <div class="stat-info">
              <p class="stat-value">{{ lifecycleStats.declining || 0 }}</p>
              <p class="stat-label">衰退期</p>
            </div>
          </el-card>
        </div>

        <el-card class="detail-card">
          <template #header>
            <span>商品生命周期详情</span>
            <span class="detail-subtitle" v-if="selectedStatus !== 'all'">
              - {{ stageNameMap[selectedStatus] }}
            </span>
          </template>
          <el-table 
            :data="products" 
            stripe 
            size="small"
            v-loading="loading"
            :cell-style="{ padding: '6px 8px' }"
          >
            <el-table-column prop="product_id" label="商品ID" width="100" show-overflow-tooltip />
            <el-table-column prop="title" label="商品标题" min-width="200" show-overflow-tooltip />
            <el-table-column prop="category" label="类目" width="100" />
            <el-table-column prop="tier" label="分层" width="80">
              <template #default="{ row }">
                <el-tag :type="getTierType(row.tier)" size="small">{{ row.tier }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="style" label="风格" width="80" />
            <el-table-column prop="scene" label="场景" width="80" />
            <el-table-column prop="manager" label="负责人" width="80" />
            <el-table-column prop="ipv" label="访客数" width="80" align="right">
              <template #default="{ row }">
                {{ formatNumber(row.ipv) }}
              </template>
            </el-table-column>
            <el-table-column prop="pv" label="浏览量" width="80" align="right">
              <template #default="{ row }">
                {{ formatNumber(row.pv) }}
              </template>
            </el-table-column>
            <el-table-column prop="payment_amount" label="支付金额" width="100" align="right">
              <template #default="{ row }">
                {{ formatCurrency(row.payment_amount) }}
              </template>
            </el-table-column>
            <el-table-column prop="payment_conversion" label="转化率" width="80" align="right">
              <template #default="{ row }">
                {{ formatPercent(row.payment_conversion) }}
              </template>
            </el-table-column>
            <el-table-column prop="cart_rate" label="加购率" width="80" align="right">
              <template #default="{ row }">
                {{ formatPercent(row.cart_rate) }}
              </template>
            </el-table-column>
            <el-table-column prop="repurchase_rate" label="复购率" width="80" align="right">
              <template #default="{ row }">
                {{ formatPercent(row.repurchase_rate) }}
              </template>
            </el-table-column>
            <el-table-column prop="marketing_roi" label="营销ROI" width="90" align="right">
              <template #default="{ row }">
                {{ formatNumber(row.marketing_roi, 2) }}
              </template>
            </el-table-column>
            <el-table-column prop="score" label="健康度" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="getScoreType(row.score)" size="small">{{ row.score }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
      
      <el-tab-pane label="GSV数据" name="gsv">
        <div class="gsv-section">
          <div class="chart-row">
            <el-card class="chart-card">
              <template #header>
                2025年汇总GSV
                <span style="float: right; font-size: 20px; font-weight: bold; color: #409eff;">¥{{ formatNumber(summary2025) }}</span>
              </template>
              <div ref="chart2025Ref" class="chart-container"></div>
            </el-card>
            
            <el-card class="chart-card">
              <template #header>
                2026年汇总GSV
                <span style="float: right; font-size: 20px; font-weight: bold; color: #67c23a;">¥{{ formatNumber(summary2026) }}</span>
              </template>
              <div ref="chart2026Ref" class="chart-container"></div>
            </el-card>
          </div>

          <el-card class="chart-card" style="margin-bottom: 20px;">
            <template #header>生命周期曲线对比</template>
            <div ref="compareChartRef" class="chart-container"></div>
          </el-card>

          <el-card class="detail-card">
            <template #header>详细月度GSV数据</template>
            <el-table :data="monthlyData" stripe size="small">
              <el-table-column prop="month" label="月份" width="100" fixed />
              <el-table-column prop="year2025" label="2025年GSV" width="150" align="right">
                <template #default="{ row }">¥{{ formatNumber(row.year2025) }}</template>
              </el-table-column>
              <el-table-column prop="year2026" label="2026年GSV" width="150" align="right">
                <template #default="{ row }">¥{{ formatNumber(row.year2026) }}</template>
              </el-table-column>
              <el-table-column prop="growth" label="同比增长" width="120" align="right">
                <template #default="{ row }">
                  <span :class="row.growth >= 0 ? 'growth-positive' : 'growth-negative'">
                    {{ row.growth >= 0 ? '+' : '' }}{{ row.growth }}%
                  </span>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue'
import { Refresh, Star, ArrowUp, ArrowDown, Sunny } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import api from '@/api'

const selectedCycle = ref('week')
const selectedStatus = ref('all')
const loading = ref(false)
const chartType = ref('bar')
const activeTab = ref('distribution')

const lifecycleStats = ref({
  new: 0,
  growing: 0,
  mature: 0,
  declining: 0
})

const allProducts = ref([])
const distributionChartRef = ref(null)
const pieChartRef = ref(null)
const chart2025Ref = ref(null)
const chart2026Ref = ref(null)
const compareChartRef = ref(null)
let distributionChart = null
let pieChart = null
let chart2025 = null
let chart2026 = null
let compareChart = null

const monthlyData = ref([
  { month: '1月', year2025: 120000, year2026: 150000, growth: 25.0 },
  { month: '2月', year2025: 150000, year2026: 180000, growth: 20.0 },
  { month: '3月', year2025: 180000, year2026: 220000, growth: 22.2 },
  { month: '4月', year2025: 220000, year2026: 0, growth: 0 },
  { month: '5月', year2025: 280000, year2026: 0, growth: 0 },
  { month: '6月', year2025: 350000, year2026: 0, growth: 0 },
  { month: '7月', year2025: 420000, year2026: 0, growth: 0 },
  { month: '8月', year2025: 450000, year2026: 0, growth: 0 },
  { month: '9月', year2025: 400000, year2026: 0, growth: 0 },
  { month: '10月', year2025: 350000, year2026: 0, growth: 0 },
  { month: '11月', year2025: 300000, year2026: 0, growth: 0 },
  { month: '12月', year2025: 250000, year2026: 0, growth: 0 }
])

const summary2025 = computed(() => {
  return monthlyData.value.reduce((sum, item) => sum + (item.year2025 || 0), 0)
})

const summary2026 = computed(() => {
  return monthlyData.value.reduce((sum, item) => sum + (item.year2026 || 0), 0)
})

const stageNameMap = {
  new: '新品',
  growing: '成长中',
  mature: '成熟期',
  declining: '衰退期'
}

const products = computed(() => {
  if (selectedStatus.value === 'all') {
    return allProducts.value
  }
  return allProducts.value.filter(p => p.lifecycle_status === selectedStatus.value)
})

const selectStatus = (status) => {
  selectedStatus.value = status
}

const handleStatusChange = () => {
  loadProducts()
}

const getTierType = (tier) => {
  const types = {
    '引流款': 'primary',
    '利润款': 'success',
    '形象款': 'warning'
  }
  return types[tier] || 'info'
}

const getScoreType = (score) => {
  if (score >= 70) return 'success'
  if (score >= 50) return 'warning'
  return 'danger'
}

const formatNumber = (num) => {
  if (!num && num !== 0) return '0'
  return Number(num).toLocaleString()
}

const formatCurrency = (num) => {
  if (!num && num !== 0) return '-'
  return '¥' + Number(num).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const formatPercent = (num) => {
  if (!num && num !== 0) return '-'
  return (Number(num) * 100).toFixed(2) + '%'
}

const refreshData = async () => {
  loading.value = true
  try {
    const res = await api.getProducts({ 
      tier: selectedStatus.value !== 'all' ? selectedStatus.value : undefined,
      dimension: selectedCycle.value 
    })
    
    if (res && res.data) {
      allProducts.value = (res.data.data || []).map(p => {
        const days = calculateDays(p.list_date)
        let lifecycle_status
        if (days <= 30) {
          lifecycle_status = 'new'
        } else if (days <= 90) {
          lifecycle_status = 'growing'
        } else if (days <= 180) {
          lifecycle_status = 'mature'
        } else {
          lifecycle_status = 'declining'
        }
        return { ...p, lifecycle_status }
      })
      
      const productsData = allProducts.value
      
      lifecycleStats.value = {
        new: productsData.filter(p => p.lifecycle_status === 'new').length,
        growing: productsData.filter(p => p.lifecycle_status === 'growing').length,
        mature: productsData.filter(p => p.lifecycle_status === 'mature').length,
        declining: productsData.filter(p => p.lifecycle_status === 'declining').length
      }
      
      nextTick(() => initCharts())
    }
  } catch (error) {
    console.error('Failed to load lifecycle data:', error)
  } finally {
    loading.value = false
  }
}

const loadProducts = async () => {
  loading.value = true
  try {
    const res = await api.getProducts({ dimension: selectedCycle.value })
    if (res && res.data) {
      allProducts.value = (res.data.data || []).map(p => {
        const days = calculateDays(p.list_date)
        let lifecycle_status
        if (days <= 30) {
          lifecycle_status = 'new'
        } else if (days <= 90) {
          lifecycle_status = 'growing'
        } else if (days <= 180) {
          lifecycle_status = 'mature'
        } else {
          lifecycle_status = 'declining'
        }
        return { ...p, lifecycle_status }
      })
    }
  } catch (error) {
    console.error('Failed to load products:', error)
  } finally {
    loading.value = false
  }
}

const calculateDays = (listDate) => {
  if (!listDate) return 0
  const list = new Date(listDate)
  const now = new Date()
  return Math.floor((now - list) / (1000 * 60 * 60 * 24))
}

const initCharts = () => {
  initDistributionChart()
  initPieChart()
  initGsvCharts()
}

const initGsvCharts = () => {
  initChart2025()
  initChart2026()
  initCompareChart()
}

const initDistributionChart = () => {
  if (!distributionChartRef.value) return
  
  if (distributionChart) {
    distributionChart.dispose()
  }
  
  distributionChart = echarts.init(distributionChartRef.value)
  
  const labels = ['新品', '成长中', '成熟期', '衰退期']
  const data = [
    lifecycleStats.value.new,
    lifecycleStats.value.growing,
    lifecycleStats.value.mature,
    lifecycleStats.value.declining
  ]
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: labels
    },
    yAxis: {
      type: 'value',
      name: '商品数量'
    },
    series: chartType.value === 'bar' ? [
      {
        name: '商品数量',
        type: 'bar',
        data: data,
        itemStyle: {
          color: (params) => {
            const colors = ['#67c23a', '#409eff', '#e6a23c', '#f56c6c']
            return colors[params.dataIndex]
          }
        },
        label: {
          show: true,
          position: 'top'
        }
      }
    ] : [
      {
        name: '商品数量',
        type: 'line',
        data: data,
        itemStyle: { color: '#409eff' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
            { offset: 1, color: 'rgba(64, 158, 255, 0.05)' }
          ])
        },
        label: { show: true }
      }
    ]
  }
  
  distributionChart.setOption(option)
  window.addEventListener('resize', () => distributionChart?.resize())
}

const initPieChart = () => {
  if (!pieChartRef.value) return
  
  if (pieChart) {
    pieChart.dispose()
  }
  
  pieChart = echarts.init(pieChartRef.value)
  
  const pieData = [
    { value: lifecycleStats.value.new, name: '新品', itemStyle: { color: '#67c23a' } },
    { value: lifecycleStats.value.growing, name: '成长中', itemStyle: { color: '#409eff' } },
    { value: lifecycleStats.value.mature, name: '成熟期', itemStyle: { color: '#e6a23c' } },
    { value: lifecycleStats.value.declining, name: '衰退期', itemStyle: { color: '#f56c6c' } }
  ]
  
  const total = pieData.reduce((sum, item) => sum + item.value, 0)
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left'
    },
    series: [
      {
        name: '生命周期',
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['50%', '50%'],
        data: pieData,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        },
        label: {
          formatter: '{b}\n{d}%'
        }
      }
    ]
  }
  
  pieChart.setOption(option)
  window.addEventListener('resize', () => pieChart?.resize())
}

const initChart2025 = () => {
  if (!chart2025Ref.value) return
  
  if (chart2025) {
    chart2025.dispose()
  }
  
  chart2025 = echarts.init(chart2025Ref.value)
  
  const data = monthlyData.value.map(item => item.year2025 || 0)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: '{b}<br/>GSV: ¥{c}'
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: 'GSV',
        type: 'bar',
        data: data,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#409eff' },
            { offset: 1, color: '#66b1ff' }
          ])
        }
      }
    ]
  }
  
  chart2025.setOption(option)
  window.addEventListener('resize', () => chart2025?.resize())
}

const initChart2026 = () => {
  if (!chart2026Ref.value) return
  
  if (chart2026) {
    chart2026.dispose()
  }
  
  chart2026 = echarts.init(chart2026Ref.value)
  
  const data = monthlyData.value.map(item => item.year2026 || 0)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: '{b}<br/>GSV: ¥{c}'
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: 'GSV',
        type: 'bar',
        data: data,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#67c23a' },
            { offset: 1, color: '#95d475' }
          ])
        }
      }
    ]
  }
  
  chart2026.setOption(option)
  window.addEventListener('resize', () => chart2026?.resize())
}

const initCompareChart = () => {
  if (!compareChartRef.value) return
  
  if (compareChart) {
    compareChart.dispose()
  }
  
  compareChart = echarts.init(compareChartRef.value)
  
  const data2025 = monthlyData.value.map(item => item.year2025 || 0)
  const data2026 = monthlyData.value.map(item => item.year2026 || 0)
  
  const option = {
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['2025年', '2026年']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: '2025年',
        type: 'line',
        data: data2025,
        itemStyle: { color: '#409eff' },
        smooth: true
      },
      {
        name: '2026年',
        type: 'line',
        data: data2026,
        itemStyle: { color: '#67c23a' },
        smooth: true
      }
    ]
  }
  
  compareChart.setOption(option)
  window.addEventListener('resize', () => compareChart?.resize())
}

watch(activeTab, (newTab) => {
  if (newTab === 'gsv') {
    nextTick(() => initGsvCharts())
  }
})

onMounted(() => {
  refreshData()
})
</script>

<style scoped>
.lifecycle-analysis {
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

.cycle-select, .status-select {
  width: 120px;
}

.chart-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.chart-card {
  min-height: 350px;
}

.chart-container {
  height: 280px;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  cursor: pointer;
  transition: all 0.3s;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.stat-card.active {
  border: 2px solid #409eff;
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.new-icon {
  background: linear-gradient(135deg, #67c23a 0%, #85ce61 100%);
  color: #fff;
}

.growing-icon {
  background: linear-gradient(135deg, #409eff 0%, #67b8ff 100%);
  color: #fff;
}

.mature-icon {
  background: linear-gradient(135deg, #e6a23c 0%, #f0c78a 100%);
  color: #fff;
}

.declining-icon {
  background: linear-gradient(135deg, #f56c6c 0%, #f89898 100%);
  color: #fff;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  margin: 0 0 4px 0;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin: 0;
}

.detail-card {
  min-height: 400px;
}

.detail-subtitle {
  color: #909399;
  font-size: 13px;
  margin-left: 8px;
}
</style>
