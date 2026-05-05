<template>
  <div class="marketing-data">
    <el-row :gutter="20" style="margin-bottom: 20px">
      <el-col :span="4" v-for="item in coreMetrics" :key="item.key">
        <el-card class="metric-card">
          <div class="metric-label">{{ item.label }}</div>
          <div class="metric-value">{{ item.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-bottom: 20px">
      <el-col :span="12">
        <el-card>
          <template #header>流量来源分析</template>
          <div ref="sourceChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>推广效果趋势</template>
          <div ref="trendChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <template #header>详细数据</template>
      <el-table :data="tableData" stripe size="small">
        <el-table-column prop="date" label="日期" width="120" />
        <el-table-column prop="marketingIpv" label="营销推广IPV" align="right" />
        <el-table-column prop="marketingCost" label="营销推广消耗" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.marketingCost) }}</template>
        </el-table-column>
        <el-table-column prop="marketingRoi" label="营销推广ROI" align="right" />
        <el-table-column prop="collectAddRate" label="收加率" align="right">
          <template #default="{ row }">{{ row.collectAddRate }}%</template>
        </el-table-column>
        <el-table-column prop="repurchaseRate" label="复购率" align="right">
          <template #default="{ row }">{{ row.repurchaseRate }}%</template>
        </el-table-column>
        <el-table-column prop="nonMarketingIpv" label="非推广IPV" align="right" />
        <el-table-column prop="searchIpv" label="搜索IPV" align="right" />
        <el-table-column prop="recommendIpv" label="推荐IPV" align="right" />
        <el-table-column prop="freeSearchCtr" label="免费搜索点击率" align="right">
          <template #default="{ row }">{{ row.freeSearchCtr }}%</template>
        </el-table-column>
        <el-table-column prop="industryCtr" label="行业点击率" align="right">
          <template #default="{ row }">{{ row.industryCtr }}%</template>
        </el-table-column>
        <el-table-column prop="unitPrice" label="笔单价" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.unitPrice) }}</template>
        </el-table-column>
        <el-table-column prop="bundleQuantity" label="连带购买量" align="right" />
        <el-table-column prop="bundleRate" label="连带购买率" align="right">
          <template #default="{ row }">{{ row.bundleRate }}%</template>
        </el-table-column>
        <el-table-column prop="bundleCategoryWidth" label="连带叶子类目宽度" align="right" />
        <el-table-column prop="repurchaseUsers" label="复购用户数" align="right" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  productId: [String, Number],
  data: Object
})

const sourceChartRef = ref(null)
const trendChartRef = ref(null)
let sourceChart = null
let trendChart = null

const coreMetrics = ref([])
const tableData = ref([])

const formatNumber = (num) => {
  if (!num && num !== 0) return '0'
  return Number(num).toLocaleString()
}

const initCharts = () => {
  initSourceChart()
  initTrendChart()
}

const initSourceChart = () => {
  if (!sourceChartRef.value) return
  
  if (sourceChart) {
    sourceChart.dispose()
  }
  
  sourceChart = echarts.init(sourceChartRef.value)
  
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
        name: '流量来源',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: true,
          formatter: '{b}\n{d}%'
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 16,
            fontWeight: 'bold'
          }
        },
        data: [
          { value: 35, name: '搜索IPV', itemStyle: { color: '#409eff' } },
          { value: 25, name: '推荐IPV', itemStyle: { color: '#67c23a' } },
          { value: 20, name: '营销推广IPV', itemStyle: { color: '#e6a23c' } },
          { value: 20, name: '非推广IPV', itemStyle: { color: '#f56c6c' } }
        ]
      }
    ]
  }
  
  sourceChart.setOption(option)
  window.addEventListener('resize', () => sourceChart?.resize())
}

const initTrendChart = () => {
  if (!trendChartRef.value) return
  
  if (trendChart) {
    trendChart.dispose()
  }
  
  trendChart = echarts.init(trendChartRef.value)
  
  const dates = (props.data?.trend || []).map(item => item.date)
  const costData = (props.data?.trend || []).map(item => item.marketingCost || 0)
  const roiData = (props.data?.trend || []).map(item => item.marketingRoi || 0)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      }
    },
    legend: {
      data: ['推广消耗', 'ROI']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: dates.length ? dates : ['04-01', '04-02', '04-03', '04-04', '04-05', '04-06', '04-07']
    },
    yAxis: [
      {
        type: 'value',
        name: '消耗',
        position: 'left'
      },
      {
        type: 'value',
        name: 'ROI',
        position: 'right'
      }
    ],
    series: [
      {
        name: '推广消耗',
        type: 'bar',
        data: costData.length ? costData : [1200, 1500, 1300, 1800, 1600, 2000, 1900],
        itemStyle: { color: '#409eff' }
      },
      {
        name: 'ROI',
        type: 'line',
        yAxisIndex: 1,
        data: roiData.length ? roiData : [3.2, 2.8, 3.5, 4.1, 3.8, 4.5, 4.2],
        itemStyle: { color: '#f56c6c' }
      }
    ]
  }
  
  trendChart.setOption(option)
  window.addEventListener('resize', () => trendChart?.resize())
}

const loadData = () => {
  const d = props.data || {}
  coreMetrics.value = [
    { key: 'marketingIpv', label: '营销推广IPV', value: formatNumber(d.marketingIpv || 0) },
    { key: 'marketingCost', label: '推广消耗', value: `¥${formatNumber(d.marketingCost || 0)}` },
    { key: 'marketingRoi', label: '营销ROI', value: (d.marketingRoi || 0).toFixed(2) },
    { key: 'repurchaseRate', label: '复购率', value: `${d.repurchaseRate || 0}%` },
    { key: 'searchIpv', label: '搜索IPV', value: formatNumber(d.searchIpv || 0) },
    { key: 'unitPrice', label: '笔单价', value: `¥${formatNumber(d.unitPrice || 0)}` }
  ]
  
  tableData.value = d.trend || [
    { date: '2025-04-01', marketingIpv: 1234, marketingCost: 1500, marketingRoi: 3.2, collectAddRate: 8.5, repurchaseRate: 12.3, nonMarketingIpv: 2345, searchIpv: 1890, recommendIpv: 455, freeSearchCtr: 4.2, industryCtr: 3.8, unitPrice: 128, bundleQuantity: 1.3, bundleRate: 35.2, bundleCategoryWidth: 2.1, repurchaseUsers: 56 },
    { date: '2025-04-02', marketingIpv: 1100, marketingCost: 1300, marketingRoi: 3.5, collectAddRate: 8.2, repurchaseRate: 11.8, nonMarketingIpv: 2100, searchIpv: 1750, recommendIpv: 350, freeSearchCtr: 4.0, industryCtr: 3.7, unitPrice: 125, bundleQuantity: 1.25, bundleRate: 33.8, bundleCategoryWidth: 2.0, repurchaseUsers: 52 }
  ]
}

watch(() => props.data, () => {
  loadData()
  initCharts()
}, { deep: true, immediate: true })

onMounted(() => {
  loadData()
  initCharts()
})
</script>

<style scoped>
.marketing-data {
  padding: 10px 0;
}

.metric-card {
  text-align: center;
}

.metric-label {
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
}

.metric-value {
  font-size: 22px;
  font-weight: 600;
  color: #303133;
}

.chart-container {
  height: 300px;
}
</style>