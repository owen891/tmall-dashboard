<template>
  <div class="compare-analysis">
    <el-card class="filter-card">
      <div class="filter-row">
        <div class="period-select">
          <span class="label">对比周期:</span>
          <el-select v-model="compareType" size="small" @change="refreshData">
            <el-option label="日对比" value="day" />
            <el-option label="周对比" value="week" />
            <el-option label="月对比" value="month" />
          </el-select>
        </div>
        
        <div class="quick-buttons">
          <el-button size="small" @click="quickCompare('lastWeek')">上周对比</el-button>
          <el-button size="small" @click="quickCompare('lastMonth')">上月对比</el-button>
        </div>
        
        <el-button type="primary" size="small" @click="refreshData" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </el-card>

    <div class="summary-cards" v-loading="loading">
      <el-card class="summary-card">
        <div class="card-header">
          <span class="card-title">GMV</span>
          <span class="card-badge">核心</span>
        </div>
        <div class="card-content">
          <div class="value-row">
            <span class="value-label">当前周期</span>
            <span class="value">¥{{ formatNumber(summaryData.current.gmv) }}</span>
          </div>
          <div class="value-row">
            <span class="value-label">对比周期</span>
            <span class="value compare">¥{{ formatNumber(summaryData.compare.gmv) }}</span>
          </div>
          <div class="change-row" :class="summaryData.change.gmv >= 0 ? 'positive' : 'negative'">
            <el-icon>
              <ArrowUp v-if="summaryData.change.gmv >= 0" />
              <ArrowDown v-else />
            </el-icon>
            <span>{{ summaryData.change.gmv >= 0 ? '+' : '' }}{{ summaryData.change.gmv }}%</span>
          </div>
        </div>
      </el-card>
      
      <el-card class="summary-card">
        <div class="card-header">
          <span class="card-title">订单数</span>
        </div>
        <div class="card-content">
          <div class="value-row">
            <span class="value-label">当前周期</span>
            <span class="value">{{ formatNumber(summaryData.current.orders) }}</span>
          </div>
          <div class="value-row">
            <span class="value-label">对比周期</span>
            <span class="value compare">{{ formatNumber(summaryData.compare.orders) }}</span>
          </div>
          <div class="change-row" :class="summaryData.change.orders >= 0 ? 'positive' : 'negative'">
            <el-icon>
              <ArrowUp v-if="summaryData.change.orders >= 0" />
              <ArrowDown v-else />
            </el-icon>
            <span>{{ summaryData.change.orders >= 0 ? '+' : '' }}{{ summaryData.change.orders }}%</span>
          </div>
        </div>
      </el-card>
      
      <el-card class="summary-card">
        <div class="card-header">
          <span class="card-title">访客数</span>
        </div>
        <div class="card-content">
          <div class="value-row">
            <span class="value-label">当前周期</span>
            <span class="value">{{ formatNumber(summaryData.current.visitors) }}</span>
          </div>
          <div class="value-row">
            <span class="value-label">对比周期</span>
            <span class="value compare">{{ formatNumber(summaryData.compare.visitors) }}</span>
          </div>
          <div class="change-row" :class="summaryData.change.visitors >= 0 ? 'positive' : 'negative'">
            <el-icon>
              <ArrowUp v-if="summaryData.change.visitors >= 0" />
              <ArrowDown v-else />
            </el-icon>
            <span>{{ summaryData.change.visitors >= 0 ? '+' : '' }}{{ summaryData.change.visitors }}%</span>
          </div>
        </div>
      </el-card>
      
      <el-card class="summary-card">
        <div class="card-header">
          <span class="card-title">转化率</span>
        </div>
        <div class="card-content">
          <div class="value-row">
            <span class="value-label">当前周期</span>
            <span class="value">{{ summaryData.current.conversion }}%</span>
          </div>
          <div class="value-row">
            <span class="value-label">对比周期</span>
            <span class="value compare">{{ summaryData.compare.conversion }}%</span>
          </div>
          <div class="change-row" :class="summaryData.change.conversion >= 0 ? 'positive' : 'negative'">
            <el-icon>
              <ArrowUp v-if="summaryData.change.conversion >= 0" />
              <ArrowDown v-else />
            </el-icon>
            <span>{{ summaryData.change.conversion >= 0 ? '+' : '' }}{{ summaryData.change.conversion }}%</span>
          </div>
        </div>
      </el-card>
    </div>

    <div class="chart-section">
      <el-card>
        <template #header>
          <span>指标趋势对比</span>
          <el-select v-model="chartMetric" size="small" style="float: right; width: 120px;">
            <el-option label="销售额" value="gmv" />
            <el-option label="订单数" value="orders" />
            <el-option label="访客数" value="visitors" />
          </el-select>
        </template>
        <div ref="trendChartRef" class="chart-container"></div>
      </el-card>
    </div>

    <div class="detail-section">
      <el-card v-loading="loading">
        <template #header>详细对比数据</template>
        <el-table :data="detailData" stripe size="small">
          <el-table-column prop="name" label="指标名称" min-width="150" />
          <el-table-column prop="currentValue" label="当前周期" width="150" align="right">
            <template #default="{ row }">{{ row.currentValue }}</template>
          </el-table-column>
          <el-table-column prop="compareValue" label="对比周期" width="150" align="right">
            <template #default="{ row }">{{ row.compareValue }}</template>
          </el-table-column>
          <el-table-column prop="change" label="变化率" width="100" align="center">
            <template #default="{ row }">
              <span :class="row.change >= 0 ? 'text-success' : 'text-danger'">
                {{ row.change >= 0 ? '+' : '' }}{{ row.change }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="趋势" width="80" align="center">
            <template #default="{ row }">
              <el-icon :class="row.change >= 0 ? 'text-success' : 'text-danger'">
                <ArrowUp v-if="row.change >= 0" />
                <ArrowDown v-else />
              </el-icon>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { Refresh, ArrowUp, ArrowDown } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import api from '@/api'

const compareType = ref('week')
const chartMetric = ref('gmv')
const loading = ref(false)

const summaryData = ref({
  current: { gmv: 0, orders: 0, visitors: 0, conversion: 0 },
  compare: { gmv: 0, orders: 0, visitors: 0, conversion: 0 },
  change: { gmv: 0, orders: 0, visitors: 0, conversion: 0 }
})

const detailData = ref([])

const trendChartRef = ref(null)
let trendChart = null

const formatNumber = (num) => {
  if (!num && num !== 0) return '0'
  return Number(num).toLocaleString()
}

const quickCompare = (type) => {
  if (type === 'lastWeek') {
    compareType.value = 'week'
    refreshData()
  } else if (type === 'lastMonth') {
    compareType.value = 'month'
    refreshData()
  }
}

const refreshData = async () => {
  loading.value = true
  try {
    const res = await api.getCompareData(compareType.value)
    
    if (res && res.data) {
      const data = res.data
      
      summaryData.value = {
        current: data.current_period || data.current || { gmv: 2856000, orders: 12580, visitors: 156800, conversion: 8.02 },
        compare: data.compare_period || data.compare || { gmv: 3189000, orders: 14250, visitors: 175200, conversion: 8.13 },
        change: data.change || { gmv: 11.66, orders: 13.28, visitors: 11.73, conversion: 1.37 }
      }
      
      if (data.details) {
        detailData.value = data.details
      } else {
        detailData.value = [
          { name: 'GMV', currentValue: '¥' + formatNumber(summaryData.value.current.gmv), compareValue: '¥' + formatNumber(summaryData.value.compare.gmv), change: summaryData.value.change.gmv },
          { name: '订单数', currentValue: formatNumber(summaryData.value.current.orders), compareValue: formatNumber(summaryData.value.compare.orders), change: summaryData.value.change.orders },
          { name: '访客数', currentValue: formatNumber(summaryData.value.current.visitors), compareValue: formatNumber(summaryData.value.compare.visitors), change: summaryData.value.change.visitors },
          { name: '转化率', currentValue: summaryData.value.current.conversion + '%', compareValue: summaryData.value.compare.conversion + '%', change: summaryData.value.change.conversion }
        ]
      }
      
      nextTick(() => initChart())
    }
  } catch (error) {
    console.error('Failed to load compare data:', error)
  } finally {
    loading.value = false
  }
}

const initChart = () => {
  if (!trendChartRef.value) return
  
  if (trendChart) {
    trendChart.dispose()
  }
  
  trendChart = echarts.init(trendChartRef.value)
  
  const labels = compareType.value === 'day' ? ['周一', '周二', '周三', '周四', '周五', '周六', '周日'] :
                 compareType.value === 'week' ? ['第1周', '第2周', '第3周', '第4周'] :
                 ['1月', '2月', '3月', '4月']
  
  const currentData = chartMetric.value === 'gmv' ? 
    [220000, 280000, 250000, 310000] :
    chartMetric.value === 'orders' ?
    [1500, 1800, 1650, 2000] :
    [18000, 22000, 20000, 24000]
  
  const compareData = chartMetric.value === 'gmv' ?
    [245000, 310000, 280000, 345000] :
    chartMetric.value === 'orders' ?
    [1680, 2000, 1820, 2250] :
    [20000, 24500, 22200, 26800]
  
  const option = {
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['当前周期', '对比周期']
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
      data: labels
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: '当前周期',
        type: 'line',
        smooth: true,
        data: currentData,
        itemStyle: { color: '#409eff' }
      },
      {
        name: '对比周期',
        type: 'line',
        smooth: true,
        data: compareData,
        itemStyle: { color: '#909399' }
      }
    ]
  }
  
  trendChart.setOption(option)
  window.addEventListener('resize', () => trendChart?.resize())
}

watch(chartMetric, () => {
  initChart()
})

onMounted(() => {
  refreshData()
})
</script>

<style scoped>
.compare-analysis {
  padding-bottom: 20px;
}

.filter-card {
  margin-bottom: 16px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.period-select {
  display: flex;
  align-items: center;
  gap: 8px;
}

.label {
  font-size: 14px;
  color: #606266;
}

.quick-buttons {
  display: flex;
  gap: 8px;
}

.summary-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.summary-card {
  position: relative;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.card-badge {
  font-size: 12px;
  color: #fff;
  background: #409eff;
  padding: 2px 8px;
  border-radius: 10px;
}

.card-content {
  padding-top: 12px;
}

.value-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.value-label {
  font-size: 13px;
  color: #909399;
}

.value {
  font-size: 18px;
  font-weight: 600;
}

.value.compare {
  color: #909399;
  font-size: 16px;
}

.change-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  padding-top: 8px;
  border-top: 1px dashed #ebeef5;
  margin-top: 8px;
}

.change-row.positive {
  color: #67c23a;
}

.change-row.negative {
  color: #f56c6c;
}

.chart-section {
  margin-bottom: 16px;
}

.chart-container {
  height: 320px;
}

.text-success {
  color: #67c23a;
}

.text-danger {
  color: #f56c6c;
}
</style>
