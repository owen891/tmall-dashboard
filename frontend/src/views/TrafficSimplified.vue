<template>
  <div class="traffic-page">
    <div class="page-header">
      <div class="header-left">
        <h2>📊 流量投放</h2>
        <span class="subtitle">流量分析与推广效果</span>
      </div>
      <div class="header-right">
        <el-select v-model="dateRange" style="width: 180px">
          <el-option label="近7天" value="7" />
          <el-option label="近30天" value="30" />
        </el-select>
        <el-button type="primary" @click="refresh">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-icon" style="background: #409eff">💰</div>
          <div class="stat-content">
            <div class="stat-value">¥{{ formatNumber(stats.totalCost) }}</div>
            <div class="stat-label">总消耗</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-icon" style="background: #67c23a">📈</div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.totalROI }}</div>
            <div class="stat-label">整体ROI</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-icon" style="background: #e6a23c">👥</div>
          <div class="stat-content">
            <div class="stat-value">{{ formatNumber(stats.totalVisitors) }}</div>
            <div class="stat-label">访客数</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-icon" style="background: #f56c6c">🎯</div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.conversionRate }}%</div>
            <div class="stat-label">转化率</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="content-section">
      <el-tabs v-model="activeTab" type="card" class="content-tabs">
        <el-tab-pane label="流量分析" name="traffic">
          <el-row :gutter="20" style="margin-bottom: 20px">
            <el-col :span="16">
              <div class="chart-card">
                <div class="chart-header">
                  <h3>📊 流量趋势</h3>
                </div>
                <div ref="trafficChartRef" class="chart-container"></div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="chart-card">
                <div class="chart-header">
                  <h3>🎯 流量来源</h3>
                </div>
                <div ref="sourceChartRef" class="chart-container"></div>
              </div>
            </el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane label="推广效果" name="ad">
          <div class="table-container">
            <el-table :data="adCampaigns" stripe style="width: 100%">
              <el-table-column prop="name" label="推广计划" min-width="200" />
              <el-table-column prop="type" label="类型" width="120">
                <template #default="{ row }">
                  <el-tag size="small">{{ row.type }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="cost" label="消耗" width="120" align="right">
                <template #default="{ row }">
                  ¥{{ formatNumber(row.cost) }}
                </template>
              </el-table-column>
              <el-table-column prop="gmv" label="GMV" width="120" align="right">
                <template #default="{ row }">
                  ¥{{ formatNumber(row.gmv) }}
                </template>
              </el-table-column>
              <el-table-column prop="roi" label="ROI" width="100" align="right">
                <template #default="{ row }">
                  <span :style="{ color: row.roi >= 3 ? '#67c23a' : row.roi >= 2 ? '#e6a23c' : '#f56c6c' }">
                    {{ row.roi }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="visitors" label="访客" width="100" align="right">
                <template #default="{ row }">
                  {{ formatNumber(row.visitors) }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="100">
                <template #default="{ row }">
                  <el-button size="small" text>详情</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

const activeTab = ref('traffic')
const dateRange = ref('7')
const trafficChartRef = ref(null)
const sourceChartRef = ref(null)
const charts = reactive({ traffic: null, source: null })

const stats = reactive({
  totalCost: 12345,
  totalROI: 3.87,
  totalVisitors: 45678,
  conversionRate: 3.2
})

const adCampaigns = ref([
  { id: 1, name: '万相台-爆款拉新', type: '万相台', cost: 3456, gmv: 12345, roi: 3.57, visitors: 4567 },
  { id: 2, name: '直通车-精准词', type: '直通车', cost: 2345, gmv: 7654, roi: 3.26, visitors: 3456 },
  { id: 3, name: '引力魔方-首页', type: '引力魔方', cost: 4567, gmv: 15678, roi: 3.43, visitors: 5678 },
  { id: 4, name: '超级推荐-猜你喜欢', type: '超级推荐', cost: 1977, gmv: 4567, roi: 2.31, visitors: 2345 }
])

const formatNumber = (num) => {
  if (!num && num !== 0) return '0'
  num = Number(num)
  if (num >= 10000) return (num / 10000).toFixed(2) + '万'
  return num.toLocaleString()
}

const refresh = () => ElMessage.success('数据已刷新')

const initCharts = () => {
  if (charts.traffic) {
    charts.traffic.dispose()
    charts.traffic = null
  }
  if (charts.source) {
    charts.source.dispose()
    charts.source = null
  }
  if (trafficChartRef.value) charts.traffic = echarts.init(trafficChartRef.value)
  if (sourceChartRef.value) charts.source = echarts.init(sourceChartRef.value)
}

const updateTrafficChart = () => {
  if (!charts.traffic) return
  const dates = ['1号', '2号', '3号', '4号', '5号', '6号', '7号']
  const data1 = [3200, 3800, 4500, 4200, 5200, 4800, 5600]
  const data2 = [2800, 3200, 3800, 3600, 4200, 4000, 4500]
  charts.traffic.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['访客数', '点击量'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
    xAxis: { type: 'category', data: dates },
    yAxis: [
      { type: 'value', name: '访客数', position: 'left' },
      { type: 'value', name: '点击量', position: 'right' }
    ],
    series: [
      { name: '访客数', type: 'line', data: data1, smooth: true, itemStyle: { color: '#409eff' }, areaStyle: { opacity: 0.3 } },
      { name: '点击量', type: 'line', yAxisIndex: 1, data: data2, smooth: true, itemStyle: { color: '#67c23a' } }
    ]
  })
}

const updateSourceChart = () => {
  if (!charts.source) return
  charts.source.setOption({
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie',
      radius: '60%',
      data: [
        { value: 1048, name: '搜索流量', itemStyle: { color: '#409eff' } },
        { value: 735, name: '推荐流量', itemStyle: { color: '#67c23a' } },
        { value: 580, name: '付费流量', itemStyle: { color: '#e6a23c' } },
        { value: 484, name: '免费流量', itemStyle: { color: '#f56c6c' } }
      ],
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      }
    }]
  })
}

const updateCharts = () => {
  updateTrafficChart()
  updateSourceChart()
}

const handleResize = () => {
  if (charts.traffic) charts.traffic.resize()
  if (charts.source) charts.source.resize()
}

onMounted(async () => {
  await nextTick()
  initCharts()
  updateCharts()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (charts.traffic) {
    charts.traffic.dispose()
    charts.traffic = null
  }
  if (charts.source) {
    charts.source.dispose()
    charts.source = null
  }
})
</script>

<style scoped>
.traffic-page {
  padding: 20px;
  background: #f5f7fa;
  min-height: 100%;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  background: white;
  padding: 20px 24px;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.header-left h2 {
  font-size: 20px;
  font-weight: 600;
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

.stats-row {
  margin-bottom: 24px;
}

.stat-card {
  display: flex;
  align-items: center;
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  margin-right: 16px;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #303133;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.content-section {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.content-tabs {
  margin-bottom: 20px;
}

.chart-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.chart-header h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  color: #303133;
}

.chart-container {
  height: 300px;
}

.table-container {
  min-height: 400px;
}
</style>
