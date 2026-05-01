<template>
  <div class="ads-container">
    <div class="header">
      <h2>广告分析</h2>
    </div>

    <el-row :gutter="20" class="summary-cards">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ formatNumber(summary.total_spend) }}</div>
          <div class="stat-label">总花费</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ formatNumber(summary.total_gmv) }}</div>
          <div class="stat-label">总GMV</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ summary.avg_roi }}</div>
          <div class="stat-label">平均ROI</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ summary.total_clicks }}</div>
          <div class="stat-label">总点击</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="chart-card">
      <template #header>
        <span>渠道对比</span>
      </template>
      <div ref="chartRef" style="width: 100%; height: 350px;"></div>
    </el-card>

    <el-card class="products-card">
      <template #header>
        <span>商品广告排名</span>
      </template>
      <el-table :data="productAds" stripe>
        <el-table-column prop="product_name" label="商品" />
        <el-table-column prop="channel" label="渠道" />
        <el-table-column prop="spend" label="花费">
          <template #default="{ row }">
            {{ formatNumber(row.spend) }}
          </template>
        </el-table-column>
        <el-table-column prop="gmv" label="GMV">
          <template #default="{ row }">
            {{ formatNumber(row.gmv) }}
          </template>
        </el-table-column>
        <el-table-column prop="clicks" label="点击" />
        <el-table-column prop="roi" label="ROI" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/api'
import * as echarts from 'echarts'

const chartRef = ref(null)
let chart = null

const summary = ref({
  total_spend: 0,
  total_gmv: 0,
  avg_roi: 0,
  total_clicks: 0
})
const channelComparison = ref([])
const productAds = ref([])

const loadAds = async () => {
  try {
    const [summaryRes, compRes, productsRes] = await Promise.all([
      api.get('/ads/summary'),
      api.get('/ads/comparison'),
      api.get('/ads/products')
    ])
    
    if (summaryRes.code === 200 || summaryRes.data) {
      summary.value = summaryRes.data || summaryRes
    }
    
    if (compRes.code === 200 || compRes.data) {
      channelComparison.value = compRes.data || []
      updateChart()
    }
    
    if (productsRes.code === 200 || productsRes.data) {
      productAds.value = productsRes.data || []
    }
  } catch (error) {
    console.error('加载广告数据失败:', error)
  }
}

const updateChart = () => {
  if (!chart) return

  const channels = channelComparison.value.map(c => c.channel)
  const spendData = channelComparison.value.map(c => c.spend)
  const gmvData = channelComparison.value.map(c => c.gmv)
  const roiData = channelComparison.value.map(c => c.roi)

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['花费', 'GMV', 'ROI'] },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: channels },
    yAxis: [
      { type: 'value', name: '金额' },
      { type: 'value', name: 'ROI', min: 0 }
    ],
    series: [
      { name: '花费', type: 'bar', data: spendData },
      { name: 'GMV', type: 'bar', data: gmvData },
      { name: 'ROI', type: 'line', data: roiData, yAxisIndex: 1 }
    ]
  })
}

const formatNumber = (num) => {
  if (!num) return '0'
  if (num >= 10000) return (num / 10000).toFixed(2) + '万'
  return num.toFixed(2)
}

onMounted(() => {
  chart = echarts.init(chartRef.value)
  loadAds()
  window.addEventListener('resize', () => chart?.resize())
})

onUnmounted(() => {
  chart?.dispose()
})
</script>

<style scoped>
.ads-container {
  padding: 20px;
}

.header {
  margin-bottom: 20px;
}

.header h2 {
  margin: 0;
}

.summary-cards {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.stat-label {
  color: #909399;
  margin-top: 8px;
}

.chart-card,
.products-card {
  margin-bottom: 20px;
}
</style>
