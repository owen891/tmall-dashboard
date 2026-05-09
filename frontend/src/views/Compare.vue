<template>
  <div class="page-container compare-page">
    <div class="header">
      <h2>同比数据对比</h2>
      <div class="controls">
        <el-select v-model="dimension" @change="loadData" style="width: 120px">
          <el-option label="按周" value="weekly" />
          <el-option label="按月" value="monthly" />
        </el-select>
      </div>
    </div>

    <el-card class="period-info" v-loading="loading">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="当期周期">
          <el-tag type="primary">{{ compareData.current_period?.period }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="对比周期">
          <el-tag type="info">{{ compareData.previous_period?.period }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="同比增长">
          <el-tag :type="compareData.comparison?.payment?.status === 'up' ? 'success' : 'danger'">
            {{ compareData.comparison?.payment?.change_percent > 0 ? '+' : '' }}{{ compareData.comparison?.payment?.change_percent || 0 }}%
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-row :gutter="20" class="kpi-cards" v-loading="loading">
      <el-col :span="12">
        <el-card class="kpi-card">
          <template #header>
            <span>销售额对比</span>
          </template>
          <div class="comparison-content">
            <div class="comparison-values">
              <div class="current">
                <div class="label">当期</div>
                <div class="value">¥{{ formatNumber(compareData.current_period?.payment) }}</div>
              </div>
              <div class="arrow">
                <el-icon><Right /></el-icon>
              </div>
              <div class="previous">
                <div class="label">去年同期</div>
                <div class="value">¥{{ formatNumber(compareData.previous_period?.payment) }}</div>
              </div>
            </div>
            <div class="change" :class="compareData.comparison?.payment?.status">
              <span v-if="compareData.comparison?.payment?.change_percent > 0">↑</span>
              <span v-else-if="compareData.comparison?.payment?.change_percent < 0">↓</span>
              {{ Math.abs(compareData.comparison?.payment?.change_percent || 0) }}%
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="kpi-card">
          <template #header>
            <span>访客数对比</span>
          </template>
          <div class="comparison-content">
            <div class="comparison-values">
              <div class="current">
                <div class="label">当期</div>
                <div class="value">{{ formatNumber(compareData.current_period?.visitors) }}</div>
              </div>
              <div class="arrow">
                <el-icon><Right /></el-icon>
              </div>
              <div class="previous">
                <div class="label">去年同期</div>
                <div class="value">{{ formatNumber(compareData.previous_period?.visitors) }}</div>
              </div>
            </div>
            <div class="change" :class="compareData.comparison?.visitors?.status">
              <span v-if="compareData.comparison?.visitors?.change_percent > 0">↑</span>
              <span v-else-if="compareData.comparison?.visitors?.change_percent < 0">↓</span>
              {{ Math.abs(compareData.comparison?.visitors?.change_percent || 0) }}%
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="charts-row">
      <el-col :span="16">
        <el-card v-loading="loading">
          <template #header>
            <span>同比趋势对比</span>
          </template>
          <div ref="trendChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card v-loading="loading">
          <template #header>
            <span>指标变化率</span>
          </template>
          <div ref="changeChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-card v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>商品同比变化 TOP20</span>
          <ExportButton :data="productComparisons" :columns="exportColumns" filename="同比对比" />
        </div>
      </template>
      <el-table :data="productComparisons" stripe empty-text="暂无对比数据">
        <el-table-column prop="product_id" label="商品ID" width="120" />
        <el-table-column prop="title" label="商品名称" min-width="200" />
        <el-table-column prop="tier" label="分层" width="100">
          <template #default="{ row }">
            <el-tag :type="getTierType(row.tier)">{{ row.tier }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="当期" align="center">
          <el-table-column prop="current_value" label="数值" align="right">
            <template #default="{ row }">
              {{ formatNumber(row.current_value) }}
            </template>
          </el-table-column>
        </el-table-column>
        <el-table-column label="去年同期" align="center">
          <el-table-column prop="previous_value" label="数值" align="right">
            <template #default="{ row }">
              {{ formatNumber(row.previous_value) }}
            </template>
          </el-table-column>
        </el-table-column>
        <el-table-column prop="comparison.change_percent" label="同比变化" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="getChangeType(row.comparison?.change_percent)">
              {{ row.comparison?.change_percent > 0 ? '+' : '' }}{{ row.comparison?.change_percent || 0 }}%
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import ExportButton from '@/components/ExportButton.vue'
import { Right } from '@element-plus/icons-vue'
import { formatNumber, getTierType } from '@/utils/format'
import { useChartManager } from '@/composables/useChartManager'

const chartManager = useChartManager()
const trendChartRef = ref(null)
const changeChartRef = ref(null)

const dimension = ref('monthly')
const loading = ref(true)
const compareData = ref({})
const productComparisons = ref([])
const trends = ref([])

const exportColumns = [
  { key: 'product_id', label: '商品ID' },
  { key: 'title', label: '商品名称' },
  { key: 'tier', label: '分层' },
  { key: 'current_value', label: '当期数值' },
  { key: 'previous_value', label: '去年同期' },
  { key: 'change_percent', label: '同比变化' },
]

const getChangeType = (percent) => {
  if (!percent) return 'info'
  return percent > 0 ? 'success' : 'danger'
}

const loadData = async () => {
  loading.value = true
  try {
    const params = { dimension: dimension.value }

    const [compareRes, productsRes, trendsRes] = await Promise.all([
      api.getCompareSummary(params),
      api.getCompareProducts({ ...params, limit: 20 }),
      api.getCompareTrends({ ...params, periods: 12 })
    ])

    compareData.value = compareRes.data || {}
    productComparisons.value = productsRes.data?.products || []
    trends.value = trendsRes.data?.trends || []

    nextTick(() => {
      initTrendChart()
      initChangeChart()
    })
  } catch (error) {
    ElMessage.error('加载对比数据失败')
    console.error('Load data error:', error)
    compareData.value = {}
    productComparisons.value = []
    trends.value = []
  } finally {
    loading.value = false
  }
}

const initTrendChart = () => {
  if (!trendChartRef.value) return

  if (trends.value.length === 0) {
    chartManager.showEmpty(trendChartRef, '暂无趋势数据')
    return
  }

  chartManager.initChart(trendChartRef)

  const periods = trends.value.map(t => t?.period)
  const currentPayments = trends.value.map(t => t?.current?.payment || 0)
  const previousPayments = trends.value.map(t => t?.previous?.payment || 0)

  chartManager.setOption(trendChartRef, {
    tooltip: { trigger: 'axis' },
    legend: { data: ['当期', '去年同期'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
    xAxis: { type: 'category', data: periods },
    yAxis: { type: 'value', name: '销售额(元)' },
    series: [
      { name: '当期', type: 'bar', data: currentPayments, itemStyle: { color: '#409eff' } },
      { name: '去年同期', type: 'bar', data: previousPayments, itemStyle: { color: '#909399' } }
    ]
  })
}

const initChangeChart = () => {
  if (!changeChartRef.value) return

  const metrics = ['payment', 'refund', 'visitors', 'conversion', 'ad_spend']
  const labels = ['销售额', '退款额', '访客', '转化率', '广告支出']
  const changes = metrics.map(m => compareData.value.comparison?.[m]?.change_percent || 0)

  const hasData = changes.some(c => c !== 0)
  if (!hasData) {
    chartManager.showEmpty(changeChartRef, '暂无变化数据')
    return
  }

  chartManager.initChart(changeChartRef)
  chartManager.setOption(changeChartRef, {
    tooltip: { trigger: 'axis', formatter: '{b}: {c}%' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'value', name: '变化率(%)' },
    yAxis: { type: 'category', data: labels },
    series: [{
      type: 'bar',
      data: changes.map(c => ({
        value: c,
        itemStyle: { color: c >= 0 ? '#67c23a' : '#f56c6c' }
      })),
      label: { show: true, formatter: '{c}%' }
    }]
  })
}

onMounted(() => {
  loadData()
  chartManager.setupResize()
})
</script>

<style scoped>
.compare-page {
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

.period-info {
  margin-bottom: 20px;
}

.kpi-cards {
  margin-bottom: 20px;
}

.comparison-content {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.comparison-values {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.current, .previous {
  flex: 1;
  text-align: center;
}

.current .label, .previous .label {
  font-size: 12px;
  color: #909399;
}

.current .value {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.previous .value {
  font-size: 24px;
  font-weight: bold;
  color: #909399;
}

.arrow {
  font-size: 24px;
  color: #c0c4cc;
}

.change {
  text-align: center;
  font-size: 28px;
  font-weight: bold;
}

.change.up {
  color: #67c23a;
}

.change.down {
  color: #f56c6c;
}

.change.stable {
  color: #909399;
}

.charts-row {
  margin-bottom: 20px;
}

.chart-container {
  height: 300px;
}
</style>
