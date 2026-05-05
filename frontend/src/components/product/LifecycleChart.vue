<template>
  <div class="lifecycle-chart">
    <div class="lifecycle-header">
      <span class="lifecycle-stage" v-if="lifecycleStage">
        <el-tag :type="getStageType(lifecycleStage)">生命周期: {{ lifecycleStage }}</el-tag>
      </span>
      <div class="lifecycle-totals">
        <span>25年汇总: <b>{{ formatCurrency(gsv25Total) }}</b></span>
        <span>26年汇总: <b>{{ formatCurrency(gsv26Total) }}</b></span>
      </div>
    </div>
    <div ref="chartRef" class="chart-container"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as echarts from 'echarts'
import api from '@/api'

const props = defineProps({
  productId: {
    type: String,
    required: true
  }
})

const chartRef = ref(null)
let chart = null

const gsvData = ref([])
const gsv25Total = ref(0)
const gsv26Total = ref(0)
const lifecycleStage = ref('')

const formatCurrency = (val) => {
  if (!val) return '¥0'
  return '¥' + Number(val).toLocaleString()
}

const getStageType = (stage) => {
  const types = {
    '新品期': 'success',
    '成长期': 'primary',
    '成熟期': 'warning',
    '衰退期': 'danger'
  }
  return types[stage] || 'info'
}

const loadData = async () => {
  try {
    const res = await api.getProductLifecycle(props.productId)
    const data = res.data || {}
    gsvData.value = data.gsv_data || []
    gsv25Total.value = data.gsv_25_total || 0
    gsv26Total.value = data.gsv_26_total || 0
    lifecycleStage.value = data.lifecycle_stage || ''
    
    initChart()
  } catch (error) {
    console.error('Load lifecycle error:', error)
  }
}

const initChart = () => {
  if (!chartRef.value) return
  
  if (chart) {
    chart.dispose()
  }
  
  chart = echarts.init(chartRef.value)
  
  const months = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
  
  const data25 = []
  const data26 = []
  
  for (let i = 1; i <= 12; i++) {
    const item25 = gsvData.value.find(d => d.year === 2025 && d.month_num === i)
    const item26 = gsvData.value.find(d => d.year === 2026 && d.month_num === i)
    data25.push(item25?.gsv || 0)
    data26.push(item26?.gsv || 0)
  }
  
  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        let result = params[0].axisValue + '<br/>'
        params.forEach(p => {
          result += `${p.marker} ${p.seriesName}: ¥${p.value?.toLocaleString() || 0}<br/>`
        })
        return result
      }
    },
    legend: {
      data: ['2025年', '2026年'],
      top: 0
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '40px',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: months,
      axisLabel: {
        interval: 0
      }
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (val) => {
          if (val >= 10000) {
            return (val / 10000).toFixed(1) + 'w'
          }
          return val
        }
      }
    },
    series: [
      {
        name: '2025年',
        type: 'line',
        data: data25,
        smooth: true,
        itemStyle: { color: '#409EFF' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
            { offset: 1, color: 'rgba(64, 158, 255, 0.05)' }
          ])
        }
      },
      {
        name: '2026年',
        type: 'line',
        data: data26,
        smooth: true,
        itemStyle: { color: '#67C23A' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(103, 194, 58, 0.3)' },
            { offset: 1, color: 'rgba(103, 194, 58, 0.05)' }
          ])
        }
      }
    ]
  }
  
  chart.setOption(option)
}

const handleResize = () => {
  if (chart) {
    chart.resize()
  }
}

watch(() => props.productId, () => {
  loadData()
})

onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (chart) {
    chart.dispose()
    chart = null
  }
})
</script>

<style scoped>
.lifecycle-chart {
  padding: 10px 0;
}

.lifecycle-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.lifecycle-totals {
  display: flex;
  gap: 20px;
  font-size: 14px;
  color: #606266;
}

.lifecycle-totals b {
  color: #409EFF;
}

.chart-container {
  height: 300px;
}
</style>
