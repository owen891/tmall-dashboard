<template>
  <div class="toolbox-container">
    <div class="header">
      <h2>运营工具箱</h2>
    </div>

    <el-card class="tips-card">
      <template #header>
        <span>每日运营提示</span>
      </template>
      <div class="tips">
        <el-alert
          v-for="tip in dailyTips"
          :key="tip.title"
          :title="tip.title"
          :description="tip.content"
          :type="getTipType(tip.type)"
          show-icon
          :closable="false"
          class="tip-item"
        />
      </div>
    </el-card>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="商品分析" name="analysis">
        <el-card>
          <el-form inline>
            <el-form-item label="选择商品">
              <el-select v-model="selectedProduct" @change="loadAnalysis" placeholder="选择商品" filterable>
                <el-option v-for="p in products" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button @click="loadAnalysis">分析</el-button>
            </el-form-item>
          </el-form>

          <div v-if="analysis" class="analysis-result">
            <el-row :gutter="20">
              <el-col :span="8">
                <el-card class="score-card">
                  <div class="score-value">{{ analysis.health_score }}</div>
                  <div class="score-label">健康分</div>
                </el-card>
              </el-col>
              <el-col :span="8">
                <el-card class="score-card">
                  <div class="score-value">{{ analysis.lifecycle_stage }}</div>
                  <div class="score-label">生命周期</div>
                </el-card>
              </el-col>
              <el-col :span="8">
                <el-card class="score-card">
                  <div class="score-value">{{ analysis.refund_risk }}</div>
                  <div class="score-label">退款风险</div>
                </el-card>
              </el-col>
            </el-row>

            <el-card class="recommendations-card">
              <template #header>
                <span>优化建议</span>
              </template>
              <el-ul>
                <el-li v-for="(rec, index) in analysis.recommendations" :key="index">
                  {{ rec }}
                </el-li>
              </el-ul>
            </el-card>
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="价格建议" name="price">
        <el-card>
          <el-form inline>
            <el-form-item label="选择商品">
              <el-select v-model="selectedProduct" @change="loadPriceRecommendation" placeholder="选择商品" filterable>
                <el-option v-for="p in products" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button @click="loadPriceRecommendation">获取建议</el-button>
            </el-form-item>
          </el-form>

          <div v-if="priceRecommendation" class="price-result">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="当前价格">{{ priceRecommendation.current_price }}</el-descriptions-item>
              <el-descriptions-item label="建议价格">
                <el-tag type="success">{{ priceRecommendation.recommended_price }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="最低价">{{ priceRecommendation.price_range_min }}</el-descriptions-item>
              <el-descriptions-item label="最高价">{{ priceRecommendation.price_range_max }}</el-descriptions-item>
              <el-descriptions-item label="建议理由" :span="2">
                {{ priceRecommendation.reason }}
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="竞品对比" name="competitor">
        <el-card>
          <el-form inline>
            <el-form-item label="选择商品">
              <el-select v-model="selectedProduct" @change="loadCompetitorComparison" placeholder="选择商品" filterable>
                <el-option v-for="p in products" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button @click="loadCompetitorComparison">对比</el-button>
            </el-form-item>
          </el-form>

          <div v-if="competitorComparison" class="competitor-result">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-card>
                  <template #header>
                    <span>您的商品</span>
                  </template>
                  <p>价格: {{ competitorComparison.your_price }}</p>
                  <p>ROI: {{ competitorComparison.your_roi }}</p>
                </el-card>
              </el-col>
              <el-col :span="12">
                <el-card>
                  <template #header>
                    <span>竞品平均</span>
                  </template>
                  <p>价格: {{ competitorComparison.avg_competitor_price }}</p>
                  <p>ROI: {{ competitorComparison.avg_competitor_roi }}</p>
                </el-card>
              </el-col>
            </el-row>
            <el-alert
              :title="competitorComparison.recommendation"
              type="info"
              show-icon
              class="competitor-tip"
            />
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="库存预警" name="inventory">
        <el-card>
          <el-table :data="inventoryAlerts" stripe>
            <el-table-column prop="product_name" label="商品" />
            <el-table-column prop="current_stock" label="当前库存" />
            <el-table-column prop="daily_sales" label="日均销量" />
            <el-table-column prop="days_remaining" label="预计天数">
              <template #default="{ row }">
                <el-tag :type="getUrgencyType(row.urgency)">
                  {{ row.days_remaining }}天
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="recommendation" label="建议" />
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="自动优化" name="auto">
        <el-card>
          <el-form inline>
            <el-form-item label="选择商品">
              <el-select v-model="selectedProduct" @change="loadAutoOptimization" placeholder="选择商品" filterable>
                <el-option v-for="p in products" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadAutoOptimization">获取优化方案</el-button>
            </el-form-item>
          </el-form>

          <div v-if="autoOptimization" class="optimization-result">
            <el-card
              v-for="(opt, index) in autoOptimization.optimizations"
              :key="index"
              class="opt-card"
            >
              <h4>{{ opt.action }}</h4>
              <p>目标: {{ opt.target }}</p>
              <p>建议调整: {{ opt.value }}</p>
              <p>原因: {{ opt.reason }}</p>
            </el-card>
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const activeTab = ref('analysis')
const selectedProduct = ref(null)
const products = ref([])
const dailyTips = ref([])
const analysis = ref(null)
const priceRecommendation = ref(null)
const competitorComparison = ref(null)
const inventoryAlerts = ref([])
const autoOptimization = ref(null)

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

const loadDailyTips = async () => {
  try {
    const res = await axios.get('/api/toolbox/tips/daily')
    if (res.data.code === 200) {
      dailyTips.value = res.data.data || []
    }
  } catch (error) {
    console.error('加载每日提示失败:', error)
  }
}

const loadAnalysis = async () => {
  if (!selectedProduct.value) {
    ElMessage.warning('请选择商品')
    return
  }
  try {
    const res = await axios.get(`/api/toolbox/analysis/product/${selectedProduct.value}`)
    if (res.data.code === 200) {
      analysis.value = res.data.data
    }
  } catch (error) {
    console.error('加载分析失败:', error)
  }
}

const loadPriceRecommendation = async () => {
  if (!selectedProduct.value) {
    ElMessage.warning('请选择商品')
    return
  }
  try {
    const res = await axios.get(`/api/toolbox/price/recommendation/${selectedProduct.value}`)
    if (res.data.code === 200) {
      priceRecommendation.value = res.data.data
    }
  } catch (error) {
    console.error('加载价格建议失败:', error)
  }
}

const loadCompetitorComparison = async () => {
  if (!selectedProduct.value) {
    ElMessage.warning('请选择商品')
    return
  }
  try {
    const res = await axios.get(`/api/toolbox/competitor/compare/${selectedProduct.value}`)
    if (res.data.code === 200) {
      competitorComparison.value = res.data.data
    }
  } catch (error) {
    console.error('加载竞品对比失败:', error)
  }
}

const loadInventoryAlerts = async () => {
  try {
    const res = await axios.get('/api/toolbox/inventory/alerts')
    if (res.data.code === 200) {
      inventoryAlerts.value = res.data.data || []
    }
  } catch (error) {
    console.error('加载库存预警失败:', error)
  }
}

const loadAutoOptimization = async () => {
  if (!selectedProduct.value) {
    ElMessage.warning('请选择商品')
    return
  }
  try {
    const res = await axios.get(`/api/toolbox/auto-optimize/${selectedProduct.value}`)
    if (res.data.code === 200) {
      autoOptimization.value = res.data.data
    }
  } catch (error) {
    console.error('加载自动优化失败:', error)
  }
}

const getTipType = (type) => {
  const map = { success: 'success', warning: 'warning', error: 'error', info: 'info' }
  return map[type] || 'info'
}

const getUrgencyType = (urgency) => {
  const map = { high: 'danger', medium: 'warning', low: 'success' }
  return map[urgency] || 'info'
}

onMounted(() => {
  loadProducts()
  loadDailyTips()
  loadInventoryAlerts()
})
</script>

<style scoped>
.toolbox-container {
  padding: 20px;
}

.header {
  margin-bottom: 20px;
}

.header h2 {
  margin: 0;
}

.tips-card {
  margin-bottom: 20px;
}

.tips {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tip-item {
  margin-bottom: 0;
}

.score-card {
  text-align: center;
  margin-bottom: 20px;
}

.score-value {
  font-size: 36px;
  font-weight: bold;
  color: #409eff;
}

.score-label {
  color: #909399;
  margin-top: 10px;
}

.analysis-result,
.price-result,
.competitor-result,
.optimization-result {
  margin-top: 20px;
}

.competitor-tip {
  margin-top: 20px;
}

.opt-card {
  margin-bottom: 15px;
}

.opt-card h4 {
  margin: 0 0 10px 0;
  color: #409eff;
}

.opt-card p {
  margin: 5px 0;
}
</style>
