<template>
  <div class="page-container health-page">
    <div class="header">
      <h2>商品健康度评分</h2>
    </div>

    <el-row :gutter="20" class="summary-cards">
      <el-col :span="4">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.product_count }}</div>
          <div class="stat-label">商品总数</div>
        </el-card>
      </el-col>
      <el-col :span="5">
        <el-card class="level-card level-excellent">
          <div class="level-value">{{ stats.excellent_count }}</div>
          <div class="level-label">优秀</div>
        </el-card>
      </el-col>
      <el-col :span="5">
        <el-card class="level-card level-good">
          <div class="level-value">{{ stats.good_count }}</div>
          <div class="level-label">良好</div>
        </el-card>
      </el-col>
      <el-col :span="5">
        <el-card class="level-card level-warning">
          <div class="level-value">{{ stats.warning_count }}</div>
          <div class="level-label">关注</div>
        </el-card>
      </el-col>
      <el-col :span="5">
        <el-card class="level-card level-danger">
          <div class="level-value">{{ stats.danger_count }}</div>
          <div class="level-label">预警</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="chart-card">
      <template #header>
        <span>健康度分布</span>
      </template>
      <div ref="chartRef" style="width: 100%; height: 300px;"></div>
    </el-card>

    <el-card class="dimension-card">
      <template #header>
        <span>12维度平均得分</span>
      </template>
      <div class="dimension-bars">
        <div v-for="dim in dimensions" :key="dim.key" class="dimension-item">
          <div class="dimension-label">{{ dim.label }}</div>
          <div class="dimension-bar-wrapper">
            <div 
              class="dimension-bar" 
              :style="{ 
                width: (dimensionAvgScores[dim.key] || 50) + '%',
                background: getBarColor(dimensionAvgScores[dim.key] || 50)
              }"
            ></div>
          </div>
          <div class="dimension-score">{{ dimensionAvgScores[dim.key] || 50 }}</div>
          <div class="dimension-weight">{{ (dim.weight * 100).toFixed(0) }}%</div>
        </div>
      </div>
    </el-card>

    <el-card class="list-card">
      <template #header>
        <div class="card-header">
          <span>商品健康度排名</span>
          <el-select v-model="healthLevelFilter" placeholder="筛选等级" clearable size="small" style="width: 120px;">
            <el-option label="优秀" value="优秀" />
            <el-option label="良好" value="良好" />
            <el-option label="关注" value="关注" />
            <el-option label="预警" value="预警" />
          </el-select>
        </div>
      </template>
      <el-table :data="filteredHealthList" stripe v-loading="loading" empty-text="暂无健康度数据">
        <el-table-column prop="product_name" label="商品" min-width="180">
          <template #default="{ row }">
            <div class="product-cell">
              <span class="product-title">{{ row.product_name }}</span>
              <span class="product-tags">
                <el-tag v-if="row.tier" size="small" type="info">{{ row.tier }}</el-tag>
                <el-tag v-if="row.style" size="small">{{ row.style }}</el-tag>
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="health_score" label="健康分" width="100" sortable>
          <template #default="{ row }">
            <el-tag :type="getScoreType(row.health_score)" size="large">
              {{ row.health_score }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="health_level" label="等级" width="80">
          <template #default="{ row }">
            <el-tag :type="getLevelType(row.health_level)" size="small">
              {{ row.health_level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column v-for="dim in dimensions" :key="dim.key" :prop="dim.key" :label="dim.label" width="80">
          <template #default="{ row }">
            <span :style="{ color: getScoreColor(row.scores?.[dim.key] || 50) }">
              {{ row.scores?.[dim.key]?.toFixed(0) || '--' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="alert_dimensions" label="预警维度" min-width="150">
          <template #default="{ row }">
            <el-tag 
              v-for="alert in row.alert_dimensions?.slice(0, 3)" 
              :key="alert.key" 
              type="danger" 
              size="small"
              style="margin: 2px;"
            >
              {{ alert.label }}
            </el-tag>
            <span v-if="!row.alert_dimensions?.length" style="color: #67c23a;">无</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="showDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="detailVisible" title="商品健康度详情" width="700px">
      <div v-if="selectedProduct" class="detail-content">
        <div class="detail-header">
          <div class="detail-title">{{ selectedProduct.product_name }}</div>
          <div class="detail-score">
            <el-tag :type="getScoreType(selectedProduct.health_score)" size="large">
              {{ selectedProduct.health_score }}
            </el-tag>
            <el-tag :type="getLevelType(selectedProduct.health_level)" style="margin-left: 8px;">
              {{ selectedProduct.health_level }}
            </el-tag>
          </div>
        </div>
        
        <div class="detail-dimensions">
          <h4>12维度评分</h4>
          <div v-for="dim in dimensions" :key="dim.key" class="detail-dim-item">
            <div class="detail-dim-label">{{ dim.label }}</div>
            <div class="detail-dim-bar-wrapper">
              <div 
                class="detail-dim-bar" 
                :style="{ 
                  width: (selectedProduct.scores?.[dim.key] || 50) + '%',
                  background: getBarColor(selectedProduct.scores?.[dim.key] || 50)
                }"
              ></div>
            </div>
            <div class="detail-dim-score">{{ selectedProduct.scores?.[dim.key]?.toFixed(0) || 50 }}</div>
            <div class="detail-dim-weight">{{ (dim.weight * 100).toFixed(0) }}%</div>
          </div>
        </div>

        <div class="detail-alerts" v-if="selectedProduct.alert_dimensions?.length">
          <h4>预警维度</h4>
          <el-tag 
            v-for="alert in selectedProduct.alert_dimensions" 
            :key="alert.key" 
            type="danger"
            style="margin: 4px;"
          >
            {{ alert.label }} ({{ alert.score }})
          </el-tag>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useChartManager } from '@/composables/useChartManager'
import api from '@/api'
import { useTimeStore } from '@/stores/time'

const timeStore = useTimeStore()

const chartManager = useChartManager()
const chartRef = ref(null)

const loading = ref(false)
const stats = ref({ product_count: 0, excellent_count: 0, good_count: 0, warning_count: 0, danger_count: 0 })
const dimensionAvgScores = ref({})
const healthList = ref([])
const healthLevelFilter = ref('')
const detailVisible = ref(false)
const selectedProduct = ref(null)

const dimensions = [
  { key: 'gmv_change_score', label: 'GSV环比', weight: 0.15 },
  { key: 'ad_spend_change_score', label: '推广花费环比', weight: 0.08 },
  { key: 'roi_change_score', label: 'ROI环比', weight: 0.10 },
  { key: 'refund_rate_score', label: '退款率', weight: 0.10 },
  { key: 'cart_rate_score', label: '加购率', weight: 0.08 },
  { key: 'search_ratio_score', label: '引潜比', weight: 0.07 },
  { key: 'new_customer_cost_score', label: '拉新成本', weight: 0.07 },
  { key: 'direct_cart_cost_score', label: '直接加购成本', weight: 0.05 },
  { key: 'total_cart_cost_score', label: '总加购成本', weight: 0.05 },
  { key: 'repurchase_rate_score', label: '复购率', weight: 0.08 },
  { key: 'cross_sell_rate_score', label: '连带率', weight: 0.07 },
  { key: 'search_ctr_vs_industry_score', label: '搜索CTRvs行业', weight: 0.10 },
]

const filteredHealthList = computed(() => {
  if (!healthLevelFilter.value) return healthList.value
  return healthList.value.filter(p => p.health_level === healthLevelFilter.value)
})

const loadHealth = async () => {
  loading.value = true
  try {
    const params = {}
    if (timeStore.startDate && timeStore.endDate) {
      params.start_date = timeStore.startDate
      params.end_date = timeStore.endDate
    }

    const [listRes, summaryRes] = await Promise.all([
      api.getHealthList({ page_size: 100, ...params }),
      api.getHealthSummary(params)
    ])

    if (listRes.data) {
      healthList.value = listRes.data?.products || []
    }

    if (summaryRes.data) {
      stats.value = summaryRes.data?.summary || {}
      dimensionAvgScores.value = summaryRes.data?.summary?.dimension_avg_scores || {}
    }

    updateChart()
  } catch (error) {
    ElMessage.error('加载健康度数据失败')
    console.error('加载健康度失败:', error)
    healthList.value = []
  } finally {
    loading.value = false
  }
}

const showDetail = (product) => {
  selectedProduct.value = product
  detailVisible.value = true
}

const getScoreType = (score) => {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'danger'
}

const getLevelType = (level) => {
  const types = {
    '优秀': 'success',
    '良好': 'primary',
    '关注': 'warning',
    '预警': 'danger'
  }
  return types[level] || 'info'
}

const getScoreColor = (score) => {
  if (score >= 80) return '#67c23a'
  if (score >= 60) return '#e6a23c'
  if (score >= 40) return '#f56c6c'
  return '#f56c6c'
}

const getBarColor = (score) => {
  if (score >= 80) return '#67c23a'
  if (score >= 60) return '#409eff'
  if (score >= 40) return '#e6a23c'
  return '#f56c6c'
}

const updateChart = () => {
  if (!chartRef.value) return

  const data = [
    { value: stats.value.excellent_count, name: '优秀', itemStyle: { color: '#67c23a' } },
    { value: stats.value.good_count, name: '良好', itemStyle: { color: '#409eff' } },
    { value: stats.value.warning_count, name: '关注', itemStyle: { color: '#e6a23c' } },
    { value: stats.value.danger_count, name: '预警', itemStyle: { color: '#f56c6c' } },
  ].filter(d => d.value > 0)

  const total = stats.value.product_count || 1
  if (data.length === 0) {
    chartManager.showEmpty(chartRef, '暂无健康度数据')
    return
  }

  chartManager.initChart(chartRef)
  chartManager.setOption(chartRef, {
    tooltip: { trigger: 'item', formatter: '{b}: {c}件 ({d}%)' },
    legend: { bottom: '5%', left: 'center' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
      label: { show: true, formatter: '{b}: {c}' },
      data: data
    }]
  })
}

onMounted(() => {
  chartManager.initChart(chartRef)
  chartManager.setupResize()
  loadHealth()
})

watch(() => [timeStore.startDate, timeStore.endDate], () => {
  loadHealth()
})
</script>

<style scoped>
.health-page {
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

.stat-card, .level-card {
  text-align: center;
}

.stat-value {
  font-size: 28px;
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

.level-excellent { background: #f0f9eb; }
.level-excellent .level-value { color: #67c23a; }
.level-good { background: #ecf5ff; }
.level-good .level-value { color: #409eff; }
.level-warning { background: #fdf6ec; }
.level-warning .level-value { color: #e6a23c; }
.level-danger { background: #fef0f0; }
.level-danger .level-value { color: #f56c6c; }

.chart-card, .dimension-card, .list-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dimension-bars {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dimension-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.dimension-label {
  width: 100px;
  text-align: right;
  font-size: 13px;
  color: #606266;
}

.dimension-bar-wrapper {
  flex: 1;
  height: 12px;
  background: #f0f2f5;
  border-radius: 6px;
  overflow: hidden;
}

.dimension-bar {
  height: 100%;
  border-radius: 6px;
  transition: width 0.3s;
}

.dimension-score {
  width: 40px;
  text-align: right;
  font-weight: bold;
  font-size: 13px;
}

.dimension-weight {
  width: 40px;
  text-align: right;
  color: #909399;
  font-size: 12px;
}

.product-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.product-title {
  font-weight: 500;
}

.product-tags {
  display: flex;
  gap: 4px;
}

.detail-content {
  padding: 10px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #eee;
}

.detail-title {
  font-size: 18px;
  font-weight: bold;
}

.detail-dimensions h4, .detail-alerts h4 {
  margin: 0 0 15px 0;
  font-size: 14px;
  color: #303133;
}

.detail-dim-item {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.detail-dim-label {
  width: 110px;
  text-align: right;
  font-size: 13px;
  color: #606266;
}

.detail-dim-bar-wrapper {
  flex: 1;
  height: 10px;
  background: #f0f2f5;
  border-radius: 5px;
  overflow: hidden;
}

.detail-dim-bar {
  height: 100%;
  border-radius: 5px;
  transition: width 0.3s;
}

.detail-dim-score {
  width: 35px;
  text-align: right;
  font-weight: bold;
  font-size: 13px;
}

.detail-dim-weight {
  width: 35px;
  text-align: right;
  color: #909399;
  font-size: 12px;
}

.detail-alerts {
  margin-top: 20px;
}
</style>
