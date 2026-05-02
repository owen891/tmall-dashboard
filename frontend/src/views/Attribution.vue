<template>
  <div class="attribution-analysis">
    <div class="header">
      <h2>异动归因分析</h2>
      <div class="controls">
        <el-select v-model="dimension" @change="loadData" style="width: 120px">
          <el-option label="按日" value="daily" />
          <el-option label="按周" value="weekly" />
          <el-option label="按月" value="monthly" />
        </el-select>
      </div>
    </div>

    <el-alert
      v-if="highSeverity > 0"
      :title="`检测到 ${highSeverity} 个高严重度异动`"
      type="error"
      show-icon
      style="margin-bottom: 20px"
    />

    <el-row :gutter="20" class="anomaly-cards" v-loading="loading">
      <el-col :span="6" v-for="(anomaly, index) in anomalies" :key="index">
        <el-card class="anomaly-card" :class="anomaly.severity">
          <div class="anomaly-content">
            <div class="anomaly-label">{{ anomaly.label }}</div>
            <div class="anomaly-change" :class="anomaly.direction">
              <span v-if="anomaly.direction === 'up'">↑</span>
              <span v-else>↓</span>
              {{ Math.abs(anomaly.change_pct) }}%
            </div>
            <div class="anomaly-values">
              <div>当期: {{ formatNumber(anomaly.current) }}</div>
              <div>上期: {{ formatNumber(anomaly.previous) }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6" v-if="anomalies.length === 0 && !loading">
        <el-card>
          <el-empty description="暂无异动" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="商品贡献分析" name="contribution">
        <el-card v-loading="loading">
          <el-table :data="contributions" stripe>
            <el-table-column type="index" label="排名" width="60" />
            <el-table-column prop="product_id" label="商品ID" width="120" />
            <el-table-column prop="title" label="商品名称" min-width="200" />
            <el-table-column prop="tier" label="分层" width="100">
              <template #default="{ row }">
                <el-tag :type="getTierType(row.tier)">{{ row.tier || '未分类' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="当期" align="center">
              <el-table-column prop="current_value" label="数值" align="right">
                <template #default="{ row }">
                  ¥{{ formatNumber(row.current_value) }}
                </template>
              </el-table-column>
            </el-table-column>
            <el-table-column label="上期" align="center">
              <el-table-column prop="prev_value" label="数值" align="right">
                <template #default="{ row }">
                  ¥{{ formatNumber(row.prev_value) }}
                </template>
              </el-table-column>
            </el-table-column>
            <el-table-column prop="change" label="变化" width="100" align="right">
              <template #default="{ row }">
                <span :class="row.impact === 'positive' ? 'text-success' : 'text-danger'">
                  {{ row.change > 0 ? '+' : '' }}{{ formatNumber(row.change) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="contribution_pct" label="贡献度" width="100" align="center">
              <template #default="{ row }">
                <el-progress
                  :percentage="Math.min(100, Math.abs(row.contribution_pct))"
                  :color="row.impact === 'positive' ? '#67C23A' : '#F56C6C'"
                  :stroke-width="8"
                />
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="漏斗流失分析" name="funnel">
        <el-card v-loading="loading">
          <template #header>
            <span>转化漏斗 - 流失点分析</span>
          </template>
          <div class="funnel-chart">
            <el-steps direction="vertical" :space="100" :active="drops.length">
              <el-step
                v-for="(stage, index) in funnel"
                :key="index"
                :title="stage.stage"
                :description="`${formatNumber(stage.value)} (${stage.rate}%)`"
              />
            </el-steps>
          </div>

          <el-divider />

          <h4>流失点详情</h4>
          <el-table :data="drops" stripe>
            <el-table-column prop="from_stage" label="从" width="100" />
            <el-table-column prop="to_stage" label="到" width="100" />
            <el-table-column prop="drop_count" label="流失数量" width="100" align="right">
              <template #default="{ row }">
                {{ formatNumber(row.drop_count) }}
              </template>
            </el-table-column>
            <el-table-column prop="drop_rate" label="流失率" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.severity === 'high' ? 'danger' : row.severity === 'medium' ? 'warning' : 'info'">
                  {{ row.drop_rate }}%
                </el-tag>
              </template>
            </el-table-column>
          </el-table>

          <el-divider />

          <h4>优化建议</h4>
          <el-alert
            v-for="(suggestion, index) in suggestions"
            :key="index"
            :title="suggestion"
            type="info"
            show-icon
            :closable="false"
            style="margin-bottom: 10px"
          />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="根因分析" name="root-cause">
        <el-card>
          <el-form inline>
            <el-form-item label="选择商品">
              <el-select
                v-model="selectedProductId"
                filterable
                placeholder="输入商品ID搜索"
                style="width: 300px"
                @change="loadRootCause"
              >
                <el-option
                  v-for="p in productList"
                  :key="p.product_id"
                  :label="p.title"
                  :value="p.product_id"
                />
              </el-select>
            </el-form-item>
          </el-form>

          <div v-if="rootCauses.length > 0" v-loading="rootCauseLoading">
            <el-divider />
            <div v-for="(cause, index) in rootCauses" :key="index" class="cause-item">
              <el-card :class="cause.severity">
                <template #header>
                  <span>{{ cause.label }}</span>
                  <el-tag
                    :type="cause.severity === 'high' ? 'danger' : cause.severity === 'medium' ? 'warning' : 'info'"
                    size="small"
                    style="float: right"
                  >
                    {{ cause.severity === 'high' ? '高' : cause.severity === 'medium' ? '中' : '低' }}
                  </el-tag>
                </template>
                <p>{{ cause.description }}</p>
                <el-divider />
                <p class="suggestion">
                  <strong>建议:</strong> {{ cause.suggestion }}
                </p>
              </el-card>
            </div>
          </div>
          <el-empty v-else-if="selectedProductId" description="暂无根因数据" />
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/api'

const dimension = ref('weekly')
const loading = ref(true)
const rootCauseLoading = ref(false)
const activeTab = ref('contribution')
const anomalies = ref([])
const highSeverity = ref(0)
const contributions = ref([])
const funnel = ref([])
const drops = ref([])
const suggestions = ref([])
const rootCauses = ref([])
const selectedProductId = ref('')
const productList = ref([])

const formatNumber = (num) => {
  if (!num && num !== 0) return '0'
  num = Number(num)
  if (num >= 10000) {
    return (num / 10000).toFixed(2) + '万'
  }
  return num.toLocaleString()
}

const getTierType = (tier) => {
  const types = { '引流款': 'success', '利润款': 'primary', '潜力款': 'warning' }
  return types[tier] || 'info'
}

const loadData = async () => {
  loading.value = true
  try {
    const [detectRes, drilldownRes, funnelRes] = await Promise.all([
      api.request.get(`/attribution/detect?dimension=${dimension.value}`),
      api.request.get(`/attribution/drilldown?dimension=${dimension.value}&metric=payment_amount`),
      api.request.get(`/attribution/funnel-drop?dimension=${dimension.value}`)
    ])

    anomalies.value = detectRes.data?.anomalies || []
    highSeverity.value = detectRes.data?.high_severity || 0
    contributions.value = drilldownRes.data?.contributions || []
    funnel.value = funnelRes.data?.funnel || []
    drops.value = funnelRes.data?.drops || []
    suggestions.value = funnelRes.data?.suggestions || []

    loadProducts()
  } catch (error) {
    console.error('Load data error:', error)
  } finally {
    loading.value = false
  }
}

const loadProducts = async () => {
  try {
    const res = await api.getProducts({ limit: 100 })
    productList.value = res.data?.products || []
  } catch (error) {
    console.error('Load products error:', error)
  }
}

const loadRootCause = async () => {
  if (!selectedProductId.value) return

  rootCauseLoading.value = true
  try {
    const res = await api.request.get(
      `/attribution/root-cause?product_id=${selectedProductId.value}&dimension=${dimension.value}`
    )
    rootCauses.value = res.data?.root_causes || []
  } catch (error) {
    console.error('Load root cause error:', error)
  } finally {
    rootCauseLoading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.attribution-analysis {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header h2 {
  margin: 0;
}

.anomaly-cards {
  margin-bottom: 20px;
}

.anomaly-card {
  cursor: default;
}

.anomaly-card.high {
  border-left: 4px solid #F56C6C;
}

.anomaly-card.medium {
  border-left: 4px solid #E6A23C;
}

.anomaly-content {
  text-align: center;
}

.anomaly-label {
  font-size: 16px;
  font-weight: bold;
  margin-bottom: 10px;
}

.anomaly-change {
  font-size: 24px;
  font-weight: bold;
}

.anomaly-change.up {
  color: #67C23A;
}

.anomaly-change.down {
  color: #F56C6C;
}

.anomaly-values {
  margin-top: 10px;
  font-size: 12px;
  color: #909399;
}

.funnel-chart {
  padding: 20px;
}

.cause-item {
  margin-bottom: 15px;
}

.cause-item .el-card.high {
  border-left: 4px solid #F56C6C;
}

.cause-item .el-card.medium {
  border-left: 4px solid #E6A23C;
}

.suggestion {
  color: #409EFF;
  margin: 0;
}

.text-success {
  color: #67C23A;
}

.text-danger {
  color: #F56C6C;
}
</style>
