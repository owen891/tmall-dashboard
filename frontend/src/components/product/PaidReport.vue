<template>
  <div class="paid-report">
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
          <template #header>花费与成交趋势</template>
          <div ref="costChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>效果指标</template>
          <div ref="effectChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <template #header>详细数据</template>
      <el-table :data="tableData" stripe size="small">
        <el-table-column prop="date" label="日期" width="120" />
        <el-table-column prop="impressions" label="展现量" align="right" />
        <el-table-column prop="clicks" label="点击量" align="right" />
        <el-table-column prop="cost" label="花费" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.cost) }}</template>
        </el-table-column>
        <el-table-column prop="ctr" label="点击率" align="right">
          <template #default="{ row }">{{ row.ctr }}%</template>
        </el-table-column>
        <el-table-column prop="avgCpc" label="平均点击花费" align="right">
          <template #default="{ row }">¥{{ row.avgCpc }}</template>
        </el-table-column>
        <el-table-column prop="cpm" label="千次展现花费" align="right">
          <template #default="{ row }">¥{{ row.cpm }}</template>
        </el-table-column>
        <el-table-column prop="directAmount" label="直接成交金额" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.directAmount) }}</template>
        </el-table-column>
        <el-table-column prop="indirectAmount" label="间接成交金额" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.indirectAmount) }}</template>
        </el-table-column>
        <el-table-column prop="totalAmount" label="总成交金额" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.totalAmount) }}</template>
        </el-table-column>
        <el-table-column prop="totalOrders" label="总成交笔数" align="right" />
        <el-table-column prop="directOrders" label="直接成交笔数" align="right" />
        <el-table-column prop="indirectOrders" label="间接成交笔数" align="right" />
        <el-table-column prop="clickConversion" label="点击转化率" align="right">
          <template #default="{ row }">{{ row.clickConversion }}%</template>
        </el-table-column>
        <el-table-column prop="roi" label="投入产出比" align="right" />
        <el-table-column prop="preSaleRoi" label="含预售投产比" align="right" />
        <el-table-column prop="totalCost" label="总成交成本" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.totalCost) }}</template>
        </el-table-column>
        <el-table-column prop="totalCart" label="总购物车数" align="right" />
        <el-table-column prop="directCart" label="直接购物车数" align="right" />
        <el-table-column prop="indirectCart" label="间接购物车数" align="right" />
        <el-table-column prop="cartRate" label="加购率" align="right">
          <template #default="{ row }">{{ row.cartRate }}%</template>
        </el-table-column>
        <el-table-column prop="collectItem" label="收藏宝贝数" align="right" />
        <el-table-column prop="collectShop" label="收藏店铺数" align="right" />
        <el-table-column prop="shopCollectCost" label="店铺收藏成本" align="right">
          <template #default="{ row }">¥{{ row.shopCollectCost }}</template>
        </el-table-column>
        <el-table-column prop="totalCollectAdd" label="总收藏加购数" align="right" />
        <el-table-column prop="totalCollectAddCost" label="总收藏加购成本" align="right">
          <template #default="{ row }">¥{{ row.totalCollectAddCost }}</template>
        </el-table-column>
        <el-table-column prop="itemCollectAdd" label="宝贝收藏加购数" align="right" />
        <el-table-column prop="itemCollectAddCost" label="宝贝收藏加购成本" align="right">
          <template #default="{ row }">¥{{ row.itemCollectAddCost }}</template>
        </el-table-column>
        <el-table-column prop="totalCollect" label="总收藏数" align="right" />
        <el-table-column prop="itemCollectCost" label="宝贝收藏成本" align="right">
          <template #default="{ row }">¥{{ row.itemCollectCost }}</template>
        </el-table-column>
        <el-table-column prop="itemCollectRate" label="宝贝收藏率" align="right">
          <template #default="{ row }">{{ row.itemCollectRate }}%</template>
        </el-table-column>
        <el-table-column prop="cartCost" label="加购成本" align="right">
          <template #default="{ row }">¥{{ row.cartCost }}</template>
        </el-table-column>
        <el-table-column prop="guideVisits" label="引导访问量" align="right" />
        <el-table-column prop="guideVisitors" label="引导访问人数" align="right" />
        <el-table-column prop="guidePotential" label="引导访问潜客数" align="right" />
        <el-table-column prop="guidePotentialRate" label="引导访问潜客占比" align="right">
          <template #default="{ row }">{{ row.guidePotentialRate }}%</template>
        </el-table-column>
        <el-table-column prop="newCustomerCount" label="成交新客数" align="right" />
        <el-table-column prop="newCustomerRate" label="成交新客占比" align="right">
          <template #default="{ row }">{{ row.newCustomerRate }}%</template>
        </el-table-column>
        <el-table-column prop="totalPayers" label="成交人数" align="right" />
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

const costChartRef = ref(null)
const effectChartRef = ref(null)
let costChart = null
let effectChart = null

const coreMetrics = ref([])
const tableData = ref([])

const formatNumber = (num) => {
  if (!num && num !== 0) return '0'
  return Number(num).toLocaleString()
}

const initCharts = () => {
  initCostChart()
  initEffectChart()
}

const initCostChart = () => {
  if (!costChartRef.value) return
  
  if (costChart) {
    costChart.dispose()
  }
  
  costChart = echarts.init(costChartRef.value)
  
  const dates = (props.data?.trend || []).map(item => item.date)
  const costData = (props.data?.trend || []).map(item => item.cost || 0)
  const amountData = (props.data?.trend || []).map(item => item.totalAmount || 0)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      }
    },
    legend: {
      data: ['花费', '总成交金额']
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
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: '花费',
        type: 'bar',
        data: costData.length ? costData : [1200, 1500, 1300, 1800, 1600, 2000, 1900],
        itemStyle: { color: '#409eff' }
      },
      {
        name: '总成交金额',
        type: 'line',
        data: amountData.length ? amountData : [4500, 5200, 4800, 6200, 5800, 7200, 6800],
        itemStyle: { color: '#f56c6c' },
        smooth: true
      }
    ]
  }
  
  costChart.setOption(option)
  window.addEventListener('resize', () => costChart?.resize())
}

const initEffectChart = () => {
  if (!effectChartRef.value) return
  
  if (effectChart) {
    effectChart.dispose()
  }
  
  effectChart = echarts.init(effectChartRef.value)
  
  const option = {
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['点击率', '点击转化率', 'ROI']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: ['04-01', '04-02', '04-03', '04-04', '04-05', '04-06', '04-07']
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: '点击率',
        type: 'line',
        data: [3.2, 3.5, 3.1, 3.8, 3.6, 4.0, 3.9],
        itemStyle: { color: '#409eff' }
      },
      {
        name: '点击转化率',
        type: 'line',
        data: [2.1, 2.3, 2.0, 2.5, 2.4, 2.8, 2.7],
        itemStyle: { color: '#67c23a' }
      },
      {
        name: 'ROI',
        type: 'line',
        data: [3.8, 3.5, 3.7, 3.4, 3.6, 3.6, 3.6],
        itemStyle: { color: '#e6a23c' }
      }
    ]
  }
  
  effectChart.setOption(option)
  window.addEventListener('resize', () => effectChart?.resize())
}

const loadData = () => {
  const d = props.data || {}
  coreMetrics.value = [
    { key: 'impressions', label: '展现量', value: formatNumber(d.impressions || 0) },
    { key: 'clicks', label: '点击量', value: formatNumber(d.clicks || 0) },
    { key: 'cost', label: '花费', value: `¥${formatNumber(d.cost || 0)}` },
    { key: 'roi', label: 'ROI', value: (d.roi || 0).toFixed(2) },
    { key: 'totalAmount', label: '总成交金额', value: `¥${formatNumber(d.totalAmount || 0)}` },
    { key: 'ctr', label: '点击率', value: `${d.ctr || 0}%` }
  ]
  
  tableData.value = d.trend || [
    { date: '2025-04-01', impressions: 100000, clicks: 3200, cost: 1500, ctr: 3.2, avgCpc: 0.47, cpm: 15.0, directAmount: 3800, indirectAmount: 700, totalAmount: 4500, totalOrders: 67, directOrders: 55, indirectOrders: 12, clickConversion: 2.1, roi: 3.0, preSaleRoi: 3.2, totalCost: 22.4, totalCart: 450, directCart: 380, indirectCart: 70, cartRate: 14.1, collectItem: 280, collectShop: 45, shopCollectCost: 33.3, totalCollectAdd: 325, totalCollectAddCost: 4.6, itemCollectAdd: 280, itemCollectAddCost: 5.4, totalCollect: 125, itemCollectCost: 12.0, itemCollectRate: 3.9, cartCost: 3.3, guideVisits: 5200, guideVisitors: 4800, guidePotential: 2100, guidePotentialRate: 43.8, newCustomerCount: 32, newCustomerRate: 47.8, totalPayers: 67 }
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
.paid-report {
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
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.chart-container {
  height: 300px;
}
</style>