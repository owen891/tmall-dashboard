<template>
  <div class="lifecycle-page">
    <el-card class="filter-card">
      <div class="filter-row">
        <el-input 
          v-model="searchText" 
          placeholder="搜索商品名称" 
          clearable 
          style="width: 200px"
          @input="debounceSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select v-model="tierFilter" placeholder="分层筛选" clearable style="width: 120px" @change="loadLifecycleData">
          <el-option label="全部" value="" />
          <el-option label="引流款" value="引流款" />
          <el-option label="利润款" value="利润款" />
          <el-option label="形象款" value="形象款" />
          <el-option label="爆款" value="爆款" />
        </el-select>
        <el-button type="primary" @click="loadLifecycleData" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </el-card>

    <div v-if="!showDetail" class="lifecycle-grid" v-loading="loading">
      <div 
        v-for="product in products" 
        :key="product.product_id" 
        class="lifecycle-card"
        @click="showProductDetail(product)"
      >
        <div class="card-header">
          <el-image 
            :src="product.image_url || defaultImage" 
            fit="cover"
            class="card-image"
          >
            <template #error>
              <div class="image-placeholder">
                <el-icon><Picture /></el-icon>
              </div>
            </template>
          </el-image>
          <div class="card-info">
            <div class="card-title">{{ product.title }}</div>
            <div class="card-meta">
              <el-tag v-if="product.tier" :type="getTierType(product.tier)" size="small">{{ product.tier }}</el-tag>
              <span v-if="product.style" class="meta-text">{{ product.style }}</span>
            </div>
          </div>
        </div>
        <div class="card-stats">
          <div class="stat-item">
            <div class="stat-value">{{ formatMoney(product.gsv_total || product.payment_amount) }}</div>
            <div class="stat-label">累计GSV</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">{{ product.active_months || '-' }}</div>
            <div class="stat-label">活跃月数</div>
          </div>
          <div class="stat-item">
            <div class="stat-value trend" :class="getTrendClass(product.trend)">
              <el-icon v-if="product.trend > 0"><ArrowUp /></el-icon>
              <el-icon v-else-if="product.trend < 0"><ArrowDown /></el-icon>
              <span v-else>-</span>
              {{ product.trend ? Math.abs(product.trend).toFixed(1) + '%' : '' }}
            </div>
            <div class="stat-label">趋势</div>
          </div>
        </div>
      </div>
      <el-empty v-if="!loading && products.length === 0" description="暂无生命周期数据" />
    </div>

    <div v-else class="lifecycle-detail">
      <el-card>
        <template #header>
          <div class="detail-header">
            <el-button @click="closeDetail" text>
              <el-icon><ArrowLeft /></el-icon>
              返回列表
            </el-button>
            <div class="product-info" v-if="selectedProduct">
              <el-image :src="selectedProduct.image_url || defaultImage" class="detail-image" />
              <div>
                <div class="detail-title">{{ selectedProduct.title }}</div>
                <div class="detail-meta">
                  <el-tag v-if="selectedProduct.tier" :type="getTierType(selectedProduct.tier)" size="small">{{ selectedProduct.tier }}</el-tag>
                  <span>{{ selectedProduct.style }} · {{ lifecycleData.length }}个月数据</span>
                </div>
              </div>
            </div>
          </div>
        </template>
        <div ref="chartRef" class="chart-container"></div>
        <div class="metrics-row">
          <div class="metric-card">
            <div class="metric-value">{{ formatMoney(totalGsv) }}</div>
            <div class="metric-label">累计GSV</div>
          </div>
          <div class="metric-card">
            <div class="metric-value">{{ avgGsv.toFixed(0) }}</div>
            <div class="metric-label">月均GSV</div>
          </div>
          <div class="metric-card">
            <div class="metric-value">{{ lifecycleData.length }}</div>
            <div class="metric-label">活跃月数</div>
          </div>
          <div class="metric-card">
            <div class="metric-value" :class="overallTrend >= 0 ? 'up' : 'down'">
              {{ overallTrend >= 0 ? '+' : '' }}{{ overallTrend.toFixed(1) }}%
            </div>
            <div class="metric-label">整体趋势</div>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed, nextTick } from 'vue'
import { Search, Refresh, Picture, ArrowUp, ArrowDown, ArrowLeft } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import api from '@/api'
import { getTierType } from '@/utils/format'

const searchText = ref('')
const tierFilter = ref('')
const loading = ref(false)
const products = ref([])
const showDetail = ref(false)
const selectedProduct = ref(null)
const lifecycleData = ref([])
const chartRef = ref(null)
let chart = null
let searchTimer = null
let handleResize = null

const defaultImage = 'https://via.placeholder.com/60x60/f0f2f5/909399?text=商'

const totalGsv = computed(() => {
  return lifecycleData.value.reduce((sum, d) => sum + (d.gsv || 0), 0)
})

const avgGsv = computed(() => {
  if (lifecycleData.value.length === 0) return 0
  return totalGsv.value / lifecycleData.value.length
})

const overallTrend = computed(() => {
  if (lifecycleData.value.length < 2) return 0
  const last = lifecycleData.value[lifecycleData.value.length - 1]?.gsv || 0
  const first = lifecycleData.value[0]?.gsv || 0
  if (first === 0) return 0
  return ((last - first) / first) * 100
})

const debounceSearch = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    loadLifecycleData()
  }, 300)
}

const loadLifecycleData = async () => {
  loading.value = true
  try {
    const params = { limit: 50 }
    if (tierFilter.value) params.tier = tierFilter.value
    if (searchText.value) params.search = searchText.value
    
    const res = await api.getProducts(params)
    const data = res.data?.data || []
    
    products.value = data.map(p => ({
      ...p,
      gsv_total: p.payment_amount,
      active_months: 1,
      trend: 0
    }))
    
    const ids = data.map(p => p.product_id).slice(0, 20).join(',')
    if (ids) {
      try {
        const lcRes = await api.getBatchLifecycle(ids)
        const lcData = lcRes.data || {}
        products.value = products.value.map(p => {
          const lc = lcData[p.product_id]
          if (lc && lc.gsv_data && lc.gsv_data.length > 0) {
            const gsvData = lc.gsv_data.filter(d => d.gsv > 0)
            const total = gsvData.reduce((sum, d) => sum + d.gsv, 0)
            const months = gsvData.length
            let trend = 0
            if (gsvData.length >= 2) {
              const last = gsvData[gsvData.length - 1].gsv
              const prev = gsvData[gsvData.length - 2].gsv
              if (prev > 0) trend = ((last - prev) / prev) * 100
            }
            return {
              ...p,
              gsv_total: total || p.payment_amount,
              active_months: months,
              trend
            }
          }
          return p
        })
      } catch (e) {
        console.log('Batch lifecycle error:', e)
      }
    }
  } catch (error) {
    console.error('Load lifecycle error:', error)
  } finally {
    loading.value = false
  }
}

const showProductDetail = async (product) => {
  selectedProduct.value = product
  showDetail.value = true
  
  try {
    const res = await api.getProductLifecycle(product.product_id)
    const data = res.data?.data || {}
    lifecycleData.value = (data.gsv_data || []).filter(d => d.gsv > 0)
    
    nextTick(() => {
      initChart()
    })
  } catch (error) {
    console.error('Load lifecycle detail error:', error)
    lifecycleData.value = []
  }
}

const closeDetail = () => {
  showDetail.value = false
  selectedProduct.value = null
  lifecycleData.value = []
  if (chart) {
    chart.dispose()
    chart = null
  }
}

const initChart = () => {
  if (!chartRef.value || lifecycleData.value.length === 0) return
  
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)
  
  const months = lifecycleData.value.map(d => d.month)
  const gsvValues = lifecycleData.value.map(d => d.gsv)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const p = params[0]
        return `${p.axisValue}<br/>GSV: ¥${p.value?.toLocaleString() || 0}`
      }
    },
    grid: { left: 60, right: 40, top: 20, bottom: 30 },
    xAxis: {
      type: 'category',
      data: months,
      axisLabel: { rotate: 45, fontSize: 11 }
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (v) => v >= 10000 ? (v / 10000).toFixed(1) + 'w' : v
      }
    },
    series: [{
      name: 'GSV',
      type: 'line',
      data: gsvValues,
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { width: 3, color: '#409EFF' },
      itemStyle: { color: '#409EFF' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
          { offset: 1, color: 'rgba(64, 158, 255, 0.05)' }
        ])
      }
    }]
  }
  
  chart.setOption(option)
  handleResize = () => chart?.resize()
  window.addEventListener('resize', handleResize)
}

const formatMoney = (val) => {
  if (!val) return '¥0'
  if (val >= 10000) return '¥' + (val / 10000).toFixed(1) + 'w'
  return '¥' + val.toLocaleString()
}

const getTrendClass = (trend) => {
  if (trend > 5) return 'up'
  if (trend < -5) return 'down'
  return ''
}

onMounted(() => {
  loadLifecycleData()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})
</script>

<style scoped>
.lifecycle-page {
  padding: 0;
}

.filter-card {
  margin-bottom: 16px;
}

.filter-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.lifecycle-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.lifecycle-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.3s;
  border: 1px solid #ebeef5;
}

.lifecycle-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.card-image {
  width: 60px;
  height: 60px;
  border-radius: 8px;
  flex-shrink: 0;
}

.image-placeholder {
  width: 60px;
  height: 60px;
  background: #f5f7fa;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
}

.card-info {
  flex: 1;
  min-width: 0;
}

.card-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
}

.meta-text {
  font-size: 12px;
  color: #909399;
}

.card-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
}

.stat-item {
  text-align: center;
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.stat-value.trend.up {
  color: #67c23a;
}

.stat-value.trend.down {
  color: #f56c6c;
}

.stat-label {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 16px;
}

.product-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.detail-image {
  width: 48px;
  height: 48px;
  border-radius: 8px;
}

.detail-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.detail-meta {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

.chart-container {
  height: 300px;
  margin: 20px 0;
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.metric-card {
  text-align: center;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.metric-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.metric-value.up {
  color: #67c23a;
}

.metric-value.down {
  color: #f56c6c;
}

.metric-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}
</style>
