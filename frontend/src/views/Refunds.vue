<template>
  <div class="refunds-container page-container">
    <div class="header">
      <h2>退款分析</h2>
      <div class="dimension-selector">
        <el-radio-group v-model="dimension" @change="loadData">
          <el-radio-button label="daily">日</el-radio-button>
          <el-radio-button label="weekly">周</el-radio-button>
          <el-radio-button label="monthly">月</el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <el-row :gutter="20" class="summary-cards">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ summary.total_refund_count }}</div>
          <div class="stat-label">退款笔数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ formatNumber(summary.total_refund_amount) }}</div>
          <div class="stat-label">退款金额</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ summary.avg_refund_rate }}%</div>
          <div class="stat-label">平均退款率</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ summary.avg_refund_days }}</div>
          <div class="stat-label">平均退款周期(天)</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="chart-card">
      <template #header>
        <span>退款率趋势</span>
      </template>
      <div ref="chartRef" style="width: 100%; height: 300px;"></div>
    </el-card>

    <el-card class="alerts-card">
      <template #header>
        <div class="card-header">
          <span>高风险商品</span>
          <el-button size="small" @click="loadAlerts">刷新告警</el-button>
        </div>
      </template>
      <el-table :data="alerts" stripe>
        <el-table-column prop="product_name" label="商品" />
        <el-table-column prop="refund_rate" label="退款率(%)">
          <template #default="{ row }">
            <el-tag :type="row.severity === 'critical' ? 'danger' : 'warning'">
              {{ row.refund_rate }}%
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="refund_count" label="退款笔数" />
        <el-table-column prop="refund_amount" label="退款金额">
          <template #default="{ row }">
            {{ formatNumber(row.refund_amount) }}
          </template>
        </el-table-column>
        <el-table-column prop="avg_refund_days" label="平均退款天数" />
        <el-table-column prop="risk_level" label="风险等级">
          <template #default="{ row }">
            <el-tag :type="row.risk_level === 'high' ? 'danger' : 'warning'">
              {{ row.risk_level === 'high' ? '高' : '中' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="reasons-card">
      <template #header>
        <span>退款原因分布</span>
      </template>
      <el-table :data="reasons" stripe>
        <el-table-column prop="reason" label="退款原因" />
        <el-table-column prop="count" label="次数" />
        <el-table-column prop="percentage" label="占比(%)" />
        <el-table-column prop="avg_amount" label="平均金额">
          <template #default="{ row }">
            {{ formatNumber(row.avg_amount) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/api'
import * as echarts from 'echarts'
import { formatNumber } from '@/utils/format'

const chartRef = ref(null)
let chart = null
let handleResize = null

const dimension = ref('weekly')
const summary = ref({
  total_refund_count: 0,
  total_refund_amount: 0,
  avg_refund_rate: 0,
  avg_refund_days: 0,
  top_risk_products: []
})
const trends = ref([])
const alerts = ref([])
const reasons = ref([])

const loadData = async () => {
  try {
    const [summaryRes, trendsRes, reasonsRes] = await Promise.all([
      api.get('/refunds/summary', { params: { dimension: dimension.value } }),
      api.get('/refunds/trends', { params: { dimension: dimension.value } }),
      api.get('/refunds/reasons')
    ])
    
    if (summaryRes.code === 200 || summaryRes.data) {
      summary.value = summaryRes.data || summaryRes
      alerts.value = summaryRes.data?.top_risk_products || []
    }
    
    if (trendsRes.code === 200 || trendsRes.data) {
      trends.value = trendsRes.data?.trends || trendsRes.data || []
      updateChart()
    }
    
    if (reasonsRes.code === 200 || reasonsRes.data) {
      reasons.value = reasonsRes.data || []
    }
  } catch (error) {
    console.error('加载退款数据失败:', error)
  }
}

const loadAlerts = async () => {
  try {
    const res = await api.get('/refunds/alerts', { params: { threshold: 5 } })
    if (res.code === 200 || res.data) {
      const alertData = res.data || []
      alerts.value = alertData.map(a => ({
        product_name: a.product_name,
        refund_rate: a.refund_rate,
        refund_count: 0,
        refund_amount: 0,
        avg_refund_days: 0,
        risk_level: a.severity === 'critical' ? 'high' : 'medium'
      }))
    }
  } catch (error) {
    console.error('加载告警失败:', error)
  }
}

const updateChart = () => {
  if (!chart) return

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['退款率(%)', '退款金额'] },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: trends.value.map(t => t.date) },
    yAxis: [
      { type: 'value', name: '退款率(%)' },
      { type: 'value', name: '退款金额' }
    ],
    series: [
      { name: '退款率(%)', type: 'line', data: trends.value.map(t => t.refund_rate) },
      { name: '退款金额', type: 'bar', data: trends.value.map(t => t.refund_amount) }
    ]
  })
}

onMounted(() => {
  chart = echarts.init(chartRef.value)
  loadData()
  loadAlerts()
  handleResize = () => chart?.resize()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})
</script>

<style scoped>
.refunds-container {
  padding: 20px;
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

.summary-cards {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #f56c6c;
}

.stat-label {
  color: #909399;
  margin-top: 8px;
}

.chart-card,
.alerts-card,
.reasons-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
