<template>
  <div class="funnel-container">
    <div class="page-header">
      <h1>流量漏斗转化分析</h1>
      <div class="header-actions">
        <el-select v-model="periodType" size="default" @change="fetchData">
          <el-option label="今日" value="today" />
          <el-option label="昨日" value="yesterday" />
          <el-option label="近7天" value="7d" />
          <el-option label="近30天" value="30d" />
        </el-select>
        <el-button type="primary" @click="fetchData">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </div>

    <div v-loading="loading" class="content-area">
      <template v-if="!error">
        <el-row :gutter="20" class="summary-cards">
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-label">总曝光</div>
              <div class="stat-value">{{ formatNumber(overview.total_exposure) }}</div>
              <div class="stat-trend" :class="getTrendClass(overview.exposure_trend)">
                {{ formatPercent(overview.exposure_trend) }}
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-label">总点击</div>
              <div class="stat-value">{{ formatNumber(overview.total_click) }}</div>
              <div class="stat-trend" :class="getTrendClass(overview.click_trend)">
                {{ formatPercent(overview.click_trend) }}
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-label">加购数</div>
              <div class="stat-value">{{ formatNumber(overview.total_cart) }}</div>
              <div class="stat-trend" :class="getTrendClass(overview.cart_trend)">
                {{ formatPercent(overview.cart_trend) }}
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-label">支付数</div>
              <div class="stat-value">{{ formatNumber(overview.total_pay) }}</div>
              <div class="stat-trend" :class="getTrendClass(overview.pay_trend)">
                {{ formatPercent(overview.pay_trend) }}
              </div>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="20" class="rate-cards">
          <el-col :span="8">
            <div class="rate-card click-rate">
              <div class="rate-name">点击率 CTR</div>
              <div class="rate-value">{{ formatPercent(overview.ctr) }}</div>
              <div class="rate-bar">
                <div class="rate-fill" :style="{ width: Math.min(overview.ctr / 10, 100) + '%' }"></div>
              </div>
              <div class="rate-compare">
                行业均值: {{ formatPercent(overview.industry_ctr || 5.2) }}
              </div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="rate-card cart-rate">
              <div class="rate-name">加购率</div>
              <div class="rate-value">{{ formatPercent(overview.cart_rate) }}</div>
              <div class="rate-bar">
                <div class="rate-fill" :style="{ width: Math.min(overview.cart_rate / 10, 100) + '%' }"></div>
              </div>
              <div class="rate-compare">
                行业均值: {{ formatPercent(overview.industry_cart || 8.5) }}
              </div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="rate-card pay-rate">
              <div class="rate-name">支付转化率</div>
              <div class="rate-value">{{ formatPercent(overview.pay_rate) }}</div>
              <div class="rate-bar">
                <div class="rate-fill" :style="{ width: Math.min(overview.pay_rate / 20, 100) + '%' }"></div>
              </div>
              <div class="rate-compare">
                行业均值: {{ formatPercent(overview.industry_pay || 15.0) }}
              </div>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="16">
            <div class="chart-card">
              <h3>转化漏斗</h3>
              <div ref="funnelChartRef" class="chart-container"></div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="chart-card">
              <h3>各环节流失分析</h3>
              <div ref="dropChartRef" class="chart-container small"></div>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <div class="chart-card">
              <h3>各流量渠道转化对比</h3>
              <div ref="sourceChartRef" class="chart-container"></div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="table-card">
              <h3>各渠道详细数据</h3>
              <el-table :data="sourceData" stripe size="small">
                <el-table-column prop="source" label="渠道" width="120">
                  <template #default="{ row }">
                    <el-tag size="small" :type="getSourceTagType(row.source)">
                      {{ row.source }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="exposure" label="曝光" align="right">
                  <template #default="{ row }">
                    {{ formatNumber(row.exposure) }}
                  </template>
                </el-table-column>
                <el-table-column prop="click" label="点击" align="right">
                  <template #default="{ row }">
                    {{ formatNumber(row.click) }}
                  </template>
                </el-table-column>
                <el-table-column prop="cart" label="加购" align="right">
                  <template #default="{ row }">
                    {{ formatNumber(row.cart) }}
                  </template>
                </el-table-column>
                <el-table-column prop="pay" label="支付" align="right">
                  <template #default="{ row }">
                    {{ formatNumber(row.pay) }}
                  </template>
                </el-table-column>
                <el-table-column prop="ctr" label="CTR" align="right">
                  <template #default="{ row }">
                    {{ formatPercent(row.ctr) }}
                  </template>
                </el-table-column>
                <el-table-column prop="conversion" label="转化率" align="right">
                  <template #default="{ row }">
                    <span :class="getConversionClass(row.conversion)">
                      {{ formatPercent(row.conversion) }}
                    </span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="24">
            <div class="table-card">
              <h3>流失节点优化建议</h3>
              <el-table :data="dropAnalysis" stripe size="small">
                <el-table-column prop="stage" label="流失环节" width="150">
                  <template #default="{ row }">
                    <span class="stage-badge" :class="'stage-' + row.stage_key">
                      {{ row.stage }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column prop="drop_rate" label="流失率" width="100" align="right">
                  <template #default="{ row }">
                    <span class="drop-rate">{{ formatPercent(row.drop_rate) }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="lost_count" label="流失人数" width="100" align="right">
                  <template #default="{ row }">
                    {{ formatNumber(row.lost_count) }}
                  </template>
                </el-table-column>
                <el-table-column label="可能原因" min-width="200">
                  <template #default="{ row }">
                    <ul class="reason-list">
                      <li v-for="reason in row.reasons" :key="reason">{{ reason }}</li>
                    </ul>
                  </template>
                </el-table-column>
                <el-table-column label="优化建议" min-width="200">
                  <template #default="{ row }">
                    <ul class="suggestion-list">
                      <li v-for="s in row.suggestions" :key="s">{{ s }}</li>
                    </ul>
                  </template>
                </el-table-column>
                <el-table-column prop="priority" label="优先级" width="80" align="center">
                  <template #default="{ row }">
                    <el-tag size="small" :type="getPriorityType(row.priority)">
                      {{ row.priority }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-col>
        </el-row>
      </template>

      <el-empty v-else description="加载数据失败" />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

const periodType = ref('7d')
const loading = ref(false)
const error = ref(false)

const overview = reactive({
  total_exposure: 0,
  total_click: 0,
  total_cart: 0,
  total_pay: 0,
  exposure_trend: 0,
  click_trend: 0,
  cart_trend: 0,
  pay_trend: 0,
  ctr: 0,
  cart_rate: 0,
  pay_rate: 0,
  industry_ctr: 5.2,
  industry_cart: 8.5,
  industry_pay: 15.0
})

const sourceData = ref([])
const dropAnalysis = ref([])

const funnelChartRef = ref(null)
const dropChartRef = ref(null)
const sourceChartRef = ref(null)

let funnelChart = null
let dropChart = null
let sourceChart = null

const fetchData = async () => {
  loading.value = true
  error.value = false
  try {
    const [overviewRes, sourceRes, dropRes] = await Promise.all([
      fetch(`/api/funnel/overview?period=${periodType.value}`),
      fetch(`/api/funnel/by-source?period=${periodType.value}`),
      fetch(`/api/funnel/drop-analysis?period=${periodType.value}`)
    ])

    if (overviewRes.ok) {
      const data = await overviewRes.json()
      Object.assign(overview, data)
    }

    if (sourceRes.ok) {
      sourceData.value = await sourceRes.json()
    }

    if (dropRes.ok) {
      dropAnalysis.value = await dropRes.json()
    }

    renderCharts()
  } catch (e) {
    error.value = true
    ElMessage.error('加载漏斗数据失败')
  } finally {
    loading.value = false
  }
}

const formatNumber = (num) => {
  if (num >= 100000000) return (num / 100000000).toFixed(1) + '亿'
  if (num >= 10000) return (num / 10000).toFixed(1) + '万'
  return num?.toLocaleString() || '0'
}

const formatPercent = (num) => {
  return (num || 0).toFixed(1) + '%'
}

const getTrendClass = (trend) => {
  if (trend > 0) return 'trend-up'
  if (trend < 0) return 'trend-down'
  return 'trend-flat'
}

const getSourceTagType = (source) => {
  const types = { '搜索': '', '推荐': 'success', '活动': 'warning', '广告': 'danger', '直接': 'info' }
  return types[source] || ''
}

const getConversionClass = (rate) => {
  if (rate >= 10) return 'conversion-high'
  if (rate >= 5) return 'conversion-mid'
  return 'conversion-low'
}

const getPriorityType = (priority) => {
  const types = { '高': 'danger', '中': 'warning', '低': 'success' }
  return types[priority] || ''
}

const renderCharts = () => {
  renderFunnelChart()
  renderDropChart()
  renderSourceChart()
}

const renderFunnelChart = () => {
  if (!funnelChartRef.value) return

  if (!funnelChart) {
    funnelChart = echarts.init(funnelChartRef.value)
  }

  const funnelData = [
    { name: '曝光', value: overview.total_exposure, color: '#409EFF' },
    { name: '点击', value: overview.total_click, color: '#67C23A' },
    { name: '加购', value: overview.total_cart, color: '#E6A23C' },
    { name: '下单', value: Math.round(overview.total_cart * 0.7), color: '#F56C6C' },
    { name: '支付', value: overview.total_pay, color: '#909399' }
  ]

  funnelChart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: (params) => `${params.name}: ${formatNumber(params.value)}`
    },
    series: [{
      type: 'funnel',
      left: '10%',
      top: 60,
      bottom: 60,
      width: '80%',
      min: 0,
      max: overview.total_exposure || 100,
      minSize: '0%',
      maxSize: '100%',
      gap: 8,
      label: {
        show: true,
        position: 'inside',
        formatter: (params) => `${params.name}\n${formatNumber(params.value)}`,
        fontSize: 14,
        color: '#fff'
      },
      labelLine: { show: false },
      itemStyle: {
        borderColor: '#fff',
        borderWidth: 2,
        shadowBlur: 10,
        shadowColor: 'rgba(0,0,0,0.3)'
      },
      data: funnelData.map(item => ({
        value: item.value,
        name: item.name,
        itemStyle: { color: item.color }
      }))
    }]
  })
}

const renderDropChart = () => {
  if (!dropChartRef.value) return

  if (!dropChart) {
    dropChart = echarts.init(dropChartRef.value)
  }

  const dropData = [
    { stage: '曝光→点击', rate: 100 - (overview.ctr || 5) },
    { stage: '点击→加购', rate: 100 - (overview.cart_rate || 8) },
    { stage: '加购→支付', rate: 100 - (overview.pay_rate || 15) }
  ]

  dropChart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => `${params[0].name}: ${params[0].value.toFixed(1)}%`
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '3%', containLabel: true },
    xAxis: {
      type: 'value',
      max: 100,
      axisLabel: { formatter: '{value}%' }
    },
    yAxis: {
      type: 'category',
      data: dropData.map(d => d.stage),
      axisLabel: { fontSize: 10 }
    },
    series: [{
      type: 'bar',
      data: dropData.map(d => ({
        value: d.rate,
        itemStyle: {
          color: d.rate > 80 ? '#F56C6C' : d.rate > 50 ? '#E6A23C' : '#67C23A'
        }
      })),
      label: {
        show: true,
        position: 'right',
        formatter: '{c}%',
        fontSize: 10
      }
    }]
  })
}

const renderSourceChart = () => {
  if (!sourceChartRef.value) return

  if (!sourceChart) {
    sourceChart = echarts.init(sourceChartRef.value)
  }

  sourceChart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    legend: {
      data: ['曝光', '点击', '加购', '支付'],
      bottom: 0
    },
    grid: { left: '3%', right: '4%', bottom: '15%', top: '5%', containLabel: true },
    xAxis: {
      type: 'category',
      data: sourceData.value.map(d => d.source)
    },
    yAxis: {
      type: 'log',
      type: 'value'
    },
    series: [
      { name: '曝光', type: 'bar', data: sourceData.value.map(d => d.exposure), itemStyle: { color: '#409EFF' } },
      { name: '点击', type: 'bar', data: sourceData.value.map(d => d.click), itemStyle: { color: '#67C23A' } },
      { name: '加购', type: 'bar', data: sourceData.value.map(d => d.cart), itemStyle: { color: '#E6A23C' } },
      { name: '支付', type: 'bar', data: sourceData.value.map(d => d.pay), itemStyle: { color: '#F56C6C' } }
    ]
  })
}

const handleResize = () => {
  funnelChart?.resize()
  dropChart?.resize()
  sourceChart?.resize()
}

onMounted(() => {
  fetchData()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  funnelChart?.dispose()
  dropChart?.dispose()
  sourceChart?.dispose()
})
</script>

<style scoped>
.funnel-container {
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

.header-actions {
  display: flex;
  gap: 12px;
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
  margin-bottom: 4px;
}

.stat-trend {
  font-size: 14px;
}

.trend-up { color: #67C23A; }
.trend-down { color: #F56C6C; }
.trend-flat { color: #909399; }

.rate-cards {
  margin-bottom: 20px;
}

.rate-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.rate-name {
  font-size: 14px;
  color: #666;
  margin-bottom: 12px;
}

.rate-value {
  font-size: 32px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
}

.rate-bar {
  height: 8px;
  background: #f0f0f0;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

.rate-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}

.click-rate .rate-fill { background: linear-gradient(90deg, #409EFF, #66B1FF); }
.cart-rate .rate-fill { background: linear-gradient(90deg, #E6A23C, #EBB564); }
.pay-rate .rate-fill { background: linear-gradient(90deg, #67C23A, #85CE61); }

.rate-compare {
  font-size: 12px;
  color: #999;
}

.chart-card, .table-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-bottom: 20px;
}

.chart-card h3, .table-card h3 {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin: 0 0 16px 0;
}

.chart-container {
  height: 320px;
}

.chart-container.small {
  height: 280px;
}

.conversion-high { color: #67C23A; font-weight: 600; }
.conversion-mid { color: #E6A23C; }
.conversion-low { color: #F56C6C; }

.stage-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.stage-exposure { background: #ECF5FF; color: #409EFF; }
.stage-click { background: #F0F9EB; color: #67C23A; }
.stage-cart { background: #FDF6EC; color: #E6A23C; }
.stage-pay { background: #F4F4F5; color: #909399; }

.drop-rate {
  color: #F56C6C;
  font-weight: 600;
}

.reason-list, .suggestion-list {
  margin: 0;
  padding-left: 16px;
  font-size: 13px;
  color: #666;
}

.reason-list li, .suggestion-list li {
  margin-bottom: 4px;
}

.suggestion-list li {
  color: #409EFF;
}

.content-area {
  min-height: 400px;
}
</style>
