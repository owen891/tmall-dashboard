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
        :cell-style="{ padding: '8px 12px' }"
      >
        <el-table-column prop="title" label="商品名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="tier" label="分层" width="100">
          <template #default="{ row }">
            <el-tag :type="getTierType(row.tier)">{{ row.tier }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="payment_amount" label="销售额" width="120" align="right">
          <template #default="{ row }">
            ¥{{ formatNumber(row.payment_amount) }}
          </template>
        </el-table-column>
        <el-table-column prop="visitors" label="访客数" width="100" align="right">
          <template #default="{ row }">
            {{ formatNumber(row.visitors) }}
          </template>
        </el-table-column>
        <el-table-column prop="conversion" label="转化率" width="100" align="right">
          <template #default="{ row }">
            {{ ((row.conversion || 0) * 100).toFixed(2) }}%
          </template>
        </el-table-column>
        <el-table-column prop="roi" label="ROI" width="80" align="right">
          <template #default="{ row }">
            {{ (row.roi || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="score" label="健康度" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getScoreType(row.score)">{{ row.score }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import { Refresh, Star, ArrowUp, ArrowDown, Sunny } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import api from '@/api'

const selectedCycle = ref('week')
const selectedStatus = ref('all')
const loading = ref(false)
const chartType = ref('bar')

const lifecycleStats = ref({
  new: 0,
  growing: 0,
  mature: 0,
  declining: 0
})

const allProducts = ref([])
const distributionChartRef = ref(null)
const pieChartRef = ref(null)
let distributionChart = null
let pieChart = null

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
  return allProducts.value
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

const refreshData = async () => {
  loading.value = true
  try {
    const res = await api.getProducts({ 
      tier: selectedStatus.value !== 'all' ? selectedStatus.value : undefined,
      dimension: selectedCycle.value 
    })
    
    if (res && res.data) {
      allProducts.value = res.data.data || []
      
      const productsData = allProducts.value
      
      lifecycleStats.value = {
        new: productsData.filter(p => {
          const days = calculateDays(p.list_date)
          return days <= 30
        }).length,
        growing: productsData.filter(p => {
          const days = calculateDays(p.list_date)
          return days > 30 && days <= 90
        }).length,
        mature: productsData.filter(p => {
          const days = calculateDays(p.list_date)
          return days > 90 && days <= 180
        }).length,
        declining: productsData.filter(p => {
          const days = calculateDays(p.list_date)
          return days > 180
        }).length
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
      allProducts.value = res.data.data || []
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
