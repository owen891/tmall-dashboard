<template>
  <div class="crowd-asset-container page-container">
    <div class="page-header">
      <h1>人群资产归因</h1>
      <div class="header-actions">
        <el-button type="primary" @click="refresh">
          <el-icon><Refresh /></el-icon> 刷新数据
        </el-button>
      </div>
    </div>

    <div v-loading="loading" class="content-area">
      <el-row :gutter="20" class="summary-cards">
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-label">总广告消耗</div>
            <div class="stat-value">¥{{ formatNumber(summary.total_cost) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-label">总GMV</div>
            <div class="stat-value">¥{{ formatNumber(summary.total_gmv) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-label">人群资产ROI</div>
            <div class="stat-value">{{ summary.asset_roi?.toFixed(2) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-label">AIPL增量</div>
            <div class="stat-value">
              <span v-if="summary.aipl_increase">{{ formatNumber(summary.aipl_increase) }}</span>
              <span v-else>-</span>
            </div>
          </div>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="16">
          <div class="chart-card">
            <div class="card-header">
              <h3>AIPL增量趋势</h3>
            </div>
            <div ref="aiplChartRef" class="chart-container"></div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="chart-card">
            <div class="card-header">
              <h3>TOP人群</h3>
            </div>
            <div class="crowd-list">
              <div v-for="crowd in topCrowds" :key="crowd.id" class="crowd-item">
                <div class="crowd-info">
                  <el-tag size="small" :type="getCrowdType(crowd.tier)">{{ crowd.tier }}</el-tag>
                  <span class="crowd-name">{{ crowd.crowd_name }}</span>
                </div>
                <div class="crowd-metrics">
                  <span class="metric">ROI: {{ crowd.asset_roi?.toFixed(2) }}</span>
                </div>
              </div>
            </div>
          </div>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="24">
          <div class="chart-card">
            <div class="card-header">
              <h3>人群×出价效率矩阵</h3>
              <div class="header-actions">
                <el-button size="small" @click="showCreateCrowd = true">添加人群包</el-button>
              </div>
            </div>
            <div ref="matrixChartRef" class="chart-container"></div>
          </div>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import api from '@/api'
import { formatNumber } from '@/utils/format'

const loading = ref(false)
const aiplChartRef = ref(null)
const matrixChartRef = ref(null)
let aiplChart = null
let matrixChart = null
let handleResize = null

const summary = ref({
  total_cost: 0,
  total_gmv: 0,
  asset_roi: 0,
  aipl_increase: 0
})

const topCrowds = ref([])
const efficiencyMatrix = ref([])

const refresh = async () => {
  loading.value = true
  try {
    const [dashboardRes, matrixRes] = await Promise.all([
      api.crowdAssetApi.getDashboard(),
      api.crowdAssetApi.getEfficiencyMatrix()
    ])
    
    const dashboardData = dashboardRes?.data || {}
    const matrixData = matrixRes?.data || {}
    
    if (dashboardData.summary) {
      summary.value = {
        total_cost: dashboardData.summary.total_cost || 0,
        total_gmv: dashboardData.summary.total_gmv || 0,
        asset_roi: dashboardData.summary.total_roi || 0,
        aipl_increase: (dashboardData.aipl_increase?.awareness || 0) + 
                       (dashboardData.aipl_increase?.interest || 0) + 
                       (dashboardData.aipl_increase?.purchase || 0) + 
                       (dashboardData.aipl_increase?.loyalty || 0)
      }
      topCrowds.value = dashboardData.top_crowds || []
    }
    
    if (matrixData.matrix) {
      efficiencyMatrix.value = matrixData.matrix
    }
    
    renderCharts()
  } catch (error) {
    console.error('加载人群资产数据失败:', error)
    loadMockData()
    renderCharts()
    ElMessage.error('加载数据失败，使用模拟数据')
  } finally {
    loading.value = false
  }
}

const loadMockData = () => {
  summary.value = {
    total_cost: 250000,
    total_gmv: 850000,
    asset_roi: 3.4,
    aipl_increase: 15600
  }
  topCrowds.value = [
    { id: 1, crowd_name: '高潜女性用户', tier: 'S', asset_roi: 4.2 },
    { id: 2, crowd_name: '运动爱好者', tier: 'A', asset_roi: 3.8 },
    { id: 3, crowd_name: '新客试用人群', tier: 'A', asset_roi: 3.2 },
    { id: 4, crowd_name: '复购老客', tier: 'S', asset_roi: 4.5 },
    { id: 5, crowd_name: '泛兴趣人群', tier: 'B', asset_roi: 2.1 }
  ]
}

const getCrowdType = (tier) => {
  const types = { 'S': 'danger', 'A': 'warning', 'B': '' }
  return types[tier] || ''
}

const renderCharts = () => {
  renderAiplChart()
  renderMatrixChart()
}

const renderAiplChart = () => {
  if (!aiplChartRef.value) return
  if (!aiplChart) {
    aiplChart = echarts.init(aiplChartRef.value)
  }
  
  aiplChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['A(认知)', 'I(兴趣)', 'P(购买)', 'L(忠诚)'] },
    xAxis: {
      type: 'category',
      data: ['Day1', 'Day2', 'Day3', 'Day4', 'Day5', 'Day6', 'Day7']
    },
    yAxis: { type: 'value' },
    series: [
      { name: 'A(认知)', type: 'line', data: [1000, 1200, 1500, 1300, 1600, 1400, 1700] },
      { name: 'I(兴趣)', type: 'line', data: [500, 600, 750, 650, 800, 700, 850] },
      { name: 'P(购买)', type: 'line', data: [100, 120, 150, 130, 160, 140, 170] },
      { name: 'L(忠诚)', type: 'line', data: [50, 60, 75, 65, 80, 70, 85] }
    ]
  })
}

const renderMatrixChart = () => {
  if (!matrixChartRef.value) return
  if (!matrixChart) {
    matrixChart = echarts.init(matrixChartRef.value)
  }
  
  const matrixData = efficiencyMatrix.value.length > 0 ? efficiencyMatrix.value : [
    { crowd_name: '人群1', tier: 'S', bid_ratio: 1.2, asset_roi: 2.5, scale: 10000 },
    { crowd_name: '人群2', tier: 'A', bid_ratio: 1.5, asset_roi: 3.2, scale: 8000 },
    { crowd_name: '人群3', tier: 'B', bid_ratio: 0.9, asset_roi: 1.8, scale: 15000 },
    { crowd_name: '人群4', tier: 'S', bid_ratio: 1.8, asset_roi: 4.1, scale: 5000 },
    { crowd_name: '人群5', tier: 'A', bid_ratio: 1.4, asset_roi: 2.9, scale: 12000 }
  ]
  
  const tierColors = { 'S': '#f56c6c', 'A': '#e6a23c', 'B': '#909399' }
  
  matrixChart.setOption({
    tooltip: { 
      trigger: 'item',
      formatter: (params) => {
        const item = matrixData[params.dataIndex]
        return `${item.crowd_name}<br/>层级: ${item.tier}<br/>ROI: ${item.asset_roi}<br/>出价系数: ${item.bid_ratio}`
      }
    },
    xAxis: { type: 'value', name: 'ROI', min: 0 },
    yAxis: { type: 'value', name: '出价系数', min: 0 },
    series: [
      {
        type: 'scatter',
        data: matrixData.map(item => ({
          value: [item.asset_roi, item.bid_ratio, item.scale],
          itemStyle: { color: tierColors[item.tier] || '#409EFF' }
        })),
        symbolSize: function (val) {
          return Math.sqrt(val[2]) / 8
        },
        label: {
          show: false
        }
      }
    ]
  })
}

onMounted(() => {
  refresh()
  handleResize = () => {
    aiplChart?.resize()
    matrixChart?.resize()
  }
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  aiplChart?.dispose()
  matrixChart?.dispose()
})
</script>

<style scoped>
.crowd-asset-container {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.summary-cards {
  margin-bottom: 20px;
}

.stat-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.stat-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #333;
}

.chart-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-header h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.chart-container {
  height: 350px;
}

.crowd-list {
  max-height: 350px;
  overflow-y: auto;
}

.crowd-item {
  padding: 16px;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.crowd-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.crowd-name {
  font-weight: 500;
}

.metric {
  color: #409EFF;
  font-weight: 500;
}
</style>

