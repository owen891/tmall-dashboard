<template>
  <div class="command-tower">
    <div class="tower-header">
      <div class="header-left">
        <h1>🎯 六边形指挥塔</h1>
        <span class="subtitle">一站式电商运营作战系统</span>
      </div>
      <div class="header-right">
        <GlobalTimeFilter />
        <el-button type="primary" @click="refresh">
          <el-icon><Refresh /></el-icon>
          刷新数据
        </el-button>
        <el-button @click="$router.push('/advanced-import')">
          <el-icon><Upload /></el-icon>
          快速导入
        </el-button>
      </div>
    </div>

    <CoreIndicators :indicators="coreIndicators" />

    <AlertBar :alerts="alerts" />

    <div class="hexagon-area">
      <div class="hexagon-grid">
        <HexagonCard
          :title="'数据与目标'"
          :icon="'TrendCharts'"
          color="#409eff"
          :stats="[
            { label: 'GMV目标', value: '87%', change: 3.2 },
            { label: '访客数', value: '123,456', change: 8.9 },
            { label: '转化率', value: '3.2%', change: 1.2 }
          ]"
          :actions="[
            { label: '数据概览', type: 'primary' },
            { label: '商品分析', type: '' }
          ]"
          to="/data-goals"
        />

        <HexagonCard
          :title="'实验与资产'"
          :icon="'DataAnalysis'"
          color="#67c23a"
          :stats="[
            { label: '进行中实验', value: '3个', change: 0 },
            { label: 'SOP模板', value: '12个', change: 20 },
            { label: '人群ROI', value: '4.2', change: 3.1 }
          ]"
          :actions="[
            { label: '策略实验', type: 'primary' },
            { label: '人群资产', type: '' }
          ]"
          to="/experiment-asset"
        />

        <HexagonCard
          :title="'执行与监控'"
          :icon="'Monitor'"
          color="#e6a23c"
          :stats="[
            { label: '待处理预警', value: '3个', change: -40 },
            { label: '任务完成率', value: '89%', change: 5.6 },
            { label: '库存健康', value: '89%', change: 3.1 }
          ]"
          :actions="[
            { label: '智能预警', type: 'primary' },
            { label: '人效监控', type: '' }
          ]"
          to="/execute-monitor"
        />

        <HexagonCard
          :title="'工具与系统'"
          :icon="'Setting'"
          color="#f56c6c"
          :stats="[
            { label: '今日导入', value: '12个', change: 15 },
            { label: '备份次数', value: '3次', change: 0 },
            { label: '数据质量', value: '94%', change: 2.5 }
          ]"
          :actions="[
            { label: '数据管理', type: 'primary' },
            { label: '分析工具', type: '' }
          ]"
          to="/tools-system"
        />

        <HexagonCard
          :title="'数据概览'"
          :icon="'Odometer'"
          color="#909399"
          :stats="[
            { label: 'GMV', value: '¥456,789', change: 12.3 },
            { label: '访客数', value: '123,456', change: 8.9 },
            { label: 'ROI', value: '3.87', change: 3.1 }
          ]"
          :actions="[
            { label: '查看详情', type: 'primary' },
            { label: '数据导出', type: '' }
          ]"
          to="/dashboard"
        />

        <HexagonCard
          :title="'商品中心'"
          :icon="'Goods'"
          color="#00bcd4"
          :stats="[
            { label: '热销TOP', value: '87,654元', change: 12.3 },
            { label: '滞销警告', value: '5个', change: -2 },
            { label: '转化率', value: '3.2%', change: 1.2 }
          ]"
          :actions="[
            { label: '商品列表', type: 'primary' },
            { label: '商品排行', type: '' }
          ]"
          to="/products"
        />
      </div>
    </div>

    <div class="bottom-section">
      <el-row :gutter="20">
        <el-col :span="16">
          <div class="chart-card">
            <div class="chart-header">
              <h3>📊 GMV趋势</h3>
              <el-radio-group v-model="trendPeriod" size="small">
                <el-radio-button label="week">近7天</el-radio-button>
                <el-radio-button label="month">近30天</el-radio-button>
              </el-radio-group>
            </div>
            <div ref="trendChartRef" class="chart-container"></div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="chart-card">
            <div class="chart-header">
              <h3>🎯 目标完成情况</h3>
            </div>
            <div ref="gaugeChartRef" class="chart-container"></div>
          </div>
        </el-col>
      </el-row>

      <el-row :gutter="20" style="margin-top: 20px">
        <el-col :span="24">
          <div class="chart-card">
            <div class="chart-header">
              <h3>🔥 热销TOP10</h3>
              <el-button type="primary" text @click="$router.push('/products')">
                查看全部
              </el-button>
            </div>
            <el-table :data="topProducts" stripe>
              <el-table-column type="index" label="排名" width="60" align="center" />
              <el-table-column prop="title" label="商品名称" min-width="200" />
              <el-table-column prop="tier" label="分层" width="100">
                <template #default="{ row }">
                  <el-tag :type="getTierType(row.tier)">{{ row.tier || '未分类' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="net_sales" label="销售额" width="120" align="right">
                <template #default="{ row }">
                  ¥{{ formatNumber(row.net_sales) }}
                </template>
              </el-table-column>
              <el-table-column prop="visitors" label="访客数" width="100" align="right">
                <template #default="{ row }">
                  {{ formatNumber(row.visitors) }}
                </template>
              </el-table-column>
              <el-table-column prop="conversion" label="转化率" width="100" align="right">
                <template #default="{ row }">
                  {{ row.conversion ? (row.conversion * 100).toFixed(2) : 0 }}%
                </template>
              </el-table-column>
              <el-table-column label="操作" width="100">
                <template #default="{ row }">
                  <el-button size="small" text @click="viewProduct(row)">查看</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import {
  Refresh, Upload, TrendCharts, DataAnalysis,
  Monitor, Setting, Odometer, Goods
} from '@element-plus/icons-vue'
import GlobalTimeFilter from '@/components/GlobalTimeFilter.vue'
import CoreIndicators from '@/components/tower/CoreIndicators.vue'
import AlertBar from '@/components/tower/AlertBar.vue'
import HexagonCard from '@/components/tower/HexagonCard.vue'

const router = useRouter()
const trendPeriod = ref('week')
const trendChartRef = ref(null)
const gaugeChartRef = ref(null)
const charts = reactive({ trend: null, gauge: null })

const coreIndicators = ref([
  { label: 'GMV', value: '¥456,789', change: 12.3, color: '#409eff', icon: 'DataLine' },
  { label: '访客数', value: '123,456', change: 8.9, color: '#67c23a', icon: 'User' },
  { label: 'ROI', value: '3.87', change: 3.1, color: '#e6a23c', icon: 'DataAnalysis' },
  { label: '转化率', value: '3.2%', change: 1.2, color: '#00bcd4', icon: 'TrendCharts' }
])

const alerts = ref([
  {
    id: 1,
    level: 'urgent',
    title: '万相台ROI下降预警',
    desc: '万相台某个计划ROI低于2.0，已连续3天下降',
    time: '10分钟前'
  },
  {
    id: 2,
    level: 'urgent',
    title: '热销商品库存告急',
    desc: 'TOP1热销商品库存仅剩86件，预计明天断货',
    time: '32分钟前'
  },
  {
    id: 3,
    level: 'warning',
    title: '首页跳出率过高',
    desc: '首页跳出率68%，超过正常水平20%',
    time: '1小时前'
  },
  {
    id: 4,
    level: 'warning',
    title: '新访客占比下降',
    desc: '新访客占比从45%下降到38%',
    time: '2小时前'
  }
])

const topProducts = ref([
  { id: 1, title: '中古风玄关装饰摆件', tier: '利润款', net_sales: 87654, visitors: 4567, conversion: 0.032 },
  { id: 2, title: '入户玄关装饰品钟馗财神爷摆件', tier: '引流款', net_sales: 76543, visitors: 5678, conversion: 0.028 },
  { id: 3, title: '中古风玄关装饰摆件放钥匙收纳', tier: '利润款', net_sales: 54321, visitors: 3456, conversion: 0.041 },
  { id: 4, title: '现代简约客厅装饰画', tier: '潜力款', net_sales: 43210, visitors: 2345, conversion: 0.035 },
  { id: 5, title: '北欧风电视柜组合', tier: '利润款', net_sales: 32109, visitors: 1234, conversion: 0.038 }
])

const formatNumber = (num) => {
  if (!num && num !== 0) return '0'
  num = Number(num)
  if (num >= 10000) {
    return (num / 10000).toFixed(2) + '万'
  }
  return num.toLocaleString()
}

const getTierType = (tier) => {
  const types = { '引流款': 'success', '利润款': 'primary', '潜力款': 'warning' }
  return types[tier] || 'info'
}

const refresh = () => {
  ElMessage.success('数据已刷新')
}

const viewProduct = (product) => {
  ElMessage.info(`查看商品: ${product.title}`)
}

const initCharts = () => {
  if (charts.trend) {
    charts.trend.dispose()
    charts.trend = null
  }
  if (charts.gauge) {
    charts.gauge.dispose()
    charts.gauge = null
  }

  if (trendChartRef.value) {
    charts.trend = echarts.init(trendChartRef.value)
  }
  if (gaugeChartRef.value) {
    charts.gauge = echarts.init(gaugeChartRef.value)
  }
}

const updateTrendChart = () => {
  if (!charts.trend) return

  const dates = ['1号', '2号', '3号', '4号', '5号', '6号', '7号']
  const data1 = [32000, 38000, 45000, 42000, 52000, 48000, 56000]
  const data2 = [28000, 32000, 38000, 36000, 42000, 40000, 45000]

  charts.trend.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['GMV', '访客数'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
    xAxis: { type: 'category', data: dates },
    yAxis: [
      { type: 'value', name: 'GMV', position: 'left' },
      { type: 'value', name: '访客数', position: 'right' }
    ],
    series: [
      {
        name: 'GMV',
        type: 'line',
        data: data1,
        smooth: true,
        itemStyle: { color: '#409eff' },
        areaStyle: { opacity: 0.3 }
      },
      {
        name: '访客数',
        type: 'line',
        yAxisIndex: 1,
        data: data2,
        smooth: true,
        itemStyle: { color: '#67c23a' }
      }
    ]
  })
}

const updateGaugeChart = () => {
  if (!charts.gauge) return

  charts.gauge.setOption({
    tooltip: { formatter: '{a} <br/>{b} : {c}%' },
    series: [
      {
        type: 'gauge',
        progress: { show: true, width: 18 },
        axisLine: { lineStyle: { width: 18 } },
        axisTick: { show: false },
        splitLine: { length: 15, lineStyle: { width: 2, color: '#999' } },
        axisLabel: { distance: 25, fontSize: 12 },
        anchor: { show: true, showAbove: true, size: 25, itemStyle: { borderWidth: 10 } },
        detail: { valueAnimation: true, fontSize: 32, offsetCenter: [0, '70%'] },
        data: [{ value: 87, name: '目标完成率' }]
      }
    ]
  })
}

const updateCharts = () => {
  updateTrendChart()
  updateGaugeChart()
}

const handleResize = () => {
  if (charts.trend) charts.trend.resize()
  if (charts.gauge) charts.gauge.resize()
}

onMounted(async () => {
  await nextTick()
  initCharts()
  updateCharts()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (charts.trend) {
    charts.trend.dispose()
    charts.trend = null
  }
  if (charts.gauge) {
    charts.gauge.dispose()
    charts.gauge = null
  }
})
</script>

<style scoped>
.command-tower {
  padding: 20px;
  background: #f5f7fa;
  min-height: 100%;
}

.tower-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  background: white;
  padding: 20px 24px;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.header-left h1 {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 4px 0;
  color: #303133;
}

.subtitle {
  font-size: 14px;
  color: #909399;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.hexagon-area {
  margin: 24px 0;
}

.hexagon-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}

.bottom-section {
  margin-top: 24px;
}

.chart-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.chart-header h3 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: #303133;
}

.chart-container {
  height: 300px;
}
</style>
