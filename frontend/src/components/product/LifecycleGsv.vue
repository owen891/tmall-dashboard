<template>
  <div class="lifecycle-gsv">
    <el-row :gutter="20" style="margin-bottom: 20px">
      <el-col :span="12">
        <el-card>
          <template #header>
            2025年汇总GSV
            <span style="float: right; font-size: 24px; font-weight: bold; color: #409eff;">¥{{ formatNumber(summary2025) }}</span>
          </template>
          <div ref="chart2025Ref" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            2026年汇总GSV
            <span style="float: right; font-size: 24px; font-weight: bold; color: #67c23a;">¥{{ formatNumber(summary2026) }}</span>
          </template>
          <div ref="chart2026Ref" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-bottom: 20px">
      <template #header>生命周期曲线对比</template>
      <div ref="compareChartRef" class="chart-container"></div>
    </el-card>

    <el-card>
      <template #header>详细月度数据</template>
      <el-table :data="monthlyData" stripe size="small">
        <el-table-column prop="month" label="月份" width="120" fixed />
        <el-table-column prop="year2025" label="2025年GSV" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.year2025) }}</template>
        </el-table-column>
        <el-table-column prop="year2026" label="2026年GSV" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.year2026) }}</template>
        </el-table-column>
        <el-table-column prop="growth" label="同比增长" align="right">
          <template #default="{ row }">
            <span :class="row.growth >= 0 ? 'growth-positive' : 'growth-negative'">
              {{ row.growth >= 0 ? '+' : '' }}{{ row.growth }}%
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  productId: [String, Number],
  data: Object
})

const chart2025Ref = ref(null)
const chart2026Ref = ref(null)
const compareChartRef = ref(null)
let chart2025 = null
let chart2026 = null
let compareChart = null

const monthlyData = ref([])

const formatNumber = (num) => {
  if (!num && num !== 0) return '0'
  return Number(num).toLocaleString()
}

const summary2025 = computed(() => {
  return monthlyData.value.reduce((sum, item) => sum + (item.year2025 || 0), 0)
})

const summary2026 = computed(() => {
  return monthlyData.value.reduce((sum, item) => sum + (item.year2026 || 0), 0)
})

const initCharts = () => {
  initChart2025()
  initChart2026()
  initCompareChart()
}

const initChart2025 = () => {
  if (!chart2025Ref.value) return
  
  if (chart2025) {
    chart2025.dispose()
  }
  
  chart2025 = echarts.init(chart2025Ref.value)
  
  const data = monthlyData.value.map(item => item.year2025 || 0)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: '{b}<br/>GSV: ¥{c}'
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: 'GSV',
        type: 'bar',
        data: data.length ? data : [12000, 15000, 18000, 22000, 28000, 35000, 42000, 45000, 40000, 35000, 30000, 25000],
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#409eff' },
            { offset: 1, color: '#66b1ff' }
          ])
        }
      }
    ]
  }
  
  chart2025.setOption(option)
  window.addEventListener('resize', () => chart2025?.resize())
}

const initChart2026 = () => {
  if (!chart2026Ref.value) return
  
  if (chart2026) {
    chart2026.dispose()
  }
  
  chart2026 = echarts.init(chart2026Ref.value)
  
  const data = monthlyData.value.map(item => item.year2026 || 0)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: '{b}<br/>GSV: ¥{c}'
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: 'GSV',
        type: 'bar',
        data: data.length ? data : [15000, 18000, 22000, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#67c23a' },
            { offset: 1, color: '#95d475' }
          ])
        }
      }
    ]
  }
  
  chart2026.setOption(option)
  window.addEventListener('resize', () => chart2026?.resize())
}

const initCompareChart = () => {
  if (!compareChartRef.value) return
  
  if (compareChart) {
    compareChart.dispose()
  }
  
  compareChart = echarts.init(compareChartRef.value)
  
  const data2025 = monthlyData.value.map(item => item.year2025 || 0)
  const data2026 = monthlyData.value.map(item => item.year2026 || 0)
  
  const option = {
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['2025年', '2026年']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: '2025年',
        type: 'line',
        data: data2025.length ? data2025 : [12000, 15000, 18000, 22000, 28000, 35000, 42000, 45000, 40000, 35000, 30000, 25000],
        itemStyle: { color: '#409eff' },
        smooth: true
      },
      {
        name: '2026年',
        type: 'line',
        data: data2026.length ? data2026 : [15000, 18000, 22000, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        itemStyle: { color: '#67c23a' },
        smooth: true
      }
    ]
  }
  
  compareChart.setOption(option)
  window.addEventListener('resize', () => compareChart?.resize())
}

const loadData = () => {
  const d = props.data || {}
  monthlyData.value = d.monthly || [
    { month: '1月', year2025: 12000, year2026: 15000, growth: 25.0 },
    { month: '2月', year2025: 15000, year2026: 18000, growth: 20.0 },
    { month: '3月', year2025: 18000, year2026: 22000, growth: 22.2 },
    { month: '4月', year2025: 22000, year2026: 0, growth: 0 },
    { month: '5月', year2025: 28000, year2026: 0, growth: 0 },
    { month: '6月', year2025: 35000, year2026: 0, growth: 0 },
    { month: '7月', year2025: 42000, year2026: 0, growth: 0 },
    { month: '8月', year2025: 45000, year2026: 0, growth: 0 },
    { month: '9月', year2025: 40000, year2026: 0, growth: 0 },
    { month: '10月', year2025: 35000, year2026: 0, growth: 0 },
    { month: '11月', year2025: 30000, year2026: 0, growth: 0 },
    { month: '12月', year2025: 25000, year2026: 0, growth: 0 }
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
.lifecycle-gsv {
  padding: 10px 0;
}

.chart-container {
  height: 280px;
}

.growth-positive {
  color: #67c23a;
}

.growth-negative {
  color: #f56c6c;
}
</style>