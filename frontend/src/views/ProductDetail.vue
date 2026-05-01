<template>
  <div class="product-detail">
    <el-page-header @back="goBack" content="商品详情" />
    
    <el-card class="info-card" style="margin-top: 20px">
      <div class="product-header">
        <div class="product-info">
          <h2>{{ product.title }}</h2>
          <div class="product-meta">
            <el-tag :type="getTierType(product.tier)">{{ product.tier }}</el-tag>
            <span>{{ product.category }}</span>
            <span>{{ product.style }} / {{ product.scene }}</span>
            <span class="product-id">{{ product.product_id }}</span>
          </div>
        </div>
        <div class="product-actions">
          <el-button 
            :type="product.starred ? 'warning' : 'default'" 
            @click="toggleStar"
          >
            <el-icon><Star /></el-icon>
            {{ product.starred ? '已收藏' : '收藏' }}
          </el-button>
        </div>
      </div>
    </el-card>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="6" v-for="kpi in kpis" :key="kpi.key">
        <el-card class="kpi-card">
          <div class="kpi-label">{{ kpi.label }}</div>
          <div class="kpi-value">{{ kpi.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>历史数据</span>
          </template>
          <div ref="chartRef" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>操作记录</span>
          </template>
          <el-timeline>
            <el-timeline-item v-for="(action, i) in actions" :key="i">
              <div class="action-date">{{ action.action_date }}</div>
              <div class="action-detail">{{ action.action_detail }}</div>
            </el-timeline-item>
            <el-empty v-if="!actions.length" description="暂无记录" />
          </el-timeline>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>商品标签</span>
          </template>
          <div class="tags">
            <el-tag
              v-for="tag in tags"
              :key="tag.id"
              closable
              @close="removeTag(tag)"
            >
              {{ tag.tag }}
            </el-tag>
            <el-button type="primary" link @click="showAddTag = true">+ 添加标签</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="showAddTag" title="添加标签" width="400px">
      <el-input v-model="newTag" placeholder="请输入标签名称" />
      <template #footer>
        <el-button @click="showAddTag = false">取消</el-button>
        <el-button type="primary" @click="addTag">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import api from '@/api'

const router = useRouter()
const route = useRoute()
const chartRef = ref(null)
let chart = null

const product = ref({})
const weeklyData = ref([])
const actions = ref([])
const tags = ref([])
const showAddTag = ref(false)
const newTag = ref('')

const getTierType = (tier) => {
  const types = {
    '引流款': 'success',
    '利润款': 'primary',
    '潜力款': 'warning'
  }
  return types[tier] || 'info'
}

const kpis = ref([
  { label: 'GMV', key: 'gmv', value: '-' },
  { label: '访客数', key: 'visitors', value: '-' },
  { label: '转化率', key: 'conversion', value: '-' },
  { label: 'ROI', key: 'roi', value: '-' }
])

const formatNumber = (num) => {
  if (!num) return '0'
  if (num >= 10000) {
    return (num / 10000).toFixed(2) + '万'
  }
  return num.toLocaleString()
}

const loadData = async () => {
  try {
    const [productRes, weeklyRes, actionsRes, tagsRes] = await Promise.all([
      api.getProduct(route.params.id),
      api.getProductWeeklyData(route.params.id),
      api.getProductOperations(route.params.id),
      api.getProductTags(route.params.id)
    ])
    
    product.value = productRes.data || {}
    weeklyData.value = productRes.data?.trend || []
    actions.value = actionsRes.data?.actions || []
    tags.value = tagsRes.data?.tags || []
    
    if (weeklyData.value.length > 0) {
      const latest = weeklyData.value[0]
      kpis.value = [
        { label: 'GMV', value: `¥${formatNumber(latest.net_sales)}` },
        { label: '访客数', value: formatNumber(latest.visitors) },
        { label: '转化率', value: `${(latest.payment_conversion * 100).toFixed(2)}%` },
        { label: 'ROI', value: latest.total_roi?.toFixed(2) || '0' }
      ]
    }
    
    nextTick(() => {
      initChart()
    })
  } catch (error) {
    console.error('Load product detail error:', error)
    ElMessage.error('加载商品详情失败')
  }
}

const initChart = () => {
  if (!chartRef.value) return
  
  if (chart) {
    chart.dispose()
  }
  
  chart = echarts.init(chartRef.value)
  
  const dates = weeklyData.value.map(d => d.week_start)
  const gmv = weeklyData.value.map(d => d.net_sales)
  const roi = weeklyData.value.map(d => d.total_roi)
  
  const option = {
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['GMV', 'ROI']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: dates
    },
    yAxis: [
      {
        type: 'value',
        name: 'GMV'
      },
      {
        type: 'value',
        name: 'ROI',
        position: 'right'
      }
    ],
    series: [
      {
        name: 'GMV',
        type: 'line',
        data: gmv,
        smooth: true,
        yAxisIndex: 0
      },
      {
        name: 'ROI',
        type: 'line',
        data: roi,
        smooth: true,
        yAxisIndex: 1,
        itemStyle: { color: '#e6a23c' }
      }
    ]
  }
  
  chart.setOption(option)
  
  window.addEventListener('resize', () => chart.resize())
}

const toggleStar = async () => {
  try {
    await api.toggleProductStar(product.value.product_id)
    product.value.starred = !product.value.starred
    ElMessage.success(product.value.starred ? '已收藏' : '已取消收藏')
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const addTag = async () => {
  if (!newTag.value.trim()) {
    ElMessage.warning('请输入标签名称')
    return
  }
  
  try {
    const res = await api.addProductTag(product.value.product_id, newTag.value.trim())
    tags.value.push(res.data)
    newTag.value = ''
    showAddTag.value = false
    ElMessage.success('添加成功')
  } catch (error) {
    ElMessage.error('添加失败')
  }
}

const removeTag = async (tag) => {
  try {
    await api.removeProductTag(product.value.product_id, tag.tag)
    tags.value = tags.value.filter(t => t.id !== tag.id)
    ElMessage.success('删除成功')
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

const goBack = () => {
  router.back()
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.product-detail {
  width: 100%;
}

.product-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.product-info h2 {
  margin: 0 0 10px 0;
}

.product-meta {
  display: flex;
  gap: 15px;
  align-items: center;
}

.product-id {
  color: #909399;
  font-size: 13px;
}

.kpi-card {
  text-align: center;
}

.kpi-label {
  color: #909399;
  font-size: 14px;
  margin-bottom: 5px;
}

.kpi-value {
  font-size: 24px;
  font-weight: 600;
}

.chart-container {
  height: 350px;
  width: 100%;
}

.action-date {
  font-size: 14px;
  color: #909399;
}

.action-detail {
  font-size: 14px;
}

.tags {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
</style>
