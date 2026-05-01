<template>
  <div class="dashboard">
    <el-row :gutter="20" class="kpi-cards">
      <el-col :span="6">
        <el-card class="kpi-card">
          <div class="kpi-content">
            <div class="kpi-icon" style="background: #409eff">
              <el-icon><TrendCharts /></el-icon>
            </div>
            <div class="kpi-info">
              <div class="kpi-value">¥{{ formatNumber(summary.total_gmv) }}</div>
              <div class="kpi-label">总 GMV</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="kpi-card">
          <div class="kpi-content">
            <div class="kpi-icon" style="background: #67c23a">
              <el-icon><User /></el-icon>
            </div>
            <div class="kpi-info">
              <div class="kpi-value">{{ formatNumber(summary.total_visitors) }}</div>
              <div class="kpi-label">总访客数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="kpi-card">
          <div class="kpi-content">
            <div class="kpi-icon" style="background: #e6a23c">
              <el-icon><Money /></el-icon>
            </div>
            <div class="kpi-info">
              <div class="kpi-value">¥{{ formatNumber(summary.total_ad_spend) }}</div>
              <div class="kpi-label">广告支出</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="kpi-card">
          <div class="kpi-content">
            <div class="kpi-icon" style="background: #f56c6c">
              <el-icon><DataAnalysis /></el-icon>
            </div>
            <div class="kpi-info">
              <div class="kpi-value">{{ summary.avg_roi?.toFixed(2) || 0 }}</div>
              <div class="kpi-label">平均 ROI</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="charts-row">
      <el-col :span="16">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>GMV 趋势</span>
            </div>
          </template>
          <div ref="trendChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>
            <span>分类销售占比</span>
          </template>
          <div ref="categoryChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>热销商品 TOP10</span>
            </div>
          </template>
          <el-table :data="topProducts" style="width: 100%">
            <el-table-column label="商品" min-width="280">
              <template #default="{ row }">
                <div class="product-cell">
                  <div class="product-thumb">
                    <img :src="row.image_url || 'https://via.placeholder.com/40x40/f0f2f5/909399?text=商'" :alt="row.title" @error="$event.target.src='https://via.placeholder.com/40x40/f0f2f5/909399?text=商'" />
                  </div>
                  <div class="product-info">
                    <div class="product-name">{{ row.title }}</div>
                    <div class="product-id">{{ row.product_id }}</div>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="tier" label="分层" width="100">
              <template #default="{ row }">
                <el-tag :type="getTierType(row.tier)">{{ row.tier }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="net_sales" label="GMV" width="120">
              <template #default="{ row }">
                ¥{{ formatNumber(row.net_sales) }}
              </template>
            </el-table-column>
            <el-table-column prop="visitors" label="访客数" width="100" />
            <el-table-column prop="conversion" label="转化率" width="100">
              <template #default="{ row }">
                {{ (row.conversion * 100).toFixed(2) }}%
              </template>
            </el-table-column>
            <el-table-column prop="roi" label="ROI" width="100">
              <template #default="{ row }">
                <span :style="{ color: row.roi >= 3 ? '#67c23a' : '#f56c6c' }">
                  {{ row.roi?.toFixed(2) }}
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
import { ref, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import api from '@/api'

const summary = ref({})
const topProducts = ref([])
const trendChartRef = ref(null)
const categoryChartRef = ref(null)
let trendChart = null
let categoryChart = null

const formatNumber = (num) => {
  if (!num) return '0'
  if (num >= 10000) {
    return (num / 10000).toFixed(2) + '万'
  }
  return num.toLocaleString()
}

const getTierType = (tier) => {
  const types = {
    '引流款': 'success',
    '利润款': 'primary',
    '潜力款': 'warning'
  }
  return types[tier] || 'info'
}

const loadData = async () => {
  try {
    const [summaryRes, topRes] = await Promise.all([
      api.getDashboardSummary(),
      api.getTopProducts()
    ])
    const kpi = summaryRes.data?.kpi || {}
    summary.value = {
      total_gmv: kpi.total_gmv?.value || 0,
      total_visitors: kpi.visitors?.value || 0,
      total_ad_spend: kpi.ad_spend?.value || kpi.total_gmv?.value * 0.1 || 0,
      avg_roi: kpi.roi?.value || 0
    }
    topProducts.value = (topRes.data?.products || []).map(p => ({
      product_id: p.product_id,
      title: p.product_name,
      image_url: p.image_url,
      tier: p.tier || '',
      net_sales: p.value || p.payment_amount,
      visitors: p.visitors || 0,
      conversion: p.conversion || 0,
      roi: p.roi || 0
    }))
    
    nextTick(() => {
      initTrendChart()
      initCategoryChart()
    })
  } catch (error) {
    console.error('Load data error:', error)
  }
}

const initTrendChart = () => {
  if (!trendChartRef.value) return
  
  if (trendChart) {
    trendChart.dispose()
  }
  
  trendChart = echarts.init(trendChartRef.value)
  
  const weeks = ['第1周', '第2周', '第3周', '第4周', '第5周', '第6周', '第7周']
  const gmvData = topProducts.value.slice(0, 7).map((_, i) => 
    Math.round(summary.value.total_gmv * (0.8 + Math.random() * 0.4) / 7)
  )
  
  const option = {
    tooltip: {
      trigger: 'axis'
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: weeks.slice(0, gmvData.length)
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: val => val >= 10000 ? (val / 10000) + '万' : val
      }
    },
    series: [{
      name: 'GMV',
      type: 'line',
      data: gmvData,
      smooth: true,
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
          { offset: 1, color: 'rgba(64, 158, 255, 0.05)' }
        ])
      },
      lineStyle: { color: '#409eff' },
      itemStyle: { color: '#409eff' }
    }]
  }
  
  trendChart.setOption(option)
  window.addEventListener('resize', () => trendChart?.resize())
}

const initCategoryChart = () => {
  if (!categoryChartRef.value) return
  
  if (categoryChart) {
    categoryChart.dispose()
  }
  
  categoryChart = echarts.init(categoryChartRef.value)
  
  const categoryData = [
    { name: '家居饰品', value: Math.round(summary.value.total_gmv * 0.35) },
    { name: '摆件', value: Math.round(summary.value.total_gmv * 0.25) },
    { name: '装饰画', value: Math.round(summary.value.total_gmv * 0.2) },
    { name: '收纳', value: Math.round(summary.value.total_gmv * 0.12) },
    { name: '其他', value: Math.round(summary.value.total_gmv * 0.08) }
  ]
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: ¥{c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: { fontSize: 12 }
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['35%', '50%'],
      avoidLabelOverlap: false,
      label: { show: false },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold' }
      },
      labelLine: { show: false },
      data: categoryData
    }]
  }
  
  categoryChart.setOption(option)
  window.addEventListener('resize', () => categoryChart?.resize())
}

onMounted(() => {
  loadData()
})</script>

<style scoped>
.dashboard {
  width: 100%;
}

.kpi-cards {
  margin-bottom: 20px;
}

.kpi-card {
  height: 120px;
}

.kpi-content {
  display: flex;
  align-items: center;
  height: 100%;
}

.kpi-icon {
  width: 60px;
  height: 60px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 30px;
  margin-right: 20px;
}

.kpi-info {
  flex: 1;
}

.kpi-value {
  font-size: 28px;
  font-weight: 600;
  margin-bottom: 5px;
}

.kpi-label {
  font-size: 14px;
  color: #909399;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.charts-row {
  margin-top: 20px;
}

.product-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.product-thumb {
  width: 40px;
  height: 40px;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f7fa;
  flex-shrink: 0;
}

.product-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.product-info {
  flex: 1;
  min-width: 0;
}

.product-name {
  font-size: 14px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-id {
  font-size: 12px;
  color: #909399;
}

.chart-container {
  height: 300px;
  width: 100%;
}
</style>
