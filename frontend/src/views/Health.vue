<template>
  <div class="health-container">
    <div class="header">
      <h2>健康度评分</h2>
    </div>

    <el-row :gutter="20" class="summary-cards">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.avg_score }}</div>
          <div class="stat-label">平均健康分</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-col :span="8">
          <el-card class="level-card level-1">
            <div class="level-value">{{ distribution.excellent }}</div>
            <div class="level-label">优秀</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card class="level-card level-2">
            <div class="level-value">{{ distribution.good }}</div>
            <div class="level-label">良好</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card class="level-card level-3">
            <div class="level-value">{{ distribution.warning }}</div>
            <div class="level-label">预警</div>
          </el-card>
        </el-col>
      </el-col>
    </el-row>

    <el-card class="chart-card">
      <template #header>
        <span>健康度分布</span>
      </template>
      <div ref="chartRef" style="width: 100%; height: 300px;"></div>
    </el-card>

    <el-card class="list-card">
      <template #header>
        <span>商品健康度排名</span>
      </template>
      <el-table :data="healthList" stripe>
        <el-table-column prop="product_name" label="商品" />
        <el-table-column prop="health_score" label="健康分">
          <template #default="{ row }">
            <el-tag :type="getScoreType(row.health_score)">
              {{ row.health_score }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sales_score" label="销量" />
        <el-table-column prop="conversion_score" label="转化" />
        <el-table-column prop="roi_score" label="ROI" />
        <el-table-column prop="refund_score" label="退款" />
        <el-table-column prop="growth_score" label="增长" />
        <el-table-column prop="alert_dimensions" label="问题指标">
          <template #default="{ row }">
            <el-tag v-for="dim in row.alert_dimensions" :key="dim" type="danger" size="small">
              {{ dim }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" @click="refreshScore(row.product_id)">刷新</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import * as echarts from 'echarts'

const chartRef = ref(null)
let chart = null

const stats = ref({ avg_score: 0 })
const distribution = ref({ excellent: 0, good: 0, warning: 0 })
const healthList = ref([])

const loadHealth = async () => {
  try {
    const listRes = await axios.get('/api/health/list')
    if (listRes.data.code === 200) {
      healthList.value = listRes.data.data
    }

    const distRes = await axios.get('/api/health/distribution')
    if (distRes.data.code === 200) {
      distribution.value = distRes.data.data
    }

    const avgScore = healthList.value.reduce((sum, p) => sum + p.health_score, 0) / healthList.value.length || 0
    stats.value.avg_score = avgScore.toFixed(1)

    updateChart()
  } catch (error) {
    console.error('加载健康度失败:', error)
  }
}

const refreshScore = async (productId) => {
  try {
    await axios.post(`/api/health/refresh/${productId}`)
    ElMessage.success('刷新成功')
    loadHealth()
  } catch (error) {
    ElMessage.error('刷新失败')
  }
}

const getScoreType = (score) => {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'danger'
}

const updateChart = () => {
  if (!chart) return

  const data = [
    { value: distribution.value.excellent, name: '优秀(80+)' },
    { value: distribution.value.good, name: '良好(60-79)' },
    { value: distribution.value.warning, name: '预警(<60)' }
  ]

  chart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: '5%', left: 'center' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
      label: { show: true, formatter: '{b}: {c} ({d}%)' },
      data
    }]
  })
}

onMounted(() => {
  chart = echarts.init(chartRef.value)
  loadHealth()
  window.addEventListener('resize', () => chart?.resize())
})

onUnmounted(() => {
  chart?.dispose()
})
</script>

<style scoped>
.health-container {
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

.stat-card,
.level-card {
  text-align: center;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #409eff;
}

.stat-label {
  color: #909399;
  margin-top: 8px;
}

.level-value {
  font-size: 24px;
  font-weight: bold;
}

.level-label {
  font-size: 12px;
  color: #909399;
}

.level-1 { background: #f0f9eb; }
.level-2 { background: #fdf6ec; }
.level-3 { background: #fef0f0; }

.chart-card,
.list-card {
  margin-bottom: 20px;
}
</style>
