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

      <el-tab-pane label="评价生成主图建议" name="main-image-suggest">
        <el-card>
          <template #header>
            <span>🖼️ 评价生成主图建议 - 分析好评数据，提取核心卖点</span>
          </template>
          <el-form inline>
            <el-form-item label="商品ID（可选）">
              <el-input v-model="imageSuggestParams.product_id" placeholder="留空则分析全部商品" />
            </el-form-item>
            <el-form-item label="分析评价数量">
              <el-input-number v-model="imageSuggestParams.limit" :min="10" :max="200" :step="10" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadImageSuggestion" :loading="imageSuggestLoading">生成建议</el-button>
            </el-form-item>
          </el-form>

          <div v-if="imageSuggestionResult" class="tool-result">
            <el-alert :title="imageSuggestionResult.analysis_summary" type="success" show-icon class="mb-4" />
            <p class="text-gray-600">分析评价数: {{ imageSuggestionResult.review_count }}</p>
            
            <el-row :gutter="20" class="mt-4">
              <el-col :span="12">
                <el-card>
                  <template #header>🎯 核心卖点</template>
                  <div v-if="imageSuggestionResult.suggestions.core_selling_points.length">
                    <el-tag v-for="(point, idx) in imageSuggestionResult.suggestions.core_selling_points" :key="idx" class="mr-2 mb-2">
                      {{ point.name }} ({{ point.count }})
                    </el-tag>
                  </div>
                  <div v-else>暂无数据</div>
                </el-card>
              </el-col>
              <el-col :span="12">
                <el-card>
                  <template #header>🎬 使用场景</template>
                  <div v-if="imageSuggestionResult.suggestions.scene_suggestions.length">
                    <el-tag v-for="(scene, idx) in imageSuggestionResult.suggestions.scene_suggestions" :key="idx" class="mr-2 mb-2">
                      {{ scene.name }} ({{ scene.count }})
                    </el-tag>
                  </div>
                  <div v-else>暂无数据</div>
                </el-card>
              </el-col>
            </el-row>

            <el-card class="mt-4">
              <template #header>🔑 热门关键词</template>
              <div v-if="imageSuggestionResult.suggestions.keyword_suggestions.length">
                <el-tag v-for="(kw, idx) in imageSuggestionResult.suggestions.keyword_suggestions" :key="idx" class="mr-2 mb-2">
                  {{ kw.word }} ({{ kw.count }})
                </el-tag>
              </div>
              <div v-else>暂无数据</div>
            </el-card>

            <el-card class="mt-4">
              <template #header>📋 优化方向</template>
              <ol>
                <li v-for="(dir, idx) in imageSuggestionResult.suggestions.optimization_directions" :key="idx" class="mb-2">
                  {{ dir }}
                </li>
              </ol>
            </el-card>
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="评价仿写助手" name="review-reply">
        <el-card>
          <template #header>✍️ 评价仿写助手 - 根据评价内容自动生成专业回复</template>
          <el-form label-width="120px">
            <el-form-item label="评价内容">
              <el-input v-model="replyParams.review_text" type="textarea" :rows="4" placeholder="请输入需要回复的评价内容" />
            </el-form-item>
            <el-form-item label="回复风格">
              <el-select v-model="replyParams.reply_style" placeholder="选择回复风格">
                <el-option label="专业正式" value="专业正式" />
                <el-option label="亲切温暖" value="亲切温暖" />
                <el-option label="简洁高效" value="简洁高效" />
              </el-select>
            </el-form-item>
            <el-form-item label="商品类型">
              <el-input v-model="replyParams.product_type" placeholder="如：连衣裙、手机壳、零食（可选）" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadReviewReply" :loading="replyLoading">生成回复</el-button>
            </el-form-item>
          </el-form>

          <div v-if="replyResult" class="tool-result">
            <el-alert :title="'检测为' + replyResult.detected_sentiment_label + '评价'" type="info" show-icon class="mb-4" />
            
            <div v-for="(reply, idx) in replyResult.replies" :key="idx" class="mb-4">
              <el-card>
                <template #header>
                  <span>{{ reply.style }}</span>
                  <el-button type="primary" text @click="copyText(reply.content)">复制</el-button>
                </template>
                <p>{{ reply.content }}</p>
              </el-card>
            </div>
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="商品详情页诊断" name="product-diagnose">
        <el-card>
          <template #header>🔍 商品详情页诊断 - 综合分析商品数据，诊断详情页各维度优化机会</template>
          <el-form inline>
            <el-form-item label="商品ID">
              <el-input v-model="diagnoseParams.product_id" placeholder="请输入商品ID" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadProductDiagnose" :loading="diagnoseLoading">开始诊断</el-button>
            </el-form-item>
          </el-form>

          <div v-if="diagnoseResult" class="tool-result">
            <el-card class="mb-4">
              <template #header>📊 商品信息</template>
              <el-descriptions :column="2" border>
                <el-descriptions-item label="商品ID">{{ diagnoseResult.product_info.product_id }}</el-descriptions-item>
                <el-descriptions-item label="商品标题">{{ diagnoseResult.product_info.title }}</el-descriptions-item>
                <el-descriptions-item label="类目">{{ diagnoseResult.product_info.category }}</el-descriptions-item>
                <el-descriptions-item label="分层">{{ diagnoseResult.product_info.tier }}</el-descriptions-item>
              </el-descriptions>
            </el-card>

            <el-card class="mb-4">
              <template #header>⭐ 综合评分</template>
              <div class="text-center py-4">
                <div class="score-value">{{ diagnoseResult.overall_score }}</div>
                <div class="score-label">综合健康分</div>
              </div>
            </el-card>

            <el-row :gutter="20" class="mb-4">
              <el-col v-for="(d, idx) in diagnoseResult.diagnostics" :key="idx" :span="8">
                <el-card>
                  <template #header>
                    <span>{{ d.area }}</span>
                  </template>
                  <el-progress :percentage="d.score" :color="getDiagnosisColor(d.level)" :stroke-width="20" />
                  <p class="text-sm text-gray-600 mt-2">{{ d.metric }}</p>
                  <p class="text-sm font-medium">{{ d.level }}</p>
                  <p class="text-xs text-gray-500">{{ d.suggestion }}</p>
                </el-card>
              </el-col>
            </el-row>

            <el-card>
              <template #header>🔝 优先改进项</template>
              <div v-for="(p, idx) in diagnoseResult.priority_actions" :key="idx" class="mb-3 pb-3 border-b last:border-0">
                <el-tag :type="getPriorityTagType(p.score)" class="mr-2">{{ p.area }}</el-tag>
                <span class="text-sm">{{ p.action }}</span>
              </div>
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
import api from '@/api'

const activeTab = ref('analysis')
const selectedProduct = ref(null)
const products = ref([])
const dailyTips = ref([])
const analysis = ref(null)
const priceRecommendation = ref(null)
const competitorComparison = ref(null)
const inventoryAlerts = ref([])
const autoOptimization = ref(null)

// 新工具状态
const imageSuggestParams = ref({
  product_id: '',
  limit: 50
})
const imageSuggestLoading = ref(false)
const imageSuggestionResult = ref(null)

const replyParams = ref({
  review_text: '',
  reply_style: '专业正式',
  product_type: ''
})
const replyLoading = ref(false)
const replyResult = ref(null)

const diagnoseParams = ref({
  product_id: ''
})
const diagnoseLoading = ref(false)
const diagnoseResult = ref(null)

const loadProducts = async () => {
  try {
    const res = await api.get('/products')
    if (res.code === 200 || res.data) {
      products.value = res.data || res
    }
  } catch (error) {
    console.error('加载商品失败:', error)
  }
}

const loadDailyTips = async () => {
  try {
    const res = await api.get('/toolbox/tips/daily')
    if (res.code === 200 || res.data) {
      dailyTips.value = res.data || []
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
    const res = await api.get(`/toolbox/analysis/product/${selectedProduct.value}`)
    if (res.code === 200 || res.data) {
      analysis.value = res.data || res
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
    const res = await api.get(`/toolbox/price/recommendation/${selectedProduct.value}`)
    if (res.code === 200 || res.data) {
      priceRecommendation.value = res.data || res
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
    const res = await api.get(`/toolbox/competitor/compare/${selectedProduct.value}`)
    if (res.code === 200 || res.data) {
      competitorComparison.value = res.data || res
    }
  } catch (error) {
    console.error('加载竞品对比失败:', error)
  }
}

const loadInventoryAlerts = async () => {
  try {
    const res = await api.get('/toolbox/inventory/alerts')
    if (res.code === 200 || res.data) {
      inventoryAlerts.value = res.data || []
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
    const res = await api.get(`/toolbox/auto-optimize/${selectedProduct.value}`)
    if (res.code === 200 || res.data) {
      autoOptimization.value = res.data || res
    }
  } catch (error) {
    console.error('加载自动优化失败:', error)
  }
}

// 新工具函数
const loadImageSuggestion = async () => {
  imageSuggestLoading.value = true
  try {
    const res = await api.post('/toolbox/tools/execute', {
      tool_id: 'main_image_suggest',
      params: imageSuggestParams.value
    })
    if (res.code === 200 && res.data) {
      imageSuggestionResult.value = res.data.result
      ElMessage.success('分析成功！')
    } else if (res.message) {
      ElMessage.warning(res.message)
    }
  } catch (error) {
    console.error('加载主图建议失败:', error)
    ElMessage.error('分析失败，请稍后重试')
  } finally {
    imageSuggestLoading.value = false
  }
}

const loadReviewReply = async () => {
  if (!replyParams.value.review_text) {
    ElMessage.warning('请输入评价内容')
    return
  }
  replyLoading.value = true
  try {
    const res = await api.post('/toolbox/tools/execute', {
      tool_id: 'review_reply',
      params: replyParams.value
    })
    if (res.code === 200 && res.data) {
      replyResult.value = res.data.result
      if (replyResult.value.error) {
        ElMessage.warning(replyResult.value.error)
      } else {
        ElMessage.success('生成成功！')
      }
    } else if (res.message) {
      ElMessage.warning(res.message)
    }
  } catch (error) {
    console.error('生成回复失败:', error)
    ElMessage.error('生成失败，请稍后重试')
  } finally {
    replyLoading.value = false
  }
}

const loadProductDiagnose = async () => {
  if (!diagnoseParams.value.product_id) {
    ElMessage.warning('请输入商品ID')
    return
  }
  diagnoseLoading.value = true
  try {
    const res = await api.post('/toolbox/tools/execute', {
      tool_id: 'product_diagnose',
      params: diagnoseParams.value
    })
    if (res.code === 200 && res.data) {
      diagnoseResult.value = res.data.result
      if (diagnoseResult.value.error) {
        ElMessage.warning(diagnoseResult.value.error)
      } else {
        ElMessage.success('诊断成功！')
      }
    } else if (res.message) {
      ElMessage.warning(res.message)
    }
  } catch (error) {
    console.error('诊断失败:', error)
    ElMessage.error('诊断失败，请稍后重试')
  } finally {
    diagnoseLoading.value = false
  }
}

const copyText = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('复制成功！')
  } catch (error) {
    console.error('复制失败:', error)
    ElMessage.error('复制失败')
  }
}

const getDiagnosisColor = (level) => {
  const map = {
    '优秀': '#67c23a',
    '良好': '#409eff',
    '待优化': '#e6a23c',
    '需改进': '#f56c6c'
  }
  return map[level] || '#909399'
}

const getPriorityTagType = (score) => {
  if (score < 40) return 'danger'
  if (score < 60) return 'warning'
  if (score < 80) return 'info'
  return 'success'
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
