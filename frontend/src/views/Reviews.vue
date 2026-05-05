<template>
  <div class="reviews-container">
    <div class="header">
      <h2>评价分析</h2>
    </div>

    <el-row :gutter="20" class="summary-cards">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ summary.total_reviews }}</div>
          <div class="stat-label">总评价数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ summary.avg_rating }}</div>
          <div class="stat-label">平均评分</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card positive">
          <div class="stat-value">{{ summary.positive_rate }}%</div>
          <div class="stat-label">好评率</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card negative">
          <div class="stat-value">{{ summary.negative_count }}</div>
          <div class="stat-label">差评数</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <span>情感分布</span>
          </template>
          <div ref="sentimentChartRef" style="width: 100%; height: 280px;"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <span>评分分布</span>
          </template>
          <div ref="ratingChartRef" style="width: 100%; height: 280px;"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="keywords-card">
      <template #header>
        <span>热点关键词</span>
      </template>
      <div class="keywords">
        <el-tag v-for="kw in summary.keywords" :key="kw" type="info" size="large" class="keyword-tag">
          {{ kw }}
        </el-tag>
      </div>
    </el-card>

    <el-card class="list-card">
      <template #header>
        <span>评价列表</span>
      </template>
      <el-table :data="reviews" stripe>
        <el-table-column prop="review_date" label="日期" width="120" />
        <el-table-column prop="product_name" label="商品" width="150" />
        <el-table-column prop="rating" label="评分" width="80">
          <template #default="{ row }">
            <el-rate v-model="row.rating" disabled />
          </template>
        </el-table-column>
        <el-table-column prop="sentiment" label="情感" width="80">
          <template #default="{ row }">
            <el-tag :type="getSentimentType(row.sentiment)" size="small">
              {{ getSentimentLabel(row.sentiment) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="评价内容" />
        <el-table-column prop="reviewer_type" label="买家类型" width="100" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/api'
import * as echarts from 'echarts'

const sentimentChartRef = ref(null)
const ratingChartRef = ref(null)
let sentimentChart = null
let ratingChart = null
let handleResize = null

const summary = ref({
  total_reviews: 0,
  avg_rating: 0,
  positive_rate: 0,
  positive_count: 0,
  negative_count: 0,
  neutral_count: 0,
  keywords: []
})
const sentimentDistribution = ref({ positive: 0, negative: 0, neutral: 0 })
const ratingDistribution = ref([])
const reviews = ref([])

const loadData = async () => {
  try {
    const summaryRes = await api.get('/reviews/summary')
    if ((summaryRes.code === 200 || summaryRes.data) && summaryRes.data) {
      summary.value = summaryRes.data || summaryRes
    }

    const sentimentRes = await api.get('/reviews/sentiment-distribution')
    if (sentimentRes.code === 200 || sentimentRes.data) {
      sentimentDistribution.value = sentimentRes.data || sentimentRes
      updateSentimentChart()
    }

    const ratingRes = await api.get('/reviews/rating-distribution')
    if (ratingRes.code === 200 || ratingRes.data) {
      ratingDistribution.value = ratingRes.data || ratingRes
      updateRatingChart()
    }

    const listRes = await api.get('/reviews/list?page_size=20')
    if (listRes.code === 200 || listRes.data) {
      reviews.value = listRes.data?.reviews || listRes.data || []
    }
  } catch (error) {
    console.error('加载评价数据失败:', error)
  }
}

const updateSentimentChart = () => {
  if (!sentimentChart) return

  const data = [
    { value: sentimentDistribution.value.positive?.count || 0, name: '好评' },
    { value: sentimentDistribution.value.negative?.count || 0, name: '差评' },
    { value: sentimentDistribution.value.neutral?.count || 0, name: '中评' }
  ]

  sentimentChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: '5%', left: 'center' },
    series: [{
      type: 'pie',
      radius: '60%',
      data,
      label: { formatter: '{b}: {c} ({d}%)' }
    }]
  })
}

const updateRatingChart = () => {
  if (!ratingChart) return

  const data = ratingDistribution.value.map(r => ({
    value: r.count,
    name: `${r.rating}星`
  }))

  ratingChart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: ratingDistribution.value.map(r => `${r.rating}星`) },
    yAxis: { type: 'value', name: '数量' },
    series: [{ type: 'bar', data: data.map(d => d.value) }]
  })
}

const getSentimentType = (sentiment) => {
  const map = { positive: 'success', negative: 'danger', neutral: 'info' }
  return map[sentiment] || 'info'
}

const getSentimentLabel = (sentiment) => {
  const map = { positive: '好评', negative: '差评', neutral: '中评' }
  return map[sentiment] || '未知'
}

onMounted(() => {
  sentimentChart = echarts.init(sentimentChartRef.value)
  ratingChart = echarts.init(ratingChartRef.value)
  loadData()
  handleResize = () => {
    sentimentChart?.resize()
    ratingChart?.resize()
  }
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  sentimentChart?.dispose()
  ratingChart?.dispose()
})
</script>

<style scoped>
.reviews-container {
  padding: 20px;
}

.header {
  margin-bottom: 20px;
}

.header h2 {
  margin: 0;
}

.summary-cards {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #409eff;
}

.stat-label {
  color: #909399;
  margin-top: 5px;
}

.stat-card.positive .stat-value { color: #67c23a; }
.stat-card.negative .stat-value { color: #f56c6c; }

.chart-card,
.keywords-card,
.list-card {
  margin-bottom: 20px;
}

.keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.keyword-tag {
  font-size: 14px;
  padding: 8px 16px;
}
</style>
