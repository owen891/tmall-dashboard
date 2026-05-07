<template>
  <div class="report-container page-container">
    <div class="page-header">
      <h1>运营报告中心</h1>
      <div class="header-actions">
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon> 新建报告
        </el-button>
      </div>
    </div>

    <el-row :gutter="20" class="report-type-cards">
      <el-col :span="8">
        <div class="type-card daily" @click="generateReport('daily')">
          <div class="type-icon">
            <el-icon size="32"><Calendar /></el-icon>
          </div>
          <div class="type-info">
            <h3>日报</h3>
            <p>每日运营数据汇总</p>
            <el-button type="primary" size="small" :loading="generating === 'daily'">
              一键生成
            </el-button>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="type-card weekly" @click="generateReport('weekly')">
          <div class="type-icon">
            <el-icon size="32"><DataLine /></el-icon>
          </div>
          <div class="type-info">
            <h3>周报</h3>
            <p>本周运营数据回顾</p>
            <el-button type="success" size="small" :loading="generating === 'weekly'">
              一键生成
            </el-button>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="type-card monthly" @click="generateReport('monthly')">
          <div class="type-icon">
            <el-icon size="32"><TrendCharts /></el-icon>
          </div>
          <div class="type-info">
            <h3>月报</h3>
            <p>本月运营数据总结</p>
            <el-button type="warning" size="small" :loading="generating === 'monthly'">
              一键生成
            </el-button>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="section-title">
      <h2>历史报告</h2>
      <el-select v-model="filterType" size="default" style="width: 120px;">
        <el-option label="全部" value="all" />
        <el-option label="日报" value="daily" />
        <el-option label="周报" value="weekly" />
        <el-option label="月报" value="monthly" />
      </el-select>
    </div>

    <div v-loading="loading" class="report-list">
      <template v-if="reports.length > 0">
        <div v-for="report in filteredReports" :key="report.id" class="report-item">
          <div class="report-icon" :class="report.type">
            <el-icon size="24">
              <Calendar v-if="report.type === 'daily'" />
              <DataLine v-else-if="report.type === 'weekly'" />
              <TrendCharts v-else />
            </el-icon>
          </div>
          <div class="report-info">
            <h4>{{ report.title }}</h4>
            <p class="report-meta">
              <span class="type-tag">{{ getTypeName(report.type) }}</span>
              <span class="date">{{ report.date }}</span>
              <span class="author">创建人: {{ report.author }}</span>
            </p>
          </div>
          <div class="report-stats">
            <div class="stat">
              <span class="label">商品数</span>
              <span class="value">{{ report.product_count }}</span>
            </div>
            <div class="stat">
              <span class="label">GMV</span>
              <span class="value">¥{{ formatMoney(report.gmv) }}</span>
            </div>
            <div class="stat">
              <span class="label">订单数</span>
              <span class="value">{{ formatNumber(report.order_count) }}</span>
            </div>
          </div>
          <div class="report-actions">
            <el-button size="small" @click="previewReport(report)">
              <el-icon><View /></el-icon> 预览
            </el-button>
            <el-button size="small" type="success" @click="exportReport(report)">
              <el-icon><Download /></el-icon> 导出
            </el-button>
            <el-dropdown trigger="click">
              <el-button size="small">
                <el-icon><MoreFilled /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="shareReport(report)">分享</el-dropdown-item>
                  <el-dropdown-item @click="duplicateReport(report)">复制</el-dropdown-item>
                  <el-dropdown-item divided @click="deleteReport(report)">删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </template>
      <el-empty v-else description="暂无历史报告" />
    </div>

    <el-dialog v-model="previewVisible" title="报告预览" width="900px" :destroy-on-close="true">
      <div v-loading="previewLoading" class="preview-content">
        <div v-if="currentReport" class="report-preview markdown-body" v-html="currentReport.content"></div>
      </div>
      <template #footer>
        <el-button @click="previewVisible = false">关闭</el-button>
        <el-button type="primary" @click="exportReport(currentReport)">
          <el-icon><Download /></el-icon> 导出
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showCreateDialog" title="创建报告" width="500px">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="报告类型">
          <el-select v-model="createForm.type" style="width: 100%;">
            <el-option label="日报" value="daily" />
            <el-option label="周报" value="weekly" />
            <el-option label="月报" value="monthly" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="createForm.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 100%;"
          />
        </el-form-item>
        <el-form-item label="包含模块">
          <el-checkbox-group v-model="createForm.modules">
            <el-checkbox label="overview">核心指标概览</el-checkbox>
            <el-checkbox label="products">TOP商品分析</el-checkbox>
            <el-checkbox label="funnel">漏斗转化</el-checkbox>
            <el-checkbox label="comparison">同比环比</el-checkbox>
            <el-checkbox label="events">运营事件</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createReport">创建报告</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/api'
import { formatNumber } from '@/utils/format'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Calendar, DataLine, TrendCharts, Plus, View, Download,
  MoreFilled
} from '@element-plus/icons-vue'

const loading = ref(false)
const generating = ref(null)
const creating = ref(false)
const previewLoading = ref(false)
const showCreateDialog = ref(false)
const previewVisible = ref(false)

const filterType = ref('all')
const reports = ref([])
const currentReport = ref(null)

const createForm = ref({
  type: 'daily',
  dateRange: [],
  modules: ['overview', 'products', 'funnel']
})

const filteredReports = computed(() => {
  if (filterType.value === 'all') return reports.value
  return reports.value.filter(r => r.type === filterType.value)
})

const formatMoney = (money) => {
  if (money >= 100000000) return (money / 100000000).toFixed(1) + '亿'
  if (money >= 10000) return (money / 10000).toFixed(1) + '万'
  return money?.toLocaleString() || '0'
}

const getTypeName = (type) => {
  const names = { daily: '日报', weekly: '周报', monthly: '月报' }
  return names[type] || type
}

const generateReport = async (type) => {
  generating.value = type
  try {
    const data = await api.request.post(`/reports/${type}`)
    ElMessage.success(`${getTypeName(type)}生成成功`)
    await fetchReports()
    previewReport(data)
  } catch (e) {
    ElMessage.error(`生成报告失败: ${e.message || '未知错误'}`)
  } finally {
    generating.value = null
  }
}

const fetchReports = async () => {
  loading.value = true
  try {
    const data = await api.request.get('/reports/list')
    reports.value = data?.items || data || []
  } catch (e) {
    ElMessage.error('获取报告列表失败')
  } finally {
    loading.value = false
  }
}

const previewReport = async (report) => {
  previewVisible.value = true
  previewLoading.value = true
  try {
    const data = await api.request.get(`/reports/${report.id}`)
    currentReport.value = data
  } catch (e) {
    ElMessage.error('获取报告详情失败')
  } finally {
    previewLoading.value = false
  }
}

const exportReport = async (report) => {
  try {
    window.open(`/api/reports/export?id=${report.id}`, '_blank')
  } catch (e) {
    ElMessage.error('导出失败')
  }
}

const shareReport = (report) => {
  const url = `${window.location.origin}/report/${report.id}`
  try {
    navigator.clipboard.writeText(url)
    ElMessage.success('报告链接已复制到剪贴板')
  } catch (e) {
    ElMessage.error('复制失败，请手动复制')
  }
}

const duplicateReport = async (report) => {
  try {
    await api.request.post('/reports/duplicate', { id: report.id })
    ElMessage.success('报告已复制')
    fetchReports()
  } catch (e) {
    ElMessage.error('复制失败')
  }
}

const deleteReport = async (report) => {
  try {
    await ElMessageBox.confirm('确定要删除这份报告吗？', '删除确认', {
      type: 'warning'
    })
    await api.request.delete(`/reports/${report.id}`)
    ElMessage.success('报告已删除')
    fetchReports()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const createReport = async () => {
  creating.value = true
  try {
    await api.request.post('/reports/create', createForm.value)
    ElMessage.success('报告创建成功')
    showCreateDialog.value = false
    fetchReports()
  } catch (e) {
    ElMessage.error('创建失败')
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  fetchReports()
})
</script>

<style scoped>
.report-container {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.report-type-cards {
  margin-bottom: 32px;
}

.type-card {
  display: flex;
  align-items: center;
  gap: 20px;
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  cursor: pointer;
  transition: all 0.3s;
  border: 2px solid transparent;
}

.type-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
}

.type-card.daily { border-color: #409EFF; }
.type-card.weekly { border-color: #67C23A; }
.type-card.monthly { border-color: #E6A23C; }

.type-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.daily .type-icon { background: linear-gradient(135deg, #409EFF, #66B1FF); }
.weekly .type-icon { background: linear-gradient(135deg, #67C23A, #85CE61); }
.monthly .type-icon { background: linear-gradient(135deg, #E6A23C, #EBB564); }

.type-info h3 {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 8px 0;
}

.type-info p {
  font-size: 14px;
  color: #666;
  margin: 0 0 16px 0;
}

.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-title h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.report-list {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}

.report-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border-bottom: 1px solid #f0f0f0;
  transition: background 0.2s;
}

.report-item:last-child {
  border-bottom: none;
}

.report-item:hover {
  background: #fafafa;
}

.report-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.report-icon.daily { background: #409EFF; }
.report-icon.weekly { background: #67C23A; }
.report-icon.monthly { background: #E6A23C; }

.report-info {
  flex: 1;
}

.report-info h4 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 8px 0;
}

.report-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: #666;
  margin: 0;
}

.type-tag {
  padding: 2px 8px;
  border-radius: 4px;
  background: #f0f0f0;
  font-size: 12px;
}

.report-stats {
  display: flex;
  gap: 24px;
}

.report-stats .stat {
  text-align: center;
}

.report-stats .label {
  display: block;
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}

.report-stats .value {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.report-actions {
  display: flex;
  gap: 8px;
}

.preview-content {
  min-height: 400px;
}

.report-preview {
  padding: 20px;
  line-height: 1.8;
}

:deep(.report-preview h1) {
  font-size: 24px;
  border-bottom: 2px solid #409EFF;
  padding-bottom: 12px;
  margin-bottom: 20px;
}

:deep(.report-preview h2) {
  font-size: 18px;
  color: #409EFF;
  margin-top: 24px;
}

:deep(.report-preview table) {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
}

:deep(.report-preview th),
:deep(.report-preview td) {
  border: 1px solid #ddd;
  padding: 8px 12px;
  text-align: left;
}

:deep(.report-preview th) {
  background: #f5f5f5;
}
</style>
