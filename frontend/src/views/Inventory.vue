<template>
  <div class="inventory-warning">
    <div class="header">
      <h2>库存预警</h2>
      <div class="controls">
        <el-button type="primary" @click="loadData">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <el-row :gutter="20" class="summary-cards" v-loading="loading">
      <el-col :span="6">
        <el-card class="summary-card critical">
          <div class="summary-content">
            <div class="summary-icon">
              <el-icon><Warning /></el-icon>
            </div>
            <div class="summary-info">
              <div class="summary-value">{{ summary.critical || 0 }}</div>
              <div class="summary-label">紧急预警</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="summary-card warning">
          <div class="summary-content">
            <div class="summary-icon">
              <el-icon><WarningFilled /></el-icon>
            </div>
            <div class="summary-info">
              <div class="summary-value">{{ summary.warning || 0 }}</div>
              <div class="summary-label">一般预警</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="summary-card info">
          <div class="summary-content">
            <div class="summary-icon">
              <el-icon><InfoFilled /></el-icon>
            </div>
            <div class="summary-info">
              <div class="summary-value">{{ summary.info || 0 }}</div>
              <div class="summary-label">提示</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="summary-card">
          <div class="summary-content">
            <div class="summary-icon">
              <el-icon><QuestionFilled /></el-icon>
            </div>
            <div class="summary-info">
              <div class="summary-value">{{ summary.no_data || 0 }}</div>
              <div class="summary-label">无数据商品</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="filter-card">
      <el-form inline>
        <el-form-item label="时间维度">
          <el-select v-model="dimension" @change="loadData" style="width: 120px">
            <el-option label="按日" value="daily" />
            <el-option label="按周" value="weekly" />
            <el-option label="按月" value="monthly" />
          </el-select>
        </el-form-item>
        <el-form-item label="库存下限">
          <el-input-number v-model="lowThreshold" :min="0" @change="loadData" />
        </el-form-item>
        <el-form-item label="库存上限">
          <el-input-number v-model="highThreshold" :min="0" @change="loadData" />
        </el-form-item>
        <el-form-item label="预警级别">
          <el-select v-model="levelFilter" @change="filterWarnings" style="width: 120px">
            <el-option label="全部" value="all" />
            <el-option label="紧急" value="critical" />
            <el-option label="警告" value="warning" />
            <el-option label="提示" value="info" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="预警列表" name="warnings">
        <el-card v-loading="loading">
          <el-table :data="filteredWarnings" stripe>
            <el-table-column prop="product_id" label="商品ID" width="120" />
            <el-table-column prop="title" label="商品名称" min-width="200" />
            <el-table-column prop="tier" label="分层" width="100">
              <template #default="{ row }">
                <el-tag :type="getTierType(row.tier)">{{ row.tier }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="inventory" label="当前库存" width="100" align="right">
              <template #default="{ row }">
                <span :class="getInventoryClass(row)">{{ row.inventory }}件</span>
              </template>
            </el-table-column>
            <el-table-column prop="sales_velocity" label="日均销量" width="100" align="right">
              <template #default="{ row }">
                {{ row.sales_velocity || 0 }}件/天
              </template>
            </el-table-column>
            <el-table-column prop="days_until_stockout" label="预计售完" width="100" align="right">
              <template #default="{ row }">
                <span v-if="row.days_until_stockout">
                  {{ row.days_until_stockout }}天
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="warning_level" label="预警级别" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="getLevelType(row.warning_level)">
                  {{ getLevelText(row.warning_level) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="issue" label="问题描述" min-width="200" />
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="无数据商品" name="no-data">
        <el-card v-loading="loading">
          <el-table :data="productsWithoutData" stripe>
            <el-table-column prop="product_id" label="商品ID" width="120" />
            <el-table-column prop="title" label="商品名称" min-width="200" />
            <el-table-column prop="tier" label="分层" width="100">
              <template #default="{ row }">
                <el-tag :type="getTierType(row.tier)">{{ row.tier }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="issue" label="问题" />
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="销售速度排行" name="velocity">
        <el-card v-loading="velocityLoading">
          <template #header>
            <span>按日均销售速度排行</span>
          </template>
          <el-table :data="velocityData" stripe>
            <el-table-column type="index" label="排名" width="80" />
            <el-table-column prop="product_id" label="商品ID" width="120" />
            <el-table-column prop="title" label="商品名称" min-width="200" />
            <el-table-column prop="tier" label="分层" width="100">
              <template #default="{ row }">
                <el-tag :type="getTierType(row.tier)">{{ row.tier }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="daily_velocity" label="日均销量" width="120" align="right">
              <template #default="{ row }">
                <span class="text-success">{{ row.daily_velocity || 0 }}件/天</span>
              </template>
            </el-table-column>
            <el-table-column prop="inventory" label="当前库存" width="100" align="right">
              <template #default="{ row }">
                {{ row.inventory || 0 }}件
              </template>
            </el-table-column>
            <el-table-column prop="days_remaining" label="库存可售天数" width="120" align="right">
              <template #default="{ row }">
                <el-tag v-if="row.days_remaining" :type="getDaysType(row.days_remaining)">
                  {{ row.days_remaining }}天
                </el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Refresh, Warning, WarningFilled, InfoFilled, QuestionFilled } from '@element-plus/icons-vue'
import api from '@/api'
import { getTierType } from '@/utils/format'

const dimension = ref('weekly')
const loading = ref(true)
const velocityLoading = ref(false)
const warnings = ref([])
const productsWithoutData = ref([])
const velocityData = ref([])
const summary = ref({})
const activeTab = ref('warnings')
const levelFilter = ref('all')
const lowThreshold = ref(50)
const highThreshold = ref(500)

const filteredWarnings = computed(() => {
  if (levelFilter.value === 'all') {
    return warnings.value
  }
  return warnings.value.filter(w => w.warning_level === levelFilter.value)
})

const getLevelType = (level) => {
  const types = {
    'critical': 'danger',
    'warning': 'warning',
    'info': 'info'
  }
  return types[level] || 'info'
}

const getLevelText = (level) => {
  const texts = {
    'critical': '紧急',
    'warning': '警告',
    'info': '提示'
  }
  return texts[level] || level
}

const getInventoryClass = (row) => {
  if (row.warning_level === 'critical') return 'text-danger'
  if (row.warning_level === 'warning') return row.inventory < row.sales_velocity * 7 ? 'text-warning' : ''
  return ''
}

const getDaysType = (days) => {
  if (days <= 3) return 'danger'
  if (days <= 7) return 'warning'
  return 'success'
}

const loadData = async () => {
  loading.value = true
  try {
    const params = {
      dimension: dimension.value,
      low_threshold: lowThreshold.value,
      high_threshold: highThreshold.value
    }

    const res = await api.getInventoryWarnings(params)
    const data = res.data || res || {}

    warnings.value = data.warnings || []
    productsWithoutData.value = data.products_without_data || []
    summary.value = data.summary || {}
  } catch (error) {
    console.error('Load data error:', error)
  } finally {
    loading.value = false
  }
}

const loadVelocity = async () => {
  if (activeTab.value !== 'velocity') return

  velocityLoading.value = true
  try {
    const params = {
      dimension: dimension.value,
      limit: 50
    }
    const res = await api.getInventoryVelocity(params)
    velocityData.value = res.data?.products || res?.products || []
  } catch (error) {
    console.error('Load velocity error:', error)
  } finally {
    velocityLoading.value = false
  }
}

const filterWarnings = () => {
}

import { watch } from 'vue'
watch(activeTab, (newTab) => {
  if (newTab === 'velocity' && velocityData.value.length === 0) {
    loadVelocity()
  }
})

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.inventory-warning {
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

.summary-cards {
  margin-bottom: 20px;
}

.summary-card {
  cursor: default;
}

.summary-card.critical {
  border-left: 4px solid #f56c6c;
}

.summary-card.warning {
  border-left: 4px solid #e6a23c;
}

.summary-card.info {
  border-left: 4px solid #909399;
}

.summary-content {
  display: flex;
  align-items: center;
  gap: 15px;
}

.summary-icon {
  width: 50px;
  height: 50px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  background: #f5f7fa;
}

.summary-card.critical .summary-icon {
  background: #fef0f0;
  color: #f56c6c;
}

.summary-card.warning .summary-icon {
  background: #fdf6ec;
  color: #e6a23c;
}

.summary-card.info .summary-icon {
  background: #f4f4f5;
  color: #909399;
}

.summary-info {
  flex: 1;
}

.summary-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.summary-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.filter-card {
  margin-bottom: 20px;
}

.text-danger {
  color: #f56c6c;
  font-weight: bold;
}

.text-warning {
  color: #e6a23c;
}

.text-success {
  color: #67c23a;
}
</style>
