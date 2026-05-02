<template>
  <div class="crowd-asset-container">
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

const loading = ref(false)
const aiplChartRef = ref(null)
const matrixChartRef = ref(null)
let aiplChart = null
let matrixChart = null

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
    const response = await fetch('/api/crowd-asset/dashboard')
    if (response.ok) {
      const data = await response.json()
      Object.assign(summary, data.summary)
      topCrowds.value = data.top_crowds || []
      renderCharts()
    }
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const formatNumber = (num) => {
  if (num >= 100000000) return (num / 100000000).toFixed(1) + '亿'
  if (num >= 10000) return (num / 10000).toFixed(1) + '万'
  return num?.toLocaleString() || '0'
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
  
  matrixChart.setOption({
    tooltip: { trigger: 'item' },
    xAxis: { type: 'value', name: 'ROI' },
    yAxis: { type: 'value', name: '出价系数' },
    series: [
      {
        type: 'scatter',
        data: [
          [2.5, 1.2, 10000],
          [3.2, 1.5, 8000],
          [1.8, 0.9, 15000],
          [4.1, 1.8, 5000],
          [2.9, 1.4, 12000]
        ],
        symbolSize: function (val) {
          return Math.sqrt(val[2]) / 5
        }
      }
    ]
  })
}

onMounted(() => {
  refresh()
})

onBeforeUnmount(() => {
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

