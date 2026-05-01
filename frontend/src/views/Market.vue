<template>
  <div class="market-container">
    <div class="header">
      <h2>市场分析</h2>
    </div>

    <el-row :gutter="20" class="summary-cards">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ overview.total_products }}</div>
          <div class="stat-label">商品数量</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ formatNumber(overview.total_gmv) }}</div>
          <div class="stat-label">总GMV</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ overview.avg_price }}</div>
          <div class="stat-label">平均价格</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ overview.avg_roi }}</div>
          <div class="stat-label">平均ROI</div>
        </el-card>
      </el-col>
    </el-row>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="关键词分析" name="keywords">
        <el-card>
          <el-table :data="keywords" stripe>
            <el-table-column prop="keyword" label="关键词" />
            <el-table-column prop="category" label="类目" />
            <el-table-column prop="search_volume" label="搜索量" />
            <el-table-column prop="competition" label="竞争度">
              <template #default="{ row }">
                <el-progress :percentage="row.competition * 100" :color="getCompetitionColor(row.competition)" />
              </template>
            </el-table-column>
            <el-table-column prop="opportunity_score" label="机会分">
              <template #default="{ row }">
                <el-tag :type="row.opportunity_score > 70 ? 'success' : row.opportunity_score > 40 ? 'warning' : 'info'">
                  {{ row.opportunity_score }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="trend_30d" label="30天趋势">
              <template #default="{ row }">
                <span :class="row.trend_30d > 0 ? 'trend-up' : 'trend-down'">
                  {{ row.trend_30d > 0 ? '↑' : '↓' }} {{ Math.abs(row.trend_30d).toFixed(1) }}%
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="市场机会" name="opportunities">
        <el-card>
          <el-table :data="opportunities" stripe>
            <el-table-column prop="keyword" label="关键词" />
            <el-table-column prop="category" label="类目" />
            <el-table-column prop="search_volume" label="搜索量" />
            <el-table-column prop="competition" label="竞争度" />
            <el-table-column prop="potential" label="潜力">
              <template #default="{ row }">
                <el-tag :type="row.potential === '高' ? 'success' : row.potential === '中' ? 'warning' : 'info'">
                  {{ row.potential }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="recommendation" label="建议" />
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="类目分析" name="categories">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-card>
              <template #header>
                <span>类目分布</span>
              </template>
              <div ref="categoryChartRef" style="width: 100%; height: 300px;"></div>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card>
              <template #header>
                <span>类目详情</span>
              </template>
              <el-table :data="categories" stripe>
                <el-table-column prop="category" label="类目" />
                <el-table-column prop="product_count" label="商品数" />
                <el-table-column prop="total_gmv" label="GMV">
                  <template #default="{ row }">
                    {{ formatNumber(row.total_gmv) }}
                  </template>
                </el-table-column>
                <el-table-column prop="market_share" label="份额(%)" />
              </el-table>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="竞品分析" name="competitors">
        <el-card>
          <el-table :data="competitors" stripe>
            <el-table-column prop="rank" label="排名" width="60" />
            <el-table-column prop="product_name" label="商品" />
            <el-table-column prop="gmv" label="GMV">
              <template #default="{ row }">
                {{ formatNumber(row.gmv) }}
              </template>
            </el-table-column>
            <el-table-column prop="market_share" label="市场份额(%)" />
            <el-table-column prop="price_range" label="价格区间" />
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'

const activeTab = ref('keywords')
const categoryChartRef = ref(null)
let categoryChart = null

const overview = ref({
  total_products: 0,
  total_gmv: 0,
  avg_price: 0,
  avg_roi: 0
})
const keywords = ref([])
const opportunities = ref([])
const categories = ref([])
const competitors = ref([])

const loadOverview = async () => {
  try {
    const res = await axios.get('/api/market/overview')
    if (res.data.code === 200) {
      overview.value = res.data.data
    }
  } catch (error) {
    console.error('加载市场概览失败:', error)
  }
}

const loadKeywords = async () => {
  try {
    const res = await axios.get('/api/market/keywords?page_size=50')
    if (res.data.code === 200) {
      keywords.value = res.data.data.keywords || []
    }
  } catch (error) {
    console.error('加载关键词失败:', error)
  }
}

const loadOpportunities = async () => {
  try {
    const res = await axios.get('/api/market/opportunities?limit=20')
    if (res.data.code === 200) {
      opportunities.value = res.data.data || []
    }
  } catch (error) {
    console.error('加载市场机会失败:', error)
  }
}

const loadCategories = async () => {
  try {
    const res = await axios.get('/api/market/categories')
    if (res.data.code === 200) {
      categories.value = res.data.data || []
      updateCategoryChart()
    }
  } catch (error) {
    console.error('加载类目分析失败:', error)
  }
}

const loadCompetitors = async () => {
  try {
    const res = await axios.get('/api/market/competitors?limit=20')
    if (res.data.code === 200) {
      competitors.value = res.data.data || []
    }
  } catch (error) {
    console.error('加载竞品分析失败:', error)
  }
}

const updateCategoryChart = () => {
  if (!categoryChart || !categories.value.length) return

  categoryChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: '5%', left: 'center' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      data: categories.value.slice(0, 8).map(c => ({
        name: c.category,
        value: c.total_gmv
      }))
    }]
  })
}

const getCompetitionColor = (value) => {
  if (value < 0.3) return '#67c23a'
  if (value < 0.6) return '#e6a23c'
  return '#f56c6c'
}

const formatNumber = (num) => {
  if (!num) return '0'
  if (num >= 10000) return (num / 10000).toFixed(2) + '万'
  return num.toFixed(2)
}

onMounted(() => {
  categoryChart = echarts.init(categoryChartRef.value)
  loadOverview()
  loadKeywords()
  loadOpportunities()
  loadCategories()
  loadCompetitors()
  window.addEventListener('resize', () => categoryChart?.resize())
})

onUnmounted(() => {
  categoryChart?.dispose()
})
</script>

<style scoped>
.market-container {
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
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.stat-label {
  color: #909399;
  margin-top: 5px;
}

.trend-up {
  color: #67c23a;
}

.trend-down {
  color: #f56c6c;
}

.el-card {
  margin-bottom: 20px;
}
</style>
