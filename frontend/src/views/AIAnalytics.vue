<template>
  <div class="ai-analytics">
    <div class="page-header">
      <h1>AI智能分析</h1>
      <el-button type="primary" @click="generateReport">
        <el-icon><MagicStick /></el-icon>
        生成报告
      </el-button>
    </div>

    <el-row :gutter="20">
      <el-col :span="16">
        <div class="analysis-section">
          <el-tabs v-model="activeTab">
            <el-tab-pane label="智能报告" name="report">
              <div v-loading="generating" class="report-content">
                <div v-if="currentReport" class="report-card">
                  <div class="report-header">
                    <h2>{{ currentReport.title }}</h2>
                    <el-tag :type="currentReport.type === 'daily' ? 'primary' : 'success'" size="small">
                      {{ currentReport.type === 'daily' ? '日报' : '周报' }}
                    </el-tag>
                    <span class="report-time">{{ currentReport.time }}</span>
                  </div>
                  
                  <div class="report-section">
                    <h3>📊 核心指标概览</h3>
                    <el-row :gutter="20">
                      <el-col :span="6">
                        <div class="metric-card">
                          <div class="metric-label">销售额</div>
                          <div class="metric-value">{{ currentReport.metrics.gmv }}</div>
                          <div class="metric-change" :class="currentReport.metrics.gmvTrend >= 0 ? 'up' : 'down'">
                            {{ currentReport.metrics.gmvTrend >= 0 ? '↑' : '↓' }} {{ Math.abs(currentReport.metrics.gmvTrend) }}%
                          </div>
                        </div>
                      </el-col>
                      <el-col :span="6">
                        <div class="metric-card">
                          <div class="metric-label">访客数</div>
                          <div class="metric-value">{{ currentReport.metrics.visitors }}</div>
                          <div class="metric-change" :class="currentReport.metrics.visitorsTrend >= 0 ? 'up' : 'down'">
                            {{ currentReport.metrics.visitorsTrend >= 0 ? '↑' : '↓' }} {{ Math.abs(currentReport.metrics.visitorsTrend) }}%
                          </div>
                        </div>
                      </el-col>
                      <el-col :span="6">
                        <div class="metric-card">
                          <div class="metric-label">转化率</div>
                          <div class="metric-value">{{ currentReport.metrics.conversion }}</div>
                          <div class="metric-change" :class="currentReport.metrics.conversionTrend >= 0 ? 'up' : 'down'">
                            {{ currentReport.metrics.conversionTrend >= 0 ? '↑' : '↓' }} {{ Math.abs(currentReport.metrics.conversionTrend) }}%
                          </div>
                        </div>
                      </el-col>
                      <el-col :span="6">
                        <div class="metric-card">
                          <div class="metric-label">ROI</div>
                          <div class="metric-value">{{ currentReport.metrics.roi }}</div>
                          <div class="metric-change" :class="currentReport.metrics.roiTrend >= 0 ? 'up' : 'down'">
                            {{ currentReport.metrics.roiTrend >= 0 ? '↑' : '↓' }} {{ Math.abs(currentReport.metrics.roiTrend) }}%
                          </div>
                        </div>
                      </el-col>
                    </el-row>
                  </div>

                  <div class="report-section">
                    <h3>🔍 问题发现</h3>
                    <div class="issue-list">
                      <div v-for="(issue, index) in currentReport.issues" :key="index" class="issue-item" :class="issue.level">
                        <div class="issue-header">
                          <el-icon><Warning /></el-icon>
                          <span>{{ issue.title }}</span>
                          <el-tag :type="getIssueType(issue.level)" size="small">
                            {{ getIssueLevel(issue.level) }}
                          </el-tag>
                        </div>
                        <div class="issue-detail">{{ issue.description }}</div>
                      </div>
                    </div>
                  </div>

                  <div class="report-section">
                    <h3>💡 优化建议</h3>
                    <div class="suggestion-list">
                      <div v-for="(suggestion, index) in currentReport.suggestions" :key="index" class="suggestion-item">
                        <div class="suggestion-header">
                          <span class="suggestion-index">{{ index + 1 }}</span>
                          <span class="suggestion-title">{{ suggestion.title }}</span>
                          <el-tag :type="getSuggestionType(suggestion.priority)" size="small">
                            {{ getSuggestionPriority(suggestion.priority) }}
                          </el-tag>
                        </div>
                        <div class="suggestion-content">{{ suggestion.description }}</div>
                        <div class="suggestion-action">
                          <el-button size="small" type="primary" @click="applySuggestion(suggestion)">
                            应用建议
                          </el-button>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div class="report-actions">
                    <el-button @click="exportReport">
                      <el-icon><Download /></el-icon> 导出报告
                    </el-button>
                    <el-button @click="shareReport">
                      <el-icon><Share /></el-icon> 分享报告
                    </el-button>
                  </div>
                </div>
                <div v-else class="no-report">
                  <el-empty description="暂无报告">
                    <el-button type="primary" @click="generateReport">生成报告</el-button>
                  </el-empty>
                </div>
              </div>
            </el-tab-pane>

            <el-tab-pane label="自然语言查询" name="query">
              <div class="query-section">
                <div class="query-input">
                  <el-input
                    v-model="queryText"
                    type="textarea"
                    :rows="3"
                    placeholder="输入您的问题，例如：上周销售额最高的商品是什么？本月转化率趋势如何？"
                  />
                  <el-button type="primary" @click="executeQuery" :loading="querying">
                    <el-icon><Search /></el-icon> 查询
                  </el-button>
                </div>

                <div v-if="queryResult" class="query-result">
                  <div class="query-result-header">
                    <h3>查询结果</h3>
                    <el-tag type="success">AI分析</el-tag>
                  </div>
                  <div class="query-answer">{{ queryResult.answer }}</div>
                  <div v-if="queryResult.data" class="query-data">
                    <el-table :data="queryResult.data" size="small" max-height="300">
                      <el-table-column 
                        v-for="col in queryResult.columns" 
                        :key="col" 
                        :prop="col" 
                        :label="col" 
                      />
                    </el-table>
                  </div>
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </el-col>

      <el-col :span="8">
        <div class="quick-actions">
          <h3>快捷报告</h3>
          <div class="action-list">
            <div class="action-item" @click="generateQuickReport('daily')">
              <el-icon><Document /></el-icon>
              <span>日报</span>
            </div>
            <div class="action-item" @click="generateQuickReport('weekly')">
              <el-icon><Calendar /></el-icon>
              <span>周报</span>
            </div>
            <div class="action-item" @click="generateQuickReport('product')">
              <el-icon><Goods /></el-icon>
              <span>商品分析</span>
            </div>
            <div class="action-item" @click="generateQuickReport('traffic')">
              <el-icon><Connection /></el-icon>
              <span>流量分析</span>
            </div>
          </div>
        </div>

        <div class="report-history">
          <h3>历史报告</h3>
          <el-timeline>
            <el-timeline-item 
              v-for="report in reportHistory" 
              :key="report.id"
              :timestamp="report.time"
              placement="top"
            >
              <el-card size="small">
                <div class="history-item">
                  <span class="history-title">{{ report.title }}</span>
                  <el-tag :type="report.type === 'daily' ? 'primary' : 'success'" size="small">
                    {{ report.type === 'daily' ? '日报' : '周报' }}
                  </el-tag>
                </div>
                <el-button size="small" @click="loadReport(report.id)">查看</el-button>
              </el-card>
            </el-timeline-item>
          </el-timeline>
        </div>

        <div class="ai-settings">
          <h3>AI设置</h3>
          <el-form label-width="80px">
            <el-form-item label="模型">
              <el-select v-model="aiSettings.model" placeholder="选择AI模型">
                <el-option label="GPT-4" value="gpt-4" />
                <el-option label="GPT-3.5" value="gpt-3.5" />
              </el-select>
            </el-form-item>
            <el-form-item label="分析深度">
              <el-slider v-model="aiSettings.depth" :min="1" :max="5" :marks="depthMarks" />
            </el-form-item>
            <el-form-item label="自动报告">
              <el-switch v-model="aiSettings.autoReport" />
            </el-form-item>
          </el-form>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  MagicStick,
  Warning,
  Download,
  Share,
  Search,
  Document,
  Calendar,
  Goods,
  Connection
} from '@element-plus/icons-vue'
import api from '@/api'

const activeTab = ref('report')
const generating = ref(false)
const querying = ref(false)
const queryText = ref('')
const queryResult = ref(null)
const reportHistory = ref([])

const aiSettings = ref({
  model: 'gpt-4',
  depth: 3,
  autoReport: true
})

const depthMarks = {
  1: '简单',
  2: '基础',
  3: '标准',
  4: '详细',
  5: '深度'
}

const currentReport = ref(null)

const generateReport = async () => {
  generating.value = true
  try {
    const res = await api.aiAnalyticsApi.generateReport({ type: 'daily' })
    currentReport.value = res.data || res
    ElMessage.success('报告生成成功')
    await fetchHistory()
  } catch (error) {
    console.error('生成报告失败:', error)
    ElMessage.error('生成报告失败')
  } finally {
    generating.value = false
  }
}

const generateQuickReport = async (type) => {
  generating.value = true
  try {
    const reportType = type === 'daily' ? 'daily' : type === 'weekly' ? 'weekly' : type === 'product' ? 'product' : 'traffic'
    const res = await api.aiAnalyticsApi.generateReport({ type: reportType })
    currentReport.value = res.data || res
    const typeName = type === 'daily' ? '日报' : type === 'weekly' ? '周报' : type === 'product' ? '商品分析' : '流量分析'
    ElMessage.success(`${typeName}生成成功`)
    await fetchHistory()
  } catch (error) {
    console.error(`生成${typeName}失败:`, error)
    ElMessage.error('生成失败')
  } finally {
    generating.value = false
  }
}

const executeQuery = async () => {
  if (!queryText.value) {
    ElMessage.warning('请输入查询内容')
    return
  }

  querying.value = true
  try {
    const res = await api.aiAnalyticsApi.executeQuery({ query: queryText.value })
    queryResult.value = res.data || res
  } catch (error) {
    console.error('查询失败:', error)
    ElMessage.error('查询失败')
  } finally {
    querying.value = false
  }
}

const applySuggestion = (suggestion) => {
  ElMessage.success(`已应用建议：${suggestion.title}`)
}

const exportReport = async () => {
  try {
    window.open('/api/ai-analytics/report/export', '_blank')
    ElMessage.success('正在导出...')
  } catch (error) {
    ElMessage.error('导出失败')
  }
}

const shareReport = () => {
  const url = `${window.location.origin}/ai-report/${currentReport.value?.id}`
  try {
    navigator.clipboard.writeText(url)
    ElMessage.success('报告链接已复制')
  } catch (error) {
    ElMessage.error('复制失败')
  }
}

const loadReport = async (reportId) => {
  try {
    const res = await api.aiAnalyticsApi.getReport(reportId)
    currentReport.value = res.data || res
  } catch (error) {
    ElMessage.error('加载报告失败')
  }
}

const fetchHistory = async () => {
  try {
    const res = await api.aiAnalyticsApi.getReportHistory()
    reportHistory.value = res.data?.reports || res?.reports || []
  } catch (error) {
    console.error('获取历史报告失败:', error)
  }
}

const getIssueType = (level) => {
  const types = { high: 'danger', medium: 'warning', low: 'info' }
  return types[level] || 'info'
}

const getIssueLevel = (level) => {
  const levels = { high: '严重', medium: '中等', low: '轻微' }
  return levels[level] || level
}

const getSuggestionType = (priority) => {
  const types = { high: 'danger', medium: 'warning', low: 'info' }
  return types[priority] || 'info'
}

const getSuggestionPriority = (priority) => {
  const priorities = { high: '高优', medium: '中优', low: '低优' }
  return priorities[priority] || priority
}

onMounted(() => {
  fetchHistory()
})
</script>

<style scoped>
.ai-analytics {
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
  margin: 0;
}

.analysis-section, .quick-actions, .report-history, .ai-settings {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-bottom: 20px;
}

.analysis-section h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px 0;
}

.report-content {
  min-height: 400px;
}

.report-card {
  padding: 20px 0;
}

.report-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #eee;
}

.report-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.report-time {
  color: #999;
  font-size: 14px;
  margin-left: auto;
}

.report-section {
  margin-bottom: 32px;
}

.report-section h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px 0;
  color: #333;
}

.metric-card {
  background: #f5f7fa;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
}

.metric-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}

.metric-value {
  font-size: 24px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
}

.metric-change {
  font-size: 13px;
}

.metric-change.up {
  color: #67C23A;
}

.metric-change.down {
  color: #F56C6C;
}

.issue-list, .suggestion-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.issue-item {
  padding: 16px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #eee;
}

.issue-item.high {
  border-color: #F56C6C;
  background: #fef0f0;
}

.issue-item.medium {
  border-color: #E6A23C;
  background: #fdf6ec;
}

.issue-item.low {
  border-color: #909399;
  background: #f4f4f5;
}

.issue-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-weight: 500;
}

.issue-detail {
  color: #666;
  font-size: 14px;
}

.suggestion-item {
  padding: 16px;
  border-radius: 8px;
  background: #f5f7fa;
}

.suggestion-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.suggestion-index {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #409EFF;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
}

.suggestion-title {
  font-weight: 500;
  flex: 1;
}

.suggestion-content {
  color: #666;
  font-size: 14px;
  margin-bottom: 12px;
}

.report-actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid #eee;
}

.no-report {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
}

.query-section {
  padding: 20px 0;
}

.query-input {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.query-input .el-input {
  flex: 1;
}

.query-result {
  background: #f5f7fa;
  padding: 20px;
  border-radius: 8px;
}

.query-result-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.query-result-header h3 {
  margin: 0;
}

.query-answer {
  font-size: 15px;
  line-height: 1.8;
  color: #333;
  margin-bottom: 16px;
}

.quick-actions h3, .report-history h3, .ai-settings h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px 0;
}

.action-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.action-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
}

.action-item:hover {
  background: #409EFF;
  color: white;
}

.action-item .el-icon {
  font-size: 24px;
}

.history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.history-title {
  font-weight: 500;
}
</style>
