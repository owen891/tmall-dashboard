<template>
  <div class="sales-chart">
    <div ref="chartRef" style="width: 100%; height: 400px;"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({ productId: String })
const chartRef = ref(null)
let chart = null

const initChart = async () => {
  if (!chartRef.value) return

  chart = echarts.init(chartRef.value)

  // 模拟销售数据
  const dates = []
  const sales = []
  const now = new Date()
  for (let i = 29; i >= 0; i--) {
    const d = new Date(now)
    d.setDate(d.getDate() - i)
    dates.push(d.toLocaleDateString())
    sales.push(Math.random() * 10000)
  }

  const option = {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', name: '销售额' },
    series: [{
      data: sales,
      type: 'line',
      smooth: true,
      areaStyle: { opacity: 0.3 }
    }]
  }

  chart.setOption(option)
}

onMounted(() => initChart())
onUnmounted(() => chart?.dispose())

watch(() => props.productId, () => initChart())
</script>

<style scoped>
.sales-chart {
  padding: 20px;
}
</style>
