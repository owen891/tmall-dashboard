<template>
  <div class="dashboard">
    <el-row :gutter="20" class="kpi-cards">
      <el-col :span="6">
        <el-card class="kpi-card">
          <div class="kpi-content">
            <div class="kpi-icon" style="background: #409eff">
              <el-icon><TrendCharts /></el-icon>
            </div>
            <div class="kpi-info">
              <div class="kpi-value">¥{{ formatNumber(summary.total_gmv) }}</div>
              <div class="kpi-label">总 GMV</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="kpi-card">
          <div class="kpi-content">
            <div class="kpi-icon" style="background: #67c23a">
              <el-icon><User /></el-icon>
            </div>
            <div class="kpi-info">
              <div class="kpi-value">{{ formatNumber(summary.total_visitors) }}</div>
              <div class="kpi-label">总访客数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="kpi-card">
          <div class="kpi-content">
            <div class="kpi-icon" style="background: #e6a23c">
              <el-icon><Money /></el-icon>
            </div>
            <div class="kpi-info">
              <div class="kpi-value">¥{{ formatNumber(summary.total_ad_spend) }}</div>
              <div class="kpi-label">广告支出</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="kpi-card">
          <div class="kpi-content">
            <div class="kpi-icon" style="background: #f56c6c">
              <el-icon><DataAnalysis /></el-icon>
            </div>
            <div class="kpi-info">
              <div class="kpi-value">{{ summary.avg_roi?.toFixed(2) || 0 }}</div>
              <div class="kpi-label">平均 ROI</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="charts-row">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>热销商品 TOP10</span>
            </div>
          </template>
          <el-table :data="topProducts" style="width: 100%">
            <el-table-column prop="title" label="商品名称" />
            <el-table-column prop="tier" label="分层" width="100">
              <template #default="{ row }">
                <el-tag :type="getTierType(row.tier)">{{ row.tier }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="net_sales" label="GMV" width="120">
              <template #default="{ row }">
                ¥{{ formatNumber(row.net_sales) }}
              </template>
            </el-table-column>
            <el-table-column prop="visitors" label="访客数" width="100" />
            <el-table-column prop="conversion" label="转化率" width="100">
              <template #default="{ row }">
                {{ (row.conversion * 100).toFixed(2) }}%
              </template>
            </el-table-column>
            <el-table-column prop="roi" label="ROI" width="100">
              <template #default="{ row }">
                <span :style="{ color: row.roi >= 3 ? '#67c23a' : '#f56c6c' }">
                  {{ row.roi?.toFixed(2) }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/api'

const summary = ref({})
const topProducts = ref([])

const formatNumber = (num) => {
  if (!num) return '0'
  if (num >= 10000) {
    return (num / 10000).toFixed(2) + '万'
  }
  return num.toLocaleString()
}

const getTierType = (tier) => {
  const types = {
    '引流款': 'success',
    '利润款': 'primary',
    '潜力款': 'warning'
  }
  return types[tier] || 'info'
}

const loadData = async () => {
  try {
    const [summaryRes, topRes] = await Promise.all([
      api.getDashboardSummary(),
      api.getTopProducts()
    ])
    summary.value = summaryRes.data || {}
    topProducts.value = topRes.data || []
  } catch (error) {
    console.error('Load data error:', error)
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.dashboard {
  width: 100%;
}

.kpi-cards {
  margin-bottom: 20px;
}

.kpi-card {
  height: 120px;
}

.kpi-content {
  display: flex;
  align-items: center;
  height: 100%;
}

.kpi-icon {
  width: 60px;
  height: 60px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 30px;
  margin-right: 20px;
}

.kpi-info {
  flex: 1;
}

.kpi-value {
  font-size: 28px;
  font-weight: 600;
  margin-bottom: 5px;
}

.kpi-label {
  font-size: 14px;
  color: #909399;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.charts-row {
  margin-top: 20px;
}
</style>
