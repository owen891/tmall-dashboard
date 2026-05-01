<template>
  <div class="compare-analysis">
    <el-card class="filter-card">
      <div class="filter-row">
        <div class="period-select">
          <span class="label">对比周期:</span>
          <el-select v-model="compareType" size="small" @change="handleCompareChange">
            <el-option label="日对比" value="day" />
            <el-option label="周对比" value="week" />
            <el-option label="月对比" value="month" />
            <el-option label="季度对比" value="quarter" />
          </el-select>
        </div>
        
        <div class="cycle-group">
          <span class="label">基准周期:</span>
          <el-date-picker
            v-model="baseDate"
            type="date"
            placeholder="选择基准日期"
            size="small"
          />
        </div>
        
        <div class="cycle-group">
          <span class="label">对比周期:</span>
          <el-date-picker
            v-model="compareDate"
            type="date"
            placeholder="选择对比日期"
            size="small"
          />
        </div>
        
        <div class="quick-buttons">
          <el-button size="small" @click="quickCompare('lastWeek')">上周对比</el-button>
          <el-button size="small" @click="quickCompare('lastMonth')">上月对比</el-button>
          <el-button size="small" @click="quickCompare('lastQuarter')">上季度对比</el-button>
        </div>
        
        <el-button type="primary" size="small" @click="refreshData">执行对比</el-button>
      </div>
    </el-card>

    <div class="summary-cards">
      <el-card class="summary-card">
        <div class="card-header">
          <span class="card-title">GMV</span>
          <span class="card-badge">核心指标</span>
        </div>
        <div class="card-content">
          <div class="value-row">
            <span class="value-label">基准周期</span>
            <span class="value">¥{{ formatNumber(summaryData.base.gmv) }}</span>
          </div>
          <div class="value-row">
            <span class="value-label">对比周期</span>
            <span class="value">¥{{ formatNumber(summaryData.compare.gmv) }}</span>
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
            <span class="value-label">基准周期</span>
            <span class="value">{{ formatNumber(summaryData.base.orders) }}</span>
          </div>
          <div class="value-row">
            <span class="value-label">对比周期</span>
            <span class="value">{{ formatNumber(summaryData.compare.orders) }}</span>
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
            <span class="value-label">基准周期</span>
            <span class="value">{{ formatNumber(summaryData.base.visitors) }}</span>
          </div>
          <div class="value-row">
            <span class="value-label">对比周期</span>
            <span class="value">{{ formatNumber(summaryData.compare.visitors) }}</span>
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
            <span class="value-label">基准周期</span>
            <span class="value">{{ summaryData.base.conversion }}%</span>
          </div>
          <div class="value-row">
            <span class="value-label">对比周期</span>
            <span class="value">{{ summaryData.compare.conversion }}%</span>
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
      <el-card class="chart-card">
        <template #header>
          <span>指标趋势对比</span>
          <el-select v-model="chartType" size="small" style="float: right;">
            <el-option label="GMV" value="gmv" />
            <el-option label="订单数" value="orders" />
            <el-option label="访客数" value="visitors" />
            <el-option label="转化率" value="conversion" />
          </el-select>
        </template>
        <div ref="trendChartRef" class="chart-container"></div>
      </el-card>
    </div>

    <div class="detail-section">
      <el-card>
        <template #header>详细对比数据</template>
        <el-table :data="detailData" stripe size="small">
          <el-table-column prop="index" label="排名" width="60" />
          <el-table-column prop="name" label="指标名称" min-width="150" />
          <el-table-column prop="baseValue" label="基准周期" width="150" align="right" />
          <el-table-column prop="compareValue" label="对比周期" width="150" align="right" />
          <el-table-column prop="change" label="变化率" width="100" align="center">
            <template #default="{ row }">
              <span :class="row.change >= 0 ? 'text-success' : 'text-danger'">
                {{ row.change >= 0 ? '+' : '' }}{{ row.change }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.change)">{{ getStatusText(row.change) }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { ArrowUp, ArrowDown } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

const compareType = ref('week')
const baseDate = ref(new Date())
const compareDate = ref(new Date())
const chartType = ref('gmv')

const summaryData = ref({
  base: { gmv: 2856000, orders: 12580, visitors: 156800, conversion: 8.02 },
  compare: { gmv: 3189000, orders: 14250, visitors: 175200, conversion: 8.13 },
  change: { gmv: 11.66, orders: 13.28, visitors: 11.73, conversion: 1.37 }
})

const detailData = ref([
  { index: 1, name: 'GMV', baseValue: '¥2,856,000', compareValue: '¥3,189,000', change: 11.66 },
  { index: 2, name: '订单数', baseValue: '12,580', compareValue: '14,250', change: 13.28 },
  { index: 3, name: '访客数', baseValue: '156,800', compareValue: '175,200', change: 11.73 },
  { index: 4, name: '转化率', baseValue: '8.02%', compareValue: '8.13%', change: 1.37 },
  { index: 5, name: '客单价', baseValue: '¥227', compareValue: '¥224', change: -1.32 },
  { index: 6, name: '退款率', baseValue: '2.35%', compareValue: '2.18%', change: -7.23 },
  { index: 7, name: '好评率', baseValue: '96.8%', compareValue: '97.2%', change: 0.41 },
  { index: 8, name: '广告花费', baseValue: '¥156,000', compareValue: '¥178,000', change: 14.10 },
  { index: 9, name: 'ROI', baseValue: '3.25', compareValue: '3.42', change: 5.23 },
  { index: 10, name: '库存周转', baseValue: '15.6天', compareValue: '14.2天', change: -9.0 }
])

const trendChartRef = ref(null)
let trendChart = null

const formatNumber = (num) => {
  return num.toLocaleString()
}

const quickCompare = (type) => {
  const now = new Date()
  baseDate.value = new Date(now)
  
  if (type === 'lastWeek') {
    compareDate.value = new Date(now.setDate(now.getDate() - 7))
  } else if (type === 'lastMonth') {
    compareDate.value = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate())
  } else if (type === 'lastQuarter') {
    compareDate.value = new Date(now.getFullYear(), now.getMonth() - 3, now.getDate())
  }
}

const handleCompareChange = () => {
  refreshData()
}

const refreshData = () => {
  nextTick(() => initChart())
}

const getStatusType = (change) => {
  if (change >= 5) return 'success'
  if (change >= 0) return 'info'
  if (change > -5) return 'warning'
  return 'danger'
}

const getStatusText = (change) => {
  if (change >= 5) return '优秀'
  if (change >= 0) return '正常'
  if (change > -5) return '关注'
  return '预警'
}

const initChart = () => {
  if (!trendChartRef.value) return
  
  if (trendChart) {
    trendChart.dispose()
  }
  
  trendChart = echarts.init(trendChartRef.value)
  
  const labels = compareType.value === 'day' ? ['周一', '周二', '周三', '周四', '周五', '周六', '周日'] :
                 compareType.value === 'week' ? ['第1周', '第2周', '第3周', '第4周'] :
                 ['1月', '2月', '3月']
  
  const baseData = chartType.value === 'gmv' ? [220, 280, 250, 310, 290, 350, 320] :
                   chartType.value === 'orders' ? [150, 180, 165, 200, 185, 220, 205] :
                   chartType.value === 'visitors' ? [1800, 2200, 2000, 2400, 2250, 2600, 2450] :
                   [7.2, 7.8, 7.5, 8.2, 8.0, 8.5, 8.3]
  
  const compareData = chartType.value === 'gmv' ? [245, 310, 280, 345, 320, 385, 355] :
                      chartType.value === 'orders' ? [168, 200, 182, 225, 208, 248, 230] :
                      chartType.value === 'visitors' ? [2000, 2450, 2220, 2680, 2500, 2900, 2720] :
                      [7.5, 8.2, 7.8, 8.6, 8.4, 8.8, 8.5]
  
  const option = {
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['基准周期', '对比周期']
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
        name: '基准周期',
        type: 'line',
        smooth: true,
        data: baseData,
        lineStyle: { color: '#909399', width: 2 },
        itemStyle: { color: '#909399' }
      },
      {
        name: '对比周期',
        type: 'line',
        smooth: true,
        data: compareData,
        lineStyle: { color: '#409eff', width: 2 },
        itemStyle: { color: '#409eff' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
            { offset: 1, color: 'rgba(64, 158, 255, 0.05)' }
          ])
        }
      }
    ]
  }
  
  trendChart.setOption(option)
  
  window.addEventListener('resize', () => {
    trendChart?.resize()
  })
}

watch(chartType, () => {
  initChart()
})

onMounted(() => {
  nextTick(() => initChart())
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

.period-select, .cycle-group {
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

.chart-card {
  min-height: 400px;
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
