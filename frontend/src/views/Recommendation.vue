<template>
  <div class="recommendation-page page-container">
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-icon><MagicStick /></el-icon>
            <span>智能选品推荐</span>
          </div>
          <el-button type="primary" @click="loadRecommendations" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新推荐
          </el-button>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="商品推荐" name="products">
          <div class="recommendations-grid">
            <el-card 
              v-for="item in recommendations" 
              :key="item.product_id"
              class="recommendation-card"
              shadow="hover"
            >
              <div class="product-header">
                <span class="recommendation-badge" :class="getBadgeClass(item.recommendation_type)">
                  {{ item.recommendation_type }}
                </span>
                <span class="score-badge">
                  <el-icon><Star /></el-icon>
                  {{ item.score }}
                </span>
              </div>
              <h4 class="product-title">{{ item.title }}</h4>
              <div class="product-meta">
                <el-tag size="small">{{ item.category }}</el-tag>
                <el-tag size="small" :type="getTierType(item.tier)">{{ item.tier }}</el-tag>
              </div>
              <div class="product-stats">
                <div class="stat-item">
                  <span class="label">销售额</span>
                  <span class="value">¥{{ formatNumber(item.payment_amount) }}</span>
                </div>
                <div class="stat-item">
                  <span class="label">ROI</span>
                  <span class="value">{{ Number(item.ad_roi || 0).toFixed(2) }}</span>
                </div>
                <div class="stat-item">
                  <span class="label">转化率</span>
                  <span class="value">{{ (Number(item.conversion || 0) * 100).toFixed(2) }}%</span>
                </div>
              </div>
              <div class="reasons">
                <div class="reason-title">推荐理由：</div>
                <el-tag 
                  v-for="reason in item.reasons" 
                  :key="reason"
                  size="small"
                  type="info"
                  class="reason-tag"
                >
                  {{ reason }}
                </el-tag>
              </div>
            </el-card>
          </div>
        </el-tab-pane>

        <el-tab-pane label="价格优化" name="price">
          <el-table :data="priceOptimizations" stripe v-loading="loading">
            <el-table-column prop="title" label="商品" min-width="200" show-overflow-tooltip />
            <el-table-column label="当前价格" width="120" align="center">
              <template #default="{ row }">
                <span class="price-current">¥{{ row.current_price }}</span>
              </template>
            </el-table-column>
            <el-table-column label="建议价格" width="120" align="center">
              <template #default="{ row }">
                <span class="price-suggested">¥{{ row.suggested_price }}</span>
              </template>
            </el-table-column>
            <el-table-column label="调整幅度" width="100" align="center">
              <template #default="{ row }">
                <el-tag 
                  :type="row.price_change > 0 ? 'success' : row.price_change < 0 ? 'danger' : 'info'"
                >
                  {{ row.price_change > 0 ? '+' : '' }}{{ row.price_change }}%
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="action" label="操作建议" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="getActionType(row.action)">{{ row.action }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="原因" min-width="180" />
            <el-table-column label="置信度" width="100" align="center">
              <template #default="{ row }">
                <el-progress 
                  :percentage="row.confidence" 
                  :color="getConfidenceColor(row.confidence)"
                  :stroke-width="10"
                />
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="关键词优化" name="keywords">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-card>
                <template #header>
                  <span>推荐关键词</span>
                </template>
                <el-table :data="keywords" stripe>
                  <el-table-column prop="keyword" label="关键词" width="120" />
                  <el-table-column prop="search_volume" label="搜索量" width="100" align="center">
                    <template #default="{ row }">
                      <span class="highlight">{{ formatNumber(row.search_volume) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="competition" label="竞争度" width="120">
                    <template #default="{ row }">
                      <el-progress 
                        :percentage="(row.competition * 100).toFixed(0)" 
                        :color="getCompetitionColor(row.competition)"
                      />
                    </template>
                  </el-table-column>
                  <el-table-column prop="opportunity_score" label="机会分" width="100" align="center">
                    <template #default="{ row }">
                      <el-tag 
                        :type="row.opportunity_score > 70 ? 'success' : row.opportunity_score > 50 ? 'warning' : 'info'"
                      >
                        {{ row.opportunity_score }}
                      </el-tag>
                    </template>
                  </el-table-column>
                </el-table>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card>
                <template #header>
                  <span>关键词使用建议</span>
                </template>
                <div class="tips-list">
                  <el-alert
                    v-for="tip in keywordTips"
                    :key="tip.title"
                    :title="tip.title"
                    :description="tip.content"
                    :type="tip.type"
                    :closable="false"
                    show-icon
                    class="tip-item"
                  />
                </div>
              </el-card>
            </el-col>
          </el-row>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { formatNumber, getTierType } from '@/utils/format'

const activeTab = ref('products')
const loading = ref(false)
const recommendations = ref([])
const priceOptimizations = ref([])
const keywords = ref([])

const keywordTips = [
  { title: '高机会分词', content: '机会分>70的关键词优先投放', type: 'success' },
  { title: '低竞争词', content: '竞争度<0.6的词更容易获得曝光', type: 'info' },
  { title: '标题优化', content: '建议在标题中加入高机会分关键词', type: 'warning' },
  { title: '长尾词', content: '长尾关键词转化率更高', type: '' }
]

const loadRecommendations = async () => {
  loading.value = true
  try {
    const [recoRes, priceRes, keywordRes] = await Promise.all([
      api.getProductRecommendations(),
      api.getPriceOptimizations(),
      api.getKeywordRecommendations()
    ])
    
    recommendations.value = recoRes.data?.items || []
    priceOptimizations.value = priceRes.data?.items || []
    keywords.value = keywordRes.data?.items || []
    
    if (recoRes.data?.total === 0) {
      ElMessage.info('暂无推荐数据，请先导入商品数据')
    }
  } catch (error) {
    console.error('Load recommendations error:', error)
    ElMessage.error('加载推荐数据失败')
  } finally {
    loading.value = false
  }
}

const getBadgeClass = (type) => {
  const classes = {
    '爆款潜力': 'badge-hot',
    '增长明星': 'badge-growth',
    '稳定款': 'badge-stable',
    '待优化': 'badge-warning'
  }
  return classes[type] || 'badge-default'
}

const getActionType = (action) => {
  const types = {
    '提价': 'success',
    '降价': 'danger',
    '小幅降价': 'warning',
    '维持': 'info'
  }
  return types[action] || 'info'
}

const getConfidenceColor = (confidence) => {
  if (confidence >= 90) return '#67c23a'
  if (confidence >= 70) return '#409eff'
  return '#e6a23c'
}

const getCompetitionColor = (competition) => {
  if (competition < 0.5) return '#67c23a'
  if (competition < 0.7) return '#409eff'
  return '#f56c6c'
}

onMounted(() => {
  loadRecommendations()
})
</script>

<style scoped>
.recommendation-page {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 500;
}

.recommendations-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 20px;
  padding: 10px 0;
}

.recommendation-card {
  transition: transform 0.2s, box-shadow 0.2s;
}

.recommendation-card:hover {
  transform: translateY(-4px);
}

.product-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.recommendation-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.badge-hot {
  background: linear-gradient(135deg, #ff6b6b, #ee5a24);
  color: white;
}

.badge-growth {
  background: linear-gradient(135deg, #4ecdc4, #44bd8c);
  color: white;
}

.badge-stable {
  background: linear-gradient(135deg, #45aaf2, #2d98da);
  color: white;
}

.badge-warning {
  background: linear-gradient(135deg, #f7b731, #f79f1f);
  color: white;
}

.badge-default {
  background: #909399;
  color: white;
}

.score-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #e6a23c;
  font-weight: 600;
}

.product-title {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #303133;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.product-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.product-stats {
  display: flex;
  justify-content: space-between;
  padding: 12px 0;
  border-top: 1px solid #f0f0f0;
  border-bottom: 1px solid #f0f0f0;
  margin-bottom: 12px;
}

.stat-item {
  text-align: center;
}

.stat-item .label {
  display: block;
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.stat-item .value {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.reasons {
  margin-top: 8px;
}

.reason-title {
  font-size: 12px;
  color: #606266;
  margin-bottom: 8px;
}

.reason-tag {
  margin-right: 4px;
  margin-bottom: 4px;
}

.price-current {
  color: #909399;
  text-decoration: line-through;
}

.price-suggested {
  color: #409eff;
  font-weight: 600;
}

.highlight {
  color: #409eff;
  font-weight: 600;
}

.tips-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
</style>
