<template>
  <div class="shengyi-data">
    <el-row :gutter="20" style="margin-bottom: 20px">
      <el-col :span="6" v-for="item in coreMetrics" :key="item.key">
        <el-card class="metric-card">
          <div class="metric-label">{{ item.label }}</div>
          <div class="metric-value">{{ item.value }}</div>
          <div v-if="item.trend !== undefined" :class="['metric-trend', item.trend >= 0 ? 'up' : 'down']">
            <el-icon><CaretTop v-if="item.trend >= 0" /><CaretBottom v-else /></el-icon>
            {{ Math.abs(item.trend).toFixed(1) }}%
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <template #header>流量趋势</template>
          <div ref="trafficChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>转化漏斗</template>
          <div ref="funnelChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 20px">
      <template #header>详细数据</template>
      <el-table :data="tableData" stripe size="small">
        <el-table-column prop="date" label="日期" width="120" />
        <el-table-column prop="visitors" label="商品访客数" align="right" />
        <el-table-column prop="pageViews" label="商品浏览量" align="right" />
        <el-table-column prop="avgStayTime" label="平均停留时长" align="right">
          <template #default="{ row }">{{ formatDuration(row.avgStayTime) }}</template>
        </el-table-column>
        <el-table-column prop="bounceRate" label="详情页跳出率" align="right">
          <template #default="{ row }">{{ row.bounceRate }}%</template>
        </el-table-column>
        <el-table-column prop="favorites" label="收藏人数" align="right" />
        <el-table-column prop="cartAdds" label="加购件数" align="right" />
        <el-table-column prop="cartPeople" label="加购人数" align="right" />
        <el-table-column prop="payBuyers" label="支付买家数" align="right" />
        <el-table-column prop="payQuantity" label="支付件数" align="right" />
        <el-table-column prop="payAmount" label="支付金额" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.payAmount) }}</template>
        </el-table-column>
        <el-table-column prop="conversion" label="商品支付转化率" align="right">
          <template #default="{ row }">{{ row.conversion }}%</template>
        </el-table-column>
        <el-table-column prop="refundAmount" label="成功退款金额" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.refundAmount) }}</template>
        </el-table-column>
        <el-table-column prop="searchConversion" label="搜索引导转化率" align="right">
          <template #default="{ row }">{{ row.searchConversion }}%</template>
        </el-table-column>
        <el-table-column prop="searchBuyers" label="搜索引导买家数" align="right" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { CaretTop, CaretBottom } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

const props = defineProps({
  productId: [String, Number],
  data: Object
})

const trafficChartRef = ref(null)
const funnelChartRef = ref(null)
let trafficChart = null
let funnelChart = null

const coreMetrics = ref([])
const tableData = ref([])

const formatNumber = (num) => {
  if (!num && num !== 0) return '0'
  return Number(num).toLocaleString()
}

const formatDuration = (seconds) => {
  if (!seconds) return '0s'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return mins > 0 ? `${mins}分${secs}秒` : `${secs}秒`
}

const initCharts = () => {
  initTrafficChart()
  initFunnelChart()
}

const initTrafficChart = () => {
  if (!trafficChartRef.value) return
  
  if (trafficChart) {
    trafficChart.dispose()
  }
  
  trafficChart = echarts.init(trafficChartRef.value)
  
  const dates = (props.data?.trend || []).map(item => item.date)
  const visitors = (props.data?.trend || []).map(item => item.visitors || 0)
  const pageViews = (props.data?.trend || []).map(item => item.pageViews || 0)
  
  const option = {
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['访客数', '浏览量']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates.length ? dates : ['01-01', '01-02', '01-03', '01-04', '01-05', '01-06', '01-07']
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: '访客数',
        type: 'line',
        data: visitors.length ? visitors : [820, 932, 901, 934, 1290, 1330, 1320],
        smooth: true,
        itemStyle: { color: '#409eff' }
      },
      {
        name: '浏览量',
        type: 'line',
        data: pageViews.length ? pageViews : [1200, 1500, 1600, 1400, 2000, 2100, 1900],
        smooth: true,
        itemStyle: { color: '#67c23a' }
      }
    ]
  }
  
  trafficChart.setOption(option)
  window.addEventListener('resize', () => trafficChart?.resize())
}

const initFunnelChart = () => {
  if (!funnelChartRef.value) return
  
  if (funnelChart) {
    funnelChart.dispose()
  }
  
  funnelChart = echarts.init(funnelChartRef.value)
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    series: [
      {
        name: '转化漏斗',
        type: 'funnel',
        left: '10%',
        top: 60,
        bottom: 60,
        width: '80%',
        min: 0,
        max: 100,
        minSize: '0%',
        maxSize: '100%',
        sort: 'descending',
        gap: 2,
        label: {
          show: true,
          position: 'inside'
        },
        labelLine: {
          length: 10,
          lineStyle: {
            width: 1,
            type: 'solid'
          }
        },
        itemStyle: {
          borderColor: '#fff',
          borderWidth: 1
        },
        emphasis: {
          label: {
            fontSize: 20
          }
        },
        data: [
          { value: 100, name: '访客数', itemStyle: { color: '#409eff' } },
          { value: 80, name: '浏览量', itemStyle: { color: '#67c23a' } },
          { value: 40, name: '加购人数', itemStyle: { color: '#e6a23c' } },
          { value: 20, name: '支付买家数', itemStyle: { color: '#f56c6c' } }
        ]
      }
    ]
  }
  
  funnelChart.setOption(option)
  window.addEventListener('resize', () => funnelChart?.resize())
}

const loadData = () => {
  const d = props.data || {}
  coreMetrics.value = [
    { key: 'visitors', label: '商品访客数', value: formatNumber(d.visitors || 0), trend: 5.2 },
    { key: 'pageViews', label: '商品浏览量', value: formatNumber(d.pageViews || 0), trend: 3.1 },
    { key: 'conversion', label: '支付转化率', value: `${d.conversion || 0}%`, trend: -1.2 },
    { key: 'payAmount', label: '支付金额', value: `¥${formatNumber(d.payAmount || 0)}`, trend: 8.5 }
  ]
  
  tableData.value = d.trend || [
    { date: '2025-04-01', visitors: 1234, pageViews: 2345, avgStayTime: 45, bounceRate: 32.5, favorites: 89, cartAdds: 234, cartPeople: 189, payBuyers: 45, payQuantity: 67, payAmount: 12345, conversion: 3.65, refundAmount: 234, searchConversion: 4.2, searchBuyers: 28 },
    { date: '2025-04-02', visitors: 1156, pageViews: 2100, avgStayTime: 42, bounceRate: 34.1, favorites: 78, cartAdds: 198, cartPeople: 167, payBuyers: 38, payQuantity: 52, payAmount: 9876, conversion: 3.29, refundAmount: 156, searchConversion: 3.8, searchBuyers: 22 }
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
.shengyi-data {
  padding: 10px 0;
}

.metric-card {
  text-align: center;
}

.metric-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
}

.metric-value {
  font-size: 26px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.metric-trend {
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.metric-trend.up {
  color: #67c23a;
}

.metric-trend.down {
  color: #f56c6c;
}

.chart-container {
  height: 300px;
}
</style>