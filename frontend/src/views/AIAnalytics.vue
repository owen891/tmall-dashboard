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
import { ref } from 'vue'
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

const activeTab = ref('report')
const generating = ref(false)
const querying = ref(false)
const queryText = ref('')
const queryResult = ref(null)

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

const currentReport = ref({
  title: '2026年5月1日运营日报',
  type: 'daily',
  time: '2026-05-01 23:59',
  metrics: {
    gmv: '¥35,556',
    gmvTrend: 12.5,
    visitors: '37,062',
    visitorsTrend: 8.3,
    conversion: '1.59%',
    conversionTrend: 3.2,
    roi: '3.87',
    roiTrend: 5.1
  },
  issues: [
    {
      level: 'high',
      title: '首页跳出率过高',
      description: '首页跳出率达到68%，高于行业平均水平50%，可能导致转化损失。'
    },
    {
      level: 'medium',
      title: '部分商品库存不足',
      description: '热销商品A库存仅剩50件，按当前销量预计3天后断货。'
    },
    {
      level: 'low',
      title: '直通车ROI略有下降',
      description: '直通车ROI从4.2下降到3.8，建议优化关键词出价。'
    }
  ],
  suggestions: [
    {
      title: '优化首页内容',
      priority: 'high',
      description: '建议在首页增加热销商品推荐模块，提高用户停留时间，预计可降低跳出率15%。'
    },
    {
      title: '及时补充库存',
      priority: 'high',
      description: '立即联系供应商补货，避免因断货导致的GMV损失。'
    },
    {
      title: '调整直通车策略',
      priority: 'medium',
      description: '优化关键词匹配方式，降低无效点击，预计可提升ROI 10%。'
    },
    {
      title: '加强客户评价管理',
      priority: 'medium',
      description: '近期有3条负面评价，建议主动联系客户解决问题，提升店铺评分。'
    }
  ]
})

const reportHistory = ref([
  { id: 1, title: '2026年4月30日运营日报', type: 'daily', time: '2026-04-30 23:59' },
  { id: 2, title: '2026年4月第四周周报', type: 'weekly', time: '2026-04-28 18:00' },
  { id: 3, title: '2026年4月29日运营日报', type: 'daily', time: '2026-04-29 23:59' }
])

const generateReport = async () => {
  generating.value = true
  
  await new Promise(resolve => setTimeout(resolve, 2000))
  
  ElMessage.success('报告生成成功')
  generating.value = false
}

const generateQuickReport = async (type) => {
  generating.value = true
  
  await new Promise(resolve => setTimeout(resolve, 1500))
  
  ElMessage.success(`${type === 'daily' ? '日报' : type === 'weekly' ? '周报' : type === 'product' ? '商品分析' : '流量分析'}生成成功`)
  generating.value = false
}

const executeQuery = async () => {
  if (!queryText.value) {
    ElMessage.warning('请输入查询内容')
    return
  }

  querying.value = true
  
  await new Promise(resolve => setTimeout(resolve, 2000))
  
  queryResult.value = {
    answer: `根据您的查询"${queryText.value}"，分析结果显示：上周销售额最高的商品是"中古风玄关装饰摆件"，销售额达到13,870元，占总销售额的3.9%。该商品转化率为1.12%，高于平均水平。`,
    data: [
      { rank: 1, product: '中古风玄关装饰摆件', gmv: 13870, conversion: '1.12%' },
      { rank: 2, product: '入户玄关装饰品钟馗财神爷摆件', gmv: 7090, conversion: '1.28%' },
      { rank: 3, product: '中古风玄关装饰摆件放钥匙收纳', gmv: 5731, conversion: '0.93%' }
    ],
    columns: ['rank', 'product', 'gmv', 'conversion']
  }
  
  querying.value = false
}

const applySuggestion = (suggestion) => {
  ElMessage.success(`已应用建议：${suggestion.title}`)
}

const exportReport = () => {
  ElMessage.info('导出功能开发中')
}

const shareReport = () => {
  ElMessage.info('分享功能开发中')
}

const loadReport = (reportId) => {
  ElMessage.info(`加载报告 ${reportId}`)
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
