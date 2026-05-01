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
      <el-col :span="4" v-for="kpi in kpis" :key="kpi.key">
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

    <el-card style="margin-top: 20px">
      <template #header>
        <span>数据详情</span>
      </template>
      <el-tabs v-model="activeDetailTab" type="card">
        <el-tab-pane label="流量来源" name="traffic">
          <div class="tab-content">
            <el-row :gutter="20">
              <el-col :span="12">
                <div class="traffic-sources">
                  <div class="source-item">
                    <span class="source-label">搜索访客</span>
                    <div class="source-bar-wrap">
                      <div class="source-bar" :style="{ width: getTrafficPercent('search') + '%' }"></div>
                    </div>
                    <span class="source-value">{{ formatNumber(latestData.search_ipv) }} ({{ getTrafficPercent('search') }}%)</span>
                  </div>
                  <div class="source-item">
                    <span class="source-label">推荐访客</span>
                    <div class="source-bar-wrap">
                      <div class="source-bar bar-recommend" :style="{ width: getTrafficPercent('recommend') + '%' }"></div>
                    </div>
                    <span class="source-value">{{ formatNumber(latestData.recommend_ipv) }} ({{ getTrafficPercent('recommend') }}%)</span>
                  </div>
                  <div class="source-item">
                    <span class="source-label">付费访客</span>
                    <div class="source-bar-wrap">
                      <div class="source-bar bar-paid" :style="{ width: getTrafficPercent('paid') + '%' }"></div>
                    </div>
                    <span class="source-value">{{ formatNumber(latestData.paid_ipv) }} ({{ getTrafficPercent('paid') }}%)</span>
                  </div>
                  <div class="source-item">
                    <span class="source-label">自然访客</span>
                    <div class="source-bar-wrap">
                      <div class="source-bar bar-organic" :style="{ width: getTrafficPercent('organic') + '%' }"></div>
                    </div>
                    <span class="source-value">{{ formatNumber(latestData.organic_ipv) }} ({{ getTrafficPercent('organic') }}%)</span>
                  </div>
                </div>
              </el-col>
              <el-col :span="12">
                <div class="funnel-container">
                  <div class="funnel-item">
                    <div class="funnel-bar funnel-visitors">
                      <span>访客 {{ formatNumber(latestData.visitors) }}</span>
                    </div>
                  </div>
                  <div class="funnel-item">
                    <div class="funnel-bar funnel-cart">
                      <span>加购 {{ formatNumber(latestData.cart_users || 0) }}</span>
                    </div>
                  </div>
                  <div class="funnel-item">
                    <div class="funnel-bar funnel-buyers">
                      <span>支付 {{ formatNumber(latestData.buyers || 0) }}</span>
                    </div>
                  </div>
                </div>
                <div class="funnel-rates">
                  <span>加购率: {{ formatPercent(latestData.cart_rate) }}</span>
                  <span>转化率: {{ formatPercent(latestData.conversion) }}</span>
                </div>
              </el-col>
            </el-row>
          </div>
        </el-tab-pane>

        <el-tab-pane label="搜索分析" name="search-analysis">
          <div class="tab-content">
            <el-row :gutter="20" class="mb-4">
              <el-col :span="8">
                <el-card>
                  <template #header>搜索占比</template>
                  <div class="metric-value">{{ getSearchRatio() }}%</div>
                  <div class="metric-label">搜索流量占比</div>
                </el-card>
              </el-col>
              <el-col :span="8">
                <el-card>
                  <template #header>搜索点击率</template>
                  <div class="metric-value">{{ formatPercent(latestData.search_click_rate) }}</div>
                  <div class="metric-label">搜索CTR</div>
                </el-card>
              </el-col>
              <el-col :span="8">
                <el-card>
                  <template #header>搜索转化</template>
                  <div class="metric-value">{{ formatPercent(latestData.search_conversion) }}</div>
                  <div class="metric-label">搜索转化率</div>
                </el-card>
              </el-col>
            </el-row>
            <el-card>
              <template #header>搜索关键词分析</template>
              <div v-if="searchKeywords.length">
                <el-table :data="searchKeywords" border>
                  <el-table-column prop="keyword" label="关键词" />
                  <el-table-column prop="pv" label="曝光量" />
                  <el-table-column prop="click" label="点击量" />
                  <el-table-column prop="ctr" label="点击率">
                    <template #default="{ row }">{{ formatPercent(row.ctr) }}</template>
                  </el-table-column>
                  <el-table-column prop="conversion" label="转化率">
                    <template #default="{ row }">{{ formatPercent(row.conversion) }}</template>
                  </el-table-column>
                  <el-table-column prop="sales" label="销售额">
                    <template #default="{ row }">¥{{ formatNumber(row.sales) }}</template>
                  </el-table-column>
                </el-table>
              </div>
              <div v-else class="empty-hint">暂无搜索关键词数据</div>
            </el-card>
          </div>
        </el-tab-pane>

        <el-tab-pane label="标题优化" name="title-optimization">
          <div class="tab-content">
            <el-card class="mb-4">
              <template #header>当前标题</template>
              <div class="current-title">{{ product.title }}</div>
              <div class="title-analysis">
                <div class="analysis-item">
                  <span class="analysis-label">标题长度:</span>
                  <span class="analysis-value">{{ product.title?.length || 0 }} 字</span>
                </div>
                <div class="analysis-item">
                  <span class="analysis-label">核心词:</span>
                  <span class="analysis-value">{{ coreKeywords.join('、') || '未识别' }}</span>
                </div>
              </div>
            </el-card>
            <el-card class="mb-4">
              <template #header>标题诊断</template>
              <div class="diagnosis-list">
                <div v-for="(item, index) in titleDiagnosis" :key="index" class="diagnosis-item">
                  <el-icon :class="['diagnosis-icon', item.type]">
                    <CircleCheck v-if="item.type === 'success'" />
                    <Warning v-else-if="item.type === 'warning'" />
                    <CircleClose v-else />
                  </el-icon>
                  <span class="diagnosis-text">{{ item.text }}</span>
                </div>
              </div>
            </el-card>
            <el-card>
              <template #header>优化建议</template>
              <div class="suggestion-list">
                <div v-for="(suggestion, index) in titleSuggestions" :key="index" class="suggestion-item">
                  <span class="suggestion-number">{{ index + 1 }}</span>
                  <span class="suggestion-text">{{ suggestion }}</span>
                </div>
              </div>
            </el-card>
          </div>
        </el-tab-pane>

        <el-tab-pane label="推广分析" name="ads">
          <div class="tab-content">
            <el-row :gutter="20">
              <el-col :span="6">
                <div class="ad-stat">
                  <div class="ad-stat-label">广告花费</div>
                  <div class="ad-stat-value">¥{{ formatNumber(latestData.ad_spend || 0) }}</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="ad-stat">
                  <div class="ad-stat-label">广告ROI</div>
                  <div class="ad-stat-value" :style="{ color: (latestData.roi || 0) >= 3 ? '#67c23a' : '#f56c6c' }">
                    {{ (latestData.roi || 0).toFixed(2) }}
                  </div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="ad-stat">
                  <div class="ad-stat-label">广告占比</div>
                  <div class="ad-stat-value">{{ getAdRatio() }}%</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="ad-stat">
                  <div class="ad-stat-label">UV价值</div>
                  <div class="ad-stat-value">¥{{ formatNumber(latestData.uv_value || 0) }}</div>
                </div>
              </el-col>
            </el-row>
            <el-divider />
            <el-row :gutter="20">
              <el-col :span="8">
                <div class="ad-detail">
                  <div class="ad-detail-label">搜索访客</div>
                  <div class="ad-detail-value">{{ formatNumber(latestData.search_ipv || 0) }}</div>
                  <div class="ad-detail-bar">
                    <div class="bar-fill bar-search" :style="{ width: getTrafficPercent('search') + '%' }"></div>
                  </div>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="ad-detail">
                  <div class="ad-detail-label">推荐访客</div>
                  <div class="ad-detail-value">{{ formatNumber(latestData.recommend_ipv || 0) }}</div>
                  <div class="ad-detail-bar">
                    <div class="bar-fill bar-recommend" :style="{ width: getTrafficPercent('recommend') + '%' }"></div>
                  </div>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="ad-detail">
                  <div class="ad-detail-label">付费访客</div>
                  <div class="ad-detail-value">{{ formatNumber(latestData.paid_ipv || 0) }}</div>
                  <div class="ad-detail-bar">
                    <div class="bar-fill bar-paid" :style="{ width: getTrafficPercent('paid') + '%' }"></div>
                  </div>
                </div>
              </el-col>
            </el-row>
          </div>
        </el-tab-pane>

        <el-tab-pane label="SKU分析" name="sku">
          <div class="tab-content">
            <el-card>
              <template #header>SKU销售分布</template>
              <div v-if="skuData.length">
                <el-table :data="skuData" border>
                  <el-table-column prop="sku_name" label="SKU名称" />
                  <el-table-column prop="sales_qty" label="销售数量" />
                  <el-table-column prop="sales_amount" label="销售额">
                    <template #default="{ row }">¥{{ formatNumber(row.sales_amount) }}</template>
                  </el-table-column>
                  <el-table-column prop="ratio" label="占比">
                    <template #default="{ row }">{{ row.ratio }}%</template>
                  </el-table-column>
                  <el-table-column prop="stock" label="库存" />
                </el-table>
              </div>
              <div v-else class="empty-hint">暂无SKU数据</div>
            </el-card>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>付费推广数据</span>
          </template>
          <el-row :gutter="20">
            <el-col :span="6">
              <div class="ad-stat">
                <div class="ad-stat-label">广告花费</div>
                <div class="ad-stat-value">¥{{ formatNumber(latestData.ad_spend || 0) }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="ad-stat">
                <div class="ad-stat-label">广告ROI</div>
                <div class="ad-stat-value" :style="{ color: (latestData.roi || 0) >= 3 ? '#67c23a' : '#f56c6c' }">
                  {{ (latestData.roi || 0).toFixed(2) }}
                </div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="ad-stat">
                <div class="ad-stat-label">广告占比</div>
                <div class="ad-stat-value">{{ getAdRatio() }}%</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="ad-stat">
                <div class="ad-stat-label">UV价值</div>
                <div class="ad-stat-value">¥{{ formatNumber(latestData.uv_value || 0) }}</div>
              </div>
            </el-col>
          </el-row>
          <el-divider />
          <el-row :gutter="20">
            <el-col :span="8">
              <div class="ad-detail">
                <div class="ad-detail-label">搜索访客</div>
                <div class="ad-detail-value">{{ formatNumber(latestData.search_ipv || 0) }}</div>
                <div class="ad-detail-bar">
                  <div class="bar-fill bar-search" :style="{ width: getTrafficPercent('search') + '%' }"></div>
                </div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="ad-detail">
                <div class="ad-detail-label">推荐访客</div>
                <div class="ad-detail-value">{{ formatNumber(latestData.recommend_ipv || 0) }}</div>
                <div class="ad-detail-bar">
                  <div class="bar-fill bar-recommend" :style="{ width: getTrafficPercent('recommend') + '%' }"></div>
                </div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="ad-detail">
                <div class="ad-detail-label">付费访客</div>
                <div class="ad-detail-value">{{ formatNumber(latestData.paid_ipv || 0) }}</div>
                <div class="ad-detail-bar">
                  <div class="bar-fill bar-paid" :style="{ width: getTrafficPercent('paid') + '%' }"></div>
                </div>
              </div>
            </el-col>
          </el-row>
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
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { CaretTop, CaretBottom, CircleCheck, Warning, CircleClose } from '@element-plus/icons-vue'
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
const latestData = ref({})
const activeDetailTab = ref('traffic')

const searchKeywords = ref([
  { keyword: '连衣裙', pv: 12580, click: 892, ctr: 0.071, conversion: 0.082, sales: 58400 },
  { keyword: '夏季连衣裙', pv: 8920, click: 654, ctr: 0.073, conversion: 0.091, sales: 45200 },
  { keyword: '碎花连衣裙', pv: 6540, click: 486, ctr: 0.074, conversion: 0.078, sales: 32100 },
  { keyword: '雪纺连衣裙', pv: 5230, click: 398, ctr: 0.076, conversion: 0.085, sales: 28900 },
  { keyword: '显瘦连衣裙', pv: 4180, click: 312, ctr: 0.075, conversion: 0.095, sales: 24500 },
])

const skuData = ref([
  { sku_name: '黑色-M', sales_qty: 156, sales_amount: 4680, ratio: 35.2, stock: 234 },
  { sku_name: '白色-M', sales_qty: 108, sales_amount: 3240, ratio: 24.3, stock: 189 },
  { sku_name: '黑色-L', sales_qty: 89, sales_amount: 2670, ratio: 20.1, stock: 156 },
  { sku_name: '白色-L', sales_qty: 56, sales_amount: 1680, ratio: 12.6, stock: 98 },
  { sku_name: '黑色-S', sales_qty: 35, sales_amount: 1050, ratio: 7.8, stock: 67 },
])

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

const getTrafficPercent = (type) => {
  const total = (latestData.value.visitors || 0)
  if (total === 0) return 0
  const map = {
    'search': latestData.value.search_ipv || 0,
    'recommend': latestData.value.recommend_ipv || 0,
    'paid': latestData.value.paid_ipv || 0,
    'organic': latestData.value.organic_ipv || 0
  }
  return Math.round((map[type] || 0) / total * 100)
}

const getAdRatio = () => {
  const payment = latestData.value.payment_amount || 0
  const adSpend = latestData.value.ad_spend || 0
  if (payment === 0) return '0'
  return ((adSpend / payment) * 100).toFixed(1)
}

const getSearchRatio = () => {
  const visitors = latestData.value.visitors || 0
  const searchIpv = latestData.value.search_ipv || 0
  if (visitors === 0) return '0'
  return ((searchIpv / visitors) * 100).toFixed(1)
}

const coreKeywords = computed(() => {
  const title = product.value.title || ''
  const keywords = []
  
  const categoryKeywords = {
    '连衣裙': ['连衣裙', '裙', '长裙', '短裙', '半身裙'],
    '上衣': ['上衣', 'T恤', '衬衫', '卫衣', '毛衣'],
    '裤子': ['裤子', '牛仔裤', '休闲裤', '短裤'],
    '鞋': ['鞋', '运动鞋', '皮鞋', '凉鞋', '靴子'],
  }
  
  for (const [category, keys] of Object.entries(categoryKeywords)) {
    for (const key of keys) {
      if (title.includes(key) && !keywords.includes(key)) {
        keywords.push(key)
      }
    }
  }
  
  const styleKeywords = ['韩版', '日系', '欧美', '复古', '简约', '时尚', '百搭']
  for (const key of styleKeywords) {
    if (title.includes(key) && !keywords.includes(key)) {
      keywords.push(key)
    }
  }
  
  const featureKeywords = ['显瘦', '修身', '宽松', '透气', '舒适', '纯棉']
  for (const key of featureKeywords) {
    if (title.includes(key) && !keywords.includes(key)) {
      keywords.push(key)
    }
  }
  
  return keywords.slice(0, 5)
})

const titleDiagnosis = computed(() => {
  const title = product.value.title || ''
  const diagnosis = []
  
  if (!title) {
    diagnosis.push({ type: 'error', text: '标题为空，请填写商品标题' })
    return diagnosis
  }
  
  if (title.length < 10) {
    diagnosis.push({ type: 'error', text: '标题过短，建议至少包含10个字符' })
  } else if (title.length >= 10 && title.length <= 30) {
    diagnosis.push({ type: 'success', text: '标题长度适中' })
  } else if (title.length > 60) {
    diagnosis.push({ type: 'warning', text: '标题过长，建议控制在60字以内' })
  } else {
    diagnosis.push({ type: 'success', text: '标题长度合理' })
  }
  
  const hasCoreKeyword = coreKeywords.value.length > 0
  if (hasCoreKeyword) {
    diagnosis.push({ type: 'success', text: `已识别到核心关键词: ${coreKeywords.value.join('、')}` })
  } else {
    diagnosis.push({ type: 'warning', text: '未识别到明确的核心关键词，建议添加品类词' })
  }
  
  if (title.includes('包邮') || title.includes('包邮') || title.includes('免邮')) {
    diagnosis.push({ type: 'success', text: '标题包含促销信息，有助于提升点击率' })
  }
  
  if (title.includes('【') || title.includes('】') || title.includes('|') || title.includes('-')) {
    diagnosis.push({ type: 'success', text: '标题使用了分隔符，结构清晰' })
  }
  
  if (title.length >= 40) {
    diagnosis.push({ type: 'warning', text: '标题较长，建议重点关键词前置' })
  }
  
  return diagnosis
})

const titleSuggestions = computed(() => {
  const title = product.value.title || ''
  const suggestions = []
  
  if (title.length < 20) {
    suggestions.push('建议增加标题长度至20-30字，包含更多搜索关键词')
  }
  
  if (coreKeywords.value.length === 0) {
    suggestions.push('建议在标题中添加品类词（如连衣裙、T恤等）')
  }
  
  if (!title.includes('包邮') && !title.includes('优惠')) {
    suggestions.push('可以考虑添加促销信息（如包邮、限时优惠等）')
  }
  
  suggestions.push('关键词建议前置，将最重要的卖点放在标题前半部分')
  
  suggestions.push('使用分隔符（如【】、|、-）区分不同卖点，提升可读性')
  
  suggestions.push('包含场景词（如夏季、通勤、显瘦等），覆盖更多搜索场景')
  
  return suggestions
})

const kpis = ref([
  { label: 'GMV', key: 'gmv', value: '-' },
  { label: '访客数', key: 'visitors', value: '-' },
  { label: '转化率', key: 'conversion', value: '-' },
  { label: 'ROI', key: 'roi', value: '-' },
  { label: '客单价', key: 'aov', value: '-' },
  { label: '退款率', key: 'refund_rate', value: '-' }
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
      latestData.value = latest
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
        },
        {
          label: '客单价',
          value: `¥${formatNumber(latest.aov || 0)}`
        },
        {
          label: '退款率',
          value: `${((latest.refund_rate || 0) * 100).toFixed(2)}%`
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

.traffic-sources {
  padding: 10px 0;
}

.source-item {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.source-item:last-child {
  margin-bottom: 0;
}

.source-label {
  width: 70px;
  font-size: 13px;
  color: #606266;
}

.source-bar-wrap {
  flex: 1;
  height: 12px;
  background: #f0f2f5;
  border-radius: 6px;
  overflow: hidden;
}

.source-bar {
  height: 100%;
  background: #409eff;
  border-radius: 6px;
  transition: width 0.3s;
}

.bar-recommend {
  background: #67c23a;
}

.bar-paid {
  background: #e6a23c;
}

.bar-organic {
  background: #909399;
}

.source-value {
  width: 120px;
  font-size: 12px;
  color: #909399;
  text-align: right;
}

.funnel-container {
  padding: 20px;
}

.funnel-item {
  display: flex;
  justify-content: center;
  margin-bottom: 8px;
}

.funnel-bar {
  background: #409eff;
  color: white;
  padding: 12px 20px;
  border-radius: 4px;
  text-align: center;
  font-size: 14px;
}

.funnel-visitors {
  width: 100%;
  background: #409eff;
}

.funnel-cart {
  width: 70%;
  background: #67c23a;
}

.funnel-buyers {
  width: 45%;
  background: #e6a23c;
}

.funnel-rates {
  display: flex;
  justify-content: space-around;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 13px;
  color: #606266;
}

.ad-stat {
  text-align: center;
  padding: 15px 0;
}

.ad-stat-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}

.ad-stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.ad-detail {
  padding: 10px 0;
}

.ad-detail-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}

.ad-detail-value {
  font-size: 18px;
  font-weight: 500;
  margin-bottom: 8px;
}

.ad-detail-bar {
  height: 6px;
  background: #f0f2f5;
  border-radius: 3px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s;
}

.bar-search {
  background: #409eff;
}

.bar-recommend {
  background: #67c23a;
}

.bar-paid {
  background: #e6a23c;
}

.tab-content {
  padding: 20px;
}

.mb-4 {
  margin-bottom: 16px;
}

.metric-value {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
  text-align: center;
  margin-top: 10px;
}

.metric-label {
  font-size: 13px;
  color: #909399;
  text-align: center;
  margin-top: 5px;
}

.empty-hint {
  text-align: center;
  padding: 40px;
  color: #909399;
}

.current-title {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 15px;
}

.title-analysis {
  display: flex;
  gap: 20px;
}

.analysis-item {
  display: flex;
  gap: 8px;
}

.analysis-label {
  color: #909399;
  font-size: 13px;
}

.analysis-value {
  color: #303133;
  font-size: 13px;
  font-weight: 500;
}

.diagnosis-list {
  padding: 10px 0;
}

.diagnosis-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
}

.diagnosis-icon {
  font-size: 16px;
}

.diagnosis-icon.success {
  color: #67c23a;
}

.diagnosis-icon.warning {
  color: #e6a23c;
}

.diagnosis-icon.error {
  color: #f56c6c;
}

.diagnosis-text {
  font-size: 13px;
  color: #606266;
}

.suggestion-list {
  padding: 10px 0;
}

.suggestion-item {
  display: flex;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px dashed #e4e7ed;
}

.suggestion-item:last-child {
  border-bottom: none;
}

.suggestion-number {
  width: 24px;
  height: 24px;
  line-height: 24px;
  text-align: center;
  background: #409eff;
  color: white;
  border-radius: 50%;
  font-size: 12px;
  flex-shrink: 0;
}

.suggestion-text {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}
</style>
