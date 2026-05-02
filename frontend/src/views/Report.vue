<template>
  <div class="report-page">
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-icon><Document /></el-icon>
            <span>自动化报告</span>
          </div>
          <div class="header-actions">
            <el-select v-model="reportType" @change="loadReport" style="width: 140px; margin-right: 12px">
              <el-option label="周度报告" value="weekly" />
              <el-option label="月度报告" value="monthly" />
              <el-option label="健康度报告" value="health" />
              <el-option label="告警汇总" value="alerts" />
            </el-select>
            <el-button type="primary" @click="loadReport">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
            <el-button type="success" @click="exportReport">
              <el-icon><Download /></el-icon>
              导出
            </el-button>
          </div>
        </div>
      </template>

      <div v-loading="loading" class="report-content">
        <div v-if="reportType === 'weekly'" class="weekly-report">
          <el-row :gutter="20" class="kpi-row">
            <el-col :span="6">
              <el-card class="kpi-card">
                <div class="kpi-value primary">¥{{ formatNumber(reportData?.summary?.total_gmv) }}</div>
                <div class="kpi-label">总 GMV</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="kpi-card">
                <div class="kpi-value">{{ formatNumber(reportData?.summary?.total_visitors) }}</div>
                <div class="kpi-label">访客数</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="kpi-card">
                <div class="kpi-value success">{{ reportData?.summary?.avg_conversion }}%</div>
                <div class="kpi-label">平均转化率</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="kpi-card">
                <div class="kpi-value warning">{{ reportData?.summary?.avg_roi }}</div>
                <div class="kpi-label">平均 ROI</div>
              </el-card>
            </el-col>
          </el-row>

          <el-card class="detail-card">
            <template #header>
              <span>周度核心指标</span>
            </template>
            <el-descriptions :column="3" border>
              <el-descriptions-item label="净销售额">¥{{ formatNumber(reportData?.summary?.net_sales) }}</el-descriptions-item>
              <el-descriptions-item label="退款金额">¥{{ formatNumber(reportData?.summary?.total_refund) }}</el-descriptions-item>
              <el-descriptions-item label="广告支出">¥{{ formatNumber(reportData?.summary?.total_ad_spend) }}</el-descriptions-item>
              <el-descriptions-item label="广告占比">{{ reportData?.summary?.ad_ratio }}%</el-descriptions-item>
              <el-descriptions-item label="统计商品数">{{ reportData?.summary?.product_count }}</el-descriptions-item>
              <el-descriptions-item label="报告周期">{{ reportData?.period }}</el-descriptions-item>
            </el-descriptions>
          </el-card>

          <el-card class="top-products-card">
            <template #header>
              <span>TOP 10 热销商品</span>
            </template>
            <el-table :data="reportData?.top_products || []" stripe>
              <el-table-column type="index" label="排名" width="60" align="center" />
              <el-table-column prop="title" label="商品名称" min-width="200" show-overflow-tooltip />
              <el-table-column prop="gmv" label="GMV" width="120" align="right">
                <template #default="{ row }">¥{{ formatNumber(row.gmv) }}</template>
              </el-table-column>
              <el-table-column prop="visitors" label="访客" width="100" align="right">
                <template #default="{ row }">{{ formatNumber(row.visitors) }}</template>
              </el-table-column>
              <el-table-column prop="conversion" label="转化率" width="100" align="center">
                <template #default="{ row }">{{ row.conversion }}%</template>
              </el-table-column>
              <el-table-column prop="roi" label="ROI" width="80" align="center" />
            </el-table>
          </el-card>
        </div>

        <div v-else-if="reportType === 'monthly'" class="monthly-report">
          <el-row :gutter="20" class="kpi-row">
            <el-col :span="4">
              <el-card class="kpi-card">
                <div class="kpi-value primary">¥{{ formatNumber(reportData?.summary?.total_gmv) }}</div>
                <div class="kpi-label">月 GMV</div>
              </el-card>
            </el-col>
            <el-col :span="4">
              <el-card class="kpi-card">
                <div class="kpi-value">{{ formatNumber(reportData?.summary?.total_visitors) }}</div>
                <div class="kpi-label">访客数</div>
              </el-card>
            </el-col>
            <el-col :span="4">
              <el-card class="kpi-card">
                <div class="kpi-value">{{ formatNumber(reportData?.summary?.total_buyers) }}</div>
                <div class="kpi-label">支付人数</div>
              </el-card>
            </el-col>
            <el-col :span="4">
              <el-card class="kpi-card">
                <div class="kpi-value">¥{{ formatNumber(reportData?.summary?.avg_order_value) }}</div>
                <div class="kpi-label">客单价</div>
              </el-card>
            </el-col>
            <el-col :span="4">
              <el-card class="kpi-card">
                <div class="kpi-value warning">{{ reportData?.summary?.avg_roi }}</div>
                <div class="kpi-label">平均 ROI</div>
              </el-card>
            </el-col>
            <el-col :span="4">
              <el-card class="kpi-card">
                <div class="kpi-value success">{{ reportData?.summary?.avg_conversion }}%</div>
                <div class="kpi-label">转化率</div>
              </el-card>
            </el-col>
          </el-row>

          <el-row :gutter="20" style="margin-top: 20px">
            <el-col :span="12">
              <el-card>
                <template #header>
                  <span>推广费用构成</span>
                </template>
                <el-descriptions :column="2" border>
                  <el-descriptions-item label="关键词推广">¥{{ formatNumber(reportData?.summary?.keyword_spend) }}</el-descriptions-item>
                  <el-descriptions-item label="人群推广">¥{{ formatNumber(reportData?.summary?.crowd_spend) }}</el-descriptions-item>
                  <el-descriptions-item label="站外推广">¥{{ formatNumber(reportData?.summary?.site_spend) }}</el-descriptions-item>
                  <el-descriptions-item label="总推广费用">¥{{ formatNumber(reportData?.summary?.total_ad_spend) }}</el-descriptions-item>
                </el-descriptions>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card>
                <template #header>
                  <span>类目销售排行</span>
                </template>
                <el-table :data="reportData?.category_breakdown || []" stripe size="small">
                  <el-table-column type="index" label="#" width="50" align="center" />
                  <el-table-column prop="category" label="类目" min-width="150" />
                  <el-table-column prop="gmv" label="GMV" width="120" align="right">
                    <template #default="{ row }">¥{{ formatNumber(row.gmv) }}</template>
                  </el-table-column>
                  <el-table-column prop="product_count" label="商品数" width="80" align="center" />
                </el-table>
              </el-card>
            </el-col>
          </el-row>
        </div>

        <div v-else-if="reportType === 'health'" class="health-report">
          <el-row :gutter="20" class="kpi-row">
            <el-col :span="6">
              <el-card class="kpi-card">
                <div class="kpi-value success">{{ reportData?.summary?.excellent || 0 }}</div>
                <div class="kpi-label">优秀</div>
                <div class="kpi-sub">健康分 80-100</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="kpi-card">
                <div class="kpi-value primary">{{ reportData?.summary?.good || 0 }}</div>
                <div class="kpi-label">良好</div>
                <div class="kpi-sub">健康分 60-80</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="kpi-card">
                <div class="kpi-value warning">{{ reportData?.summary?.warning || 0 }}</div>
                <div class="kpi-label">预警</div>
                <div class="kpi-sub">健康分 40-60</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="kpi-card">
                <div class="kpi-value danger">{{ reportData?.summary?.critical || 0 }}</div>
                <div class="kpi-label">危险</div>
                <div class="kpi-sub">健康分 0-40</div>
              </el-card>
            </el-col>
          </el-row>

          <el-row :gutter="20" style="margin-top: 20px">
            <el-col :span="24">
              <el-card>
                <template #header>
                  <span>健康度预警商品</span>
                </template>
                <el-table :data="reportData?.products || []" stripe>
                  <el-table-column prop="title" label="商品" min-width="200" show-overflow-tooltip />
                  <el-table-column prop="health_score" label="健康分" width="100" align="center">
                    <template #default="{ row }">
                      <el-tag :type="getScoreType(row.health_score)">{{ row.health_score }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="health_level" label="等级" width="80" align="center">
                    <template #default="{ row }">
                      <el-tag :type="getLevelType(row.health_level)">{{ getLevelText(row.health_level) }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="alert_dimensions" label="问题指标" min-width="200" />
                </el-table>
              </el-card>
            </el-col>
          </el-row>
        </div>

        <div v-else-if="reportType === 'alerts'" class="alerts-report">
          <el-row :gutter="20" class="kpi-row">
            <el-col :span="6">
              <el-card class="kpi-card">
                <div class="kpi-value primary">{{ reportData?.summary?.total_alerts || 0 }}</div>
                <div class="kpi-label">总告警数</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="kpi-card">
                <div class="kpi-value danger">{{ reportData?.summary?.critical_count || 0 }}</div>
                <div class="kpi-label">严重告警</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="kpi-card">
                <div class="kpi-value warning">{{ reportData?.summary?.warning_count || 0 }}</div>
                <div class="kpi-label">警告</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="kpi-card">
                <div class="kpi-value success">{{ reportData?.summary?.resolved_count || 0 }}</div>
                <div class="kpi-label">已处理</div>
              </el-card>
            </el-col>
          </el-row>

          <el-card style="margin-top: 20px">
            <template #header>
              <span>最近告警</span>
            </template>
            <el-table :data="reportData?.recent_alerts || []" stripe>
              <el-table-column prop="created_at" label="时间" width="160">
                <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
              </el-table-column>
              <el-table-column prop="title" label="告警标题" min-width="150" />
              <el-table-column prop="product_title" label="商品" min-width="150" show-overflow-tooltip />
              <el-table-column prop="severity" label="级别" width="80" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.severity === 'critical' ? 'danger' : 'warning'">
                    {{ row.severity === 'critical' ? '严重' : '警告' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="detail" label="详情" min-width="200" show-overflow-tooltip />
            </el-table>
          </el-card>
        </div>

        <div class="report-footer">
          <span class="generated-time">
            报告生成时间：{{ reportData?.generated_at ? new Date(reportData.generated_at).toLocaleString('zh-CN') : '-' }}
          </span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

const reportType = ref('weekly')
const loading = ref(false)
const reportData = ref(null)

const loadReport = async () => {
  loading.value = true
  try {
    let res
    switch (reportType.value) {
      case 'weekly':
        res = await api.getWeeklyReport()
        break
      case 'monthly':
        res = await api.getMonthlyReport()
        break
      case 'health':
        res = await api.getHealthReport()
        break
      case 'alerts':
        res = await api.getAlertSummary(7)
        break
    }
    reportData.value = res.data
  } catch (error) {
    console.error('Load report error:', error)
    ElMessage.error('加载报告失败')
  } finally {
    loading.value = false
  }
}

const exportReport = async () => {
  try {
    const res = await api.exportReportJson(reportType.value)
    const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${reportType.value}_report_${new Date().toISOString().slice(0, 10)}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (error) {
    console.error('Export error:', error)
    ElMessage.error('导出失败')
  }
}

const formatNumber = (value) => {
  if (!value && value !== 0) return '-'
  return Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

const formatTime = (time) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const getScoreType = (score) => {
  if (score >= 80) return 'success'
  if (score >= 60) return 'primary'
  if (score >= 40) return 'warning'
  return 'danger'
}

const getLevelType = (level) => {
  const types = { excellent: 'success', good: 'primary', warning: 'warning', critical: 'danger' }
  return types[level] || 'info'
}

const getLevelText = (level) => {
  const texts = { excellent: '优秀', good: '良好', warning: '预警', critical: '危险' }
  return texts[level] || level
}

onMounted(() => {
  loadReport()
})
</script>

<style scoped>
.report-page {
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

.header-actions {
  display: flex;
  align-items: center;
}

.report-content {
  min-height: 400px;
}

.kpi-row {
  margin-bottom: 20px;
}

.kpi-card {
  text-align: center;
}

.kpi-value {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 8px;
}

.kpi-value.primary {
  color: #409eff;
}

.kpi-value.success {
  color: #67c23a;
}

.kpi-value.warning {
  color: #e6a23c;
}

.kpi-value.danger {
  color: #f56c6c;
}

.kpi-label {
  font-size: 14px;
  color: #909399;
}

.kpi-sub {
  font-size: 12px;
  color: #c0c4cc;
  margin-top: 4px;
}

.detail-card,
.top-products-card {
  margin-bottom: 20px;
}

.report-footer {
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid #ebeef5;
  text-align: right;
}

.generated-time {
  font-size: 12px;
  color: #909399;
}
</style>
