<template>
  <div class="trends-container">
    <div class="header">
      <h2>趋势分析</h2>
      <div class="controls">
        <el-select v-model="dimension" @change="loadTrends" placeholder="时间维度">
          <el-option label="日" value="daily" />
          <el-option label="周" value="weekly" />
          <el-option label="月" value="monthly" />
        </el-select>
        <el-select v-model="productId" @change="loadTrends" placeholder="选择商品" clearable>
          <el-option v-for="p in products" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </div>
    </div>

    <el-card class="chart-card">
      <div ref="chartRef" style="width: 100%; height: 400px;"></div>
    </el-card>

    <el-card class="events-card">
      <template #header>
        <div class="card-header">
          <span>事件标记</span>
          <el-button type="primary" size="small" @click="showAddEvent = true">添加事件</el-button>
        </div>
      </template>
      <el-table :data="events" stripe>
        <el-table-column prop="event_date" label="日期" width="120" />
        <el-table-column prop="event_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag>{{ row.event_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" />
        <el-table-column prop="description" label="描述" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="danger" size="small" @click="deleteEvent(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showAddEvent" title="添加事件" width="400px">
      <el-form :model="eventForm" label-width="80px">
        <el-form-item label="日期">
          <el-date-picker v-model="eventForm.event_date" type="date" placeholder="选择日期" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="eventForm.event_type" placeholder="选择类型">
            <el-option label="活动" value="activity" />
            <el-option label="改价" value="price_change" />
            <el-option label="优化" value="optimization" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="eventForm.title" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="eventForm.description" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddEvent = false">取消</el-button>
        <el-button type="primary" @click="addEvent">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import * as echarts from 'echarts'

const chartRef = ref(null)
let chart = null

const dimension = ref('weekly')
const productId = ref(null)
const products = ref([])
const trends = ref([])
const events = ref([])
const showAddEvent = ref(false)
const eventForm = ref({
  event_date: '',
  event_type: '',
  title: '',
  description: ''
})

const loadProducts = async () => {
  try {
    const res = await axios.get('/api/products')
    if (res.data.code === 200) {
      products.value = res.data.data
    }
  } catch (error) {
    console.error('加载商品失败:', error)
  }
}

const loadTrends = async () => {
  try {
    let url = productId.value
      ? `/api/trends/product/${productId.value}?dimension=${dimension.value}`
      : `/api/trends/shop?dimension=${dimension.value}`

    const res = await axios.get(url)
    if (res.data.code === 200) {
      trends.value = res.data.data
      updateChart()
    }

    const eventsRes = await axios.get('/api/trends/events')
    if (eventsRes.data.code === 200) {
      events.value = eventsRes.data.data
    }
  } catch (error) {
    console.error('加载趋势失败:', error)
  }
}

const addEvent = async () => {
  try {
    await axios.post('/api/trends/events', {
      ...eventForm.value,
      product_id: productId.value
    })
    ElMessage.success('添加成功')
    showAddEvent.value = false
    eventForm.value = { event_date: '', event_type: '', title: '', description: '' }
    loadTrends()
  } catch (error) {
    ElMessage.error('添加失败')
  }
}

const deleteEvent = async (id) => {
  try {
    await axios.delete(`/api/trends/events/${id}`)
    ElMessage.success('删除成功')
    loadTrends()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

const updateChart = () => {
  if (!chart) return

  const dates = trends.value.map(t => t.date)
  const series = [
    { name: 'GMV', data: trends.value.map(t => t.gmv) },
    { name: '访客', data: trends.value.map(t => t.visitors) },
    { name: '转化率(%)', data: trends.value.map(t => t.conversion) },
    { name: 'ROI', data: trends.value.map(t => t.roi) }
  ]

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: series.map(s => s.name) },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: dates },
    yAxis: [
      { type: 'value', name: '金额/访客' },
      { type: 'value', name: '比率(%)', min: 0, max: 10 }
    ],
    series: series.map((s, i) => ({
      name: s.name,
      type: 'line',
      data: s.data,
      yAxisIndex: i >= 2 ? 1 : 0
    }))
  })
}

onMounted(() => {
  chart = echarts.init(chartRef.value)
  loadProducts()
  loadTrends()
  window.addEventListener('resize', () => chart?.resize())
})

onUnmounted(() => {
  chart?.dispose()
})
</script>

<style scoped>
.trends-container {
  padding: 20px;
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
