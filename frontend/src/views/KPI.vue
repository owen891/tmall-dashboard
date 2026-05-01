<template>
  <div class="kpi-container">
    <div class="header">
      <h2>多维度KPI分析</h2>
      <div class="dimension-selector">
        <el-radio-group v-model="dimension" @change="loadKPI">
          <el-radio-button label="daily">日</el-radio-button>
          <el-radio-button label="weekly">周</el-radio-button>
          <el-radio-button label="monthly">月</el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <el-row :gutter="20" class="summary-cards">
      <el-col :span="6">
        <el-card class="kpi-card">
          <div class="kpi-value">{{ formatNumber(summary.gmv) }}</div>
          <div class="kpi-label">GMV</div>
          <div class="kpi-change" :class="summary.gmv_trend > 0 ? 'positive' : 'negative'">
            {{ summary.gmv_trend > 0 ? '↑' : '↓' }} {{ Math.abs(summary.gmv_trend).toFixed(1) }}%
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="kpi-card">
          <div class="kpi-value">{{ formatNumber(summary.visitors) }}</div>
          <div class="kpi-label">访客数</div>
          <div class="kpi-change" :class="summary.visitors_trend > 0 ? 'positive' : 'negative'">
            {{ summary.visitors_trend > 0 ? '↑' : '↓' }} {{ Math.abs(summary.visitors_trend).toFixed(1) }}%
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="kpi-card">
          <div class="kpi-value">{{ summary.conversion }}%</div>
          <div class="kpi-label">转化率</div>
          <div class="kpi-change" :class="summary.conversion_trend > 0 ? 'positive' : 'negative'">
            {{ summary.conversion_trend > 0 ? '↑' : '↓' }} {{ Math.abs(summary.conversion_trend).toFixed(1) }}%
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="kpi-card">
          <div class="kpi-value">{{ summary.roi }}</div>
          <div class="kpi-label">ROI</div>
          <div class="kpi-change" :class="summary.roi_trend > 0 ? 'positive' : 'negative'">
            {{ summary.roi_trend > 0 ? '↑' : '↓' }} {{ Math.abs(summary.roi_trend).toFixed(1) }}%
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="anomaly-card" v-if="anomalies.length > 0">
      <template #header>
        <div class="card-header">
          <span>异常告警</span>
          <el-badge :value="anomalies.length" type="danger" />
        </div>
      </template>
      <el-table :data="anomalies" stripe>
        <el-table-column prop="product_name" label="商品" />
        <el-table-column prop="metric" label="指标" />
        <el-table-column prop="current_value" label="当前值">
          <template #default="{ row }">
            {{ row.current_value.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="change_rate" label="变化率">
          <template #default="{ row }">
            <el-tag :type="row.change_rate > 0 ? 'danger' : 'warning'">
              {{ row.change_rate > 0 ? '+' : '' }}{{ row.change_rate.toFixed(1) }}%
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="severity" label="严重程度">
          <template #default="{ row }">
            <el-tag :type="row.severity === 'critical' ? 'danger' : 'warning'">
              {{ row.severity === 'critical' ? '严重' : '警告' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" @click="dismissAnomaly(row.id)">忽略</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="product-kpi-card">
      <template #header>
        <span>商品KPI排名</span>
      </template>
      <el-table :data="productKPIs" stripe>
        <el-table-column prop="product_name" label="商品名称" />
        <el-table-column prop="gmv" label="GMV">
          <template #default="{ row }">
            {{ formatNumber(row.gmv) }}
          </template>
        </el-table-column>
        <el-table-column prop="visitors" label="访客" />
        <el-table-column prop="conversion" label="转化率(%)" />
        <el-table-column prop="roi" label="ROI" />
        <el-table-column prop="ad_spend" label="广告花费">
          <template #default="{ row }">
            {{ formatNumber(row.ad_spend) }}
          </template>
        </el-table-column>
        <el-table-column prop="refund_rate" label="退款率(%)" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

const dimension = ref('weekly')
const summary = ref({
  gmv: 0,
  gmv_trend: 0,
  visitors: 0,
  visitors_trend: 0,
  conversion: 0,
  conversion_trend: 0,
  roi: 0,
  roi_trend: 0
})
const anomalies = ref([])
const productKPIs = ref([])

const loadKPI = async () => {
  try {
    const summaryRes = await api.getKPISummary(dimension.value)
    const kpi = summaryRes.data?.kpi || {}
    summary.value = {
      gmv: kpi.total_gmv?.value || 0,
      gmv_trend: kpi.total_gmv?.change?.percent || 0,
      visitors: kpi.visitors?.value || 0,
      visitors_trend: kpi.visitors?.change?.percent || 0,
      conversion: kpi.avg_conversion?.value || 0,
      conversion_trend: kpi.avg_conversion?.change?.percent || 0,
      roi: kpi.avg_roi?.value || 0,
      roi_trend: kpi.avg_roi?.change?.percent || 0
    }
    
    const anomaliesRes = await api.getKPIAnomalies()
    anomalies.value = anomaliesRes.data?.alerts || []
    
    const productsRes = await api.getProducts({ dim: dimension.value, limit: 10 })
    productKPIs.value = (productsRes.data?.data || []).map(p => ({
      product_name: p.title,
      gmv: p.payment_amount,
      visitors: p.visitors,
      conversion: (p.conversion * 100).toFixed(2),
      roi: p.roi?.toFixed(2) || '0',
      ad_spend: p.ad_spend,
      refund_rate: (p.refund_rate * 100).toFixed(2)
    }))
  } catch (error) {
    console.error('加载KPI失败:', error)
  }
}

const dismissAnomaly = async (id) => {
  try {
    await api.dismissAnomaly(id)
    ElMessage.success('已忽略')
    loadKPI()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const formatNumber = (num) => {
  if (!num) return '0'
  if (num >= 10000) {
    return (num / 10000).toFixed(2) + '万'
  }
  return num.toFixed ? num.toFixed(2) : num
}

onMounted(() => {
  loadKPI()
})
</script>

<style scoped>
.kpi-container {
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

.kpi-card {
  text-align: center;
}

.kpi-value {
  font-size: 28px;
  font-weight: bold;
  color: #409eff;
}

.kpi-label {
  font-size: 14px;
  color: #909399;
  margin: 8px 0;
}

.kpi-change {
  font-size: 14px;
}

.kpi-change.positive {
  color: #67c23a;
}

.kpi-change.negative {
  color: #f56c6c;
}

.summary-cards {
  margin-bottom: 20px;
}

.anomaly-card,
.product-kpi-card {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
