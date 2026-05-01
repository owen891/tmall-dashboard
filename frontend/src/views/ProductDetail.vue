<template>
  <div class="product-detail">
    <el-page-header @back="goBack" content="商品详情" />
    
    <el-card class="info-card" style="margin-top: 20px">
      <div class="product-header">
        <div class="product-image-large" v-if="product.image_url">
          <img :src="product.image_url" :alt="product.title" @error="$event.target.style.display='none'" />
        </div>
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
          <div class="kpi-value-row">
            <span class="kpi-value">{{ kpi.value }}</span>
            <span v-if="kpi.trend" :class="['kpi-trend', kpi.trend > 0 ? 'trend-up' : 'trend-down']">
              <el-icon v-if="kpi.trend > 0"><CaretTop /></el-icon>
              <el-icon v-else><CaretBottom /></el-icon>
              {{ Math.abs(kpi.trend).toFixed(1) }}%
            </span>
          </div>
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
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span>操作记录</span>
              <el-button type="primary" size="small" @click="showAddAction = true">+ 添加</el-button>
            </div>
          </template>
          <el-timeline v-if="actions.length">
            <el-timeline-item v-for="(action, i) in actions" :key="i" :timestamp="action.action_date" placement="top">
              <el-card shadow="hover" class="action-card">
                <div class="action-header">
                  <el-tag :type="getActionTypeStyle(action.action_type)" size="small">
                    {{ action.action_type || '其他' }}
                  </el-tag>
                  <span class="action-detail-text">{{ action.action_detail }}</span>
                </div>
                <div class="action-effect" v-if="action.before_payment || action.after_payment">
                  <div class="effect-row">
                    <span class="effect-label">执行前:</span>
                    <span class="effect-value">GMV ¥{{ formatNumber(action.before_payment) }} | 
                      访客 {{ formatNumber(action.before_visitors) }} | 
                      转化率 {{ formatPercent(action.before_conversion) }}
                    </span>
                  </div>
                  <div class="effect-row" v-if="action.after_payment">
                    <span class="effect-label">执行后:</span>
                    <span class="effect-value">GMV ¥{{ formatNumber(action.after_payment) }} | 
                      访客 {{ formatNumber(action.after_visitors) }} | 
                      转化率 {{ formatPercent(action.after_conversion) }}
                    </span>
                  </div>
                </div>
              </el-card>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无记录" />
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

    <el-dialog v-model="showAddAction" title="添加运营动作" width="500px">
      <el-form :model="actionForm" label-width="100px">
        <el-form-item label="动作类型">
          <el-select v-model="actionForm.action_type" placeholder="请选择" style="width: 100%">
            <el-option label="标题优化" value="标题优化" />
            <el-option label="主图优化" value="主图优化" />
            <el-option label="价格调整" value="价格调整" />
            <el-option label="SKU调整" value="SKU调整" />
            <el-option label="详情优化" value="详情优化" />
            <el-option label="营销活动" value="营销活动" />
            <el-option label="付费推广" value="付费推广" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="动作描述">
          <el-input v-model="actionForm.action_detail" type="textarea" :rows="3" placeholder="请描述具体动作" />
        </el-form-item>
        <el-form-item label="执行日期">
          <el-date-picker v-model="actionForm.action_date" type="date" placeholder="选择日期" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddAction = false">取消</el-button>
        <el-button type="primary" @click="submitActionFromDetail">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { CaretTop, CaretBottom } from '@element-plus/icons-vue'
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
const showAddAction = ref(false)
const actionForm = ref({
  action_type: '',
  action_detail: '',
  action_date: ''
})

const getTierType = (tier) => {
  const types = {
    '引流款': 'success',
    '利润款': 'primary',
    '潜力款': 'warning'
  }
  return types[tier] || 'info'
}

const getActionTypeStyle = (type) => {
  const styles = {
    '标题优化': 'primary',
    '主图优化': 'success',
    '价格调整': 'warning',
    'SKU调整': 'info',
    '详情优化': '',
    '营销活动': 'danger',
    '付费推广': 'warning',
    '加付费': 'warning',
    '报名活动': 'danger'
  }
  return styles[type] || 'info'
}

const formatPercent = (value) => {
  if (!value) return '0%'
  return (value * 100).toFixed(2) + '%'
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
      const latest = weeklyData.value[weeklyData.value.length - 1]
      const prev = weeklyData.value.length > 1 ? weeklyData.value[weeklyData.value.length - 2] : null
      
      const calcTrend = (curr, prevVal) => {
        if (!prevVal || prevVal === 0) return null
        return ((curr - prevVal) / prevVal) * 100
      }
      
      kpis.value = [
        { 
          label: 'GMV', 
          value: `¥${formatNumber(latest.net_sales)}`,
          trend: prev ? calcTrend(latest.net_sales, prev.net_sales) : null
        },
        { 
          label: '访客数', 
          value: formatNumber(latest.visitors),
          trend: prev ? calcTrend(latest.visitors, prev.visitors) : null
        },
        { 
          label: '转化率', 
          value: `${((latest.conversion || latest.payment_conversion || 0) * 100).toFixed(2)}%`,
          trend: prev ? calcTrend((latest.conversion || latest.payment_conversion), (prev.conversion || prev.payment_conversion)) : null
        },
        { 
          label: 'ROI', 
          value: (latest.roi || latest.ad_roi || 0).toFixed(2),
          trend: prev ? calcTrend((latest.roi || latest.ad_roi), (prev.roi || prev.ad_roi)) : null
        }
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
  
  const dates = weeklyData.value.map(d => d.period)
  const gmv = weeklyData.value.map(d => d.net_sales)
  const roi = weeklyData.value.map(d => d.roi || d.ad_roi || 0)
  
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

const submitActionFromDetail = async () => {
  if (!actionForm.value.action_type || !actionForm.value.action_detail) {
    ElMessage.warning('请填写完整信息')
    return
  }
  try {
    await api.createAction({
      product_id: product.value.product_id,
      ...actionForm.value
    })
    ElMessage.success('添加成功')
    showAddAction.value = false
    actionForm.value = { action_type: '', action_detail: '', action_date: '' }
    const res = await api.getProductOperations(product.value.product_id)
    actions.value = res.data?.actions || []
  } catch (error) {
    ElMessage.error('添加失败')
  }
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
  gap: 20px;
}

.product-image-large {
  flex-shrink: 0;
  width: 120px;
  height: 120px;
  border-radius: 8px;
  overflow: hidden;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
}

.product-image-large img {
  width: 100%;
  height: 100%;
  object-fit: cover;
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

.kpi-value-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.kpi-value {
  font-size: 24px;
  font-weight: 600;
}

.kpi-trend {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 4px;
}

.trend-up {
  color: #67c23a;
  background: #f0f9eb;
}

.trend-down {
  color: #f56c6c;
  background: #fef0f0;
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

.action-card {
  margin-bottom: 0;
}

.action-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.action-detail-text {
  font-size: 14px;
  color: #303133;
}

.action-effect {
  background: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  margin-top: 8px;
}

.effect-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 12px;
}

.effect-row:last-child {
  margin-bottom: 0;
}

.effect-label {
  color: #909399;
  flex-shrink: 0;
}

.effect-value {
  color: #606266;
}
</style>
