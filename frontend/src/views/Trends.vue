<template>
  <div class="page-container trends-page">
    <div class="header">
      <h2>趋势分析</h2>
      <div class="controls">
        <el-select v-model="dimension" @change="loadTrends" placeholder="时间维度">
          <el-option label="日" value="daily" />
          <el-option label="周" value="weekly" />
          <el-option label="月" value="monthly" />
        </el-select>
        <el-select v-model="productId" @change="loadTrends" placeholder="选择商品" clearable>
          <el-option v-for="p in products" :key="p.product_id" :label="p.title" :value="p.product_id" />
        </el-select>
      </div>
    </div>

    <el-card class="chart-card">
      <div ref="chartRef" style="width: 100%; height: 300px;"></div>
    </el-card>

    <el-card class="events-card">
      <template #header>
        <div class="card-header">
          <span>事件标记</span>
          <el-button type="primary" size="small" @click="showEventDialog = true">添加事件</el-button>
        </div>
      </template>
      <el-table :data="eventList" stripe>
        <el-table-column prop="event_date" label="日期" width="120" />
        <el-table-column prop="event_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag>{{ row.event_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="danger" size="small" @click="deleteEvent(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showEventDialog" title="添加事件" width="400px">
      <el-form :model="eventForm" label-width="80px">
        <el-form-item label="日期">
          <el-date-picker v-model="eventForm.event_date" type="date" placeholder="选择日期" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="eventForm.event_type" placeholder="选择类型">
            <el-option label="活动" value="activity" />
            <el-option label="改价" value="price_change" />
            <el-option label="优化" value="optimization" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="eventForm.description" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEventDialog = false">取消</el-button>
        <el-button type="primary" @click="submitEvent">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import api from '@/api'

const chartRef = ref(null)
let trendChart = null
let handleResize = null

const dimension = ref('weekly')
const productId = ref(null)
const products = ref([])
const trendData = ref([])
const eventList = ref([])
const showEventDialog = ref(false)
const eventForm = ref({
  event_date: '',
  event_type: '',
  description: ''
})

const loadProducts = async () => {
  try {
    const res = await api.getProducts({ limit: 100 })
    if (res.code === 200 || res.data) {
      products.value = res.data?.data || []
    }
  } catch (error) {
    console.error('Load products error:', error)
  }
}

const loadTrends = async () => {
  try {
    const [trendRes, eventsRes] = await Promise.all([
      api.getTrendsData(productId.value, dimension.value),
      api.getTrendEvents()
    ])
    
    if (trendRes.code === 200 || trendRes.data) {
      trendData.value = trendRes.data?.trend || trendRes.data || []
      updateChart()
    }
    
    if (eventsRes.code === 200 || eventsRes.data) {
      eventList.value = eventsRes.data?.events || eventsRes.data || []
    }
  } catch (error) {
    console.error('Load trends error:', error)
  }
}

const submitEvent = async () => {
  if (!eventForm.value.event_type || !eventForm.value.description) {
    ElMessage.warning('请填写完整信息')
    return
  }
  try {
    await api.addTrendEvent({
      ...eventForm.value,
      product_id: productId.value,
      date: eventForm.value.event_date || new Date().toISOString().split('T')[0]
    })
    ElMessage.success('添加成功')
    showEventDialog.value = false
    eventForm.value = { event_date: '', event_type: '', description: '' }
    loadTrends()
  } catch (error) {
    ElMessage.error('添加失败')
  }
}

const deleteEvent = async (id) => {
  try {
    await api.deleteTrendEvent(id)
    ElMessage.success('删除成功')
    loadTrends()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

const updateChart = () => {
  if (!chartRef.value) return
  
  if (trendChart) {
    trendChart.dispose()
  }
  
  trendChart = echarts.init(chartRef.value)
  
  const dates = trendData.value.map(t => t.week_start || t.period || t.date)
  const series = [
    { name: 'GMV', data: trendData.value.map(t => t.net_sales || t.payment_amount) },
    { name: '访客', data: trendData.value.map(t => t.visitors) },
    { name: '转化率(%)', data: trendData.value.map(t => (t.conversion || 0) * 100) },
    { name: 'ROI', data: trendData.value.map(t => t.roi || 0) }
  ]
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      data: series.map(s => s.name),
      bottom: 0
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false
    },
    yAxis: [
      {
        type: 'value',
        name: '金额/访客',
        splitLine: { show: true }
      },
      {
        type: 'value',
        name: '百分比',
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: 'GMV',
        type: 'line',
        data: series[0].data,
        smooth: true,
        yAxisIndex: 0
      },
      {
        name: '访客',
        type: 'line',
        data: series[1].data,
        smooth: true,
        yAxisIndex: 0
      },
      {
        name: '转化率(%)',
        type: 'line',
        data: series[2].data,
        smooth: true,
        yAxisIndex: 1
      },
      {
        name: 'ROI',
        type: 'line',
        data: series[3].data,
        smooth: true,
        yAxisIndex: 1
      }
    ]
  }
  
  trendChart.setOption(option)
}

onMounted(async () => {
  await loadProducts()
  await loadTrends()
  handleResize = () => trendChart?.resize()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
})
</script>

<style scoped>
.trends-page {
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header h2 {
  margin: 0;
}

.controls {
  display: flex;
  gap: 10px;
}

.chart-card,
.events-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
