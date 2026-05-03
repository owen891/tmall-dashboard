<template>
  <div class="tools-system-center">
    <el-card class="header-card" shadow="never">
      <div class="header-content">
        <div class="left-section">
          <h1 class="page-title">🛠️ 工具与系统指挥中心</h1>
          <p class="page-subtitle">高级分析工具与系统管理</p>
        </div>
        <div class="right-section">
          <GlobalTimeFilter />
          <el-button type="primary" @click="refreshAll">
            <el-icon><Refresh /></el-icon>
            刷新全部
          </el-button>
        </div>
      </div>
    </el-card>

    <el-tabs v-model="activeTab" type="card" class="main-tabs">
      <el-tab-pane name="data" label="数据管理">
        <div class="tab-content">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-card shadow="never">
                <template #header>
                  <div class="card-header">
                    <span>数据导入</span>
                    <el-button type="primary" link @click="goToImportCenter">详细分析</el-button>
                  </div>
                </template>
                <div class="preview-content">
                  批量导入、增量导入、导入历史等
                </div>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card shadow="never">
                <template #header>
                  <div class="card-header">
                    <span>数据备份</span>
                    <el-button type="primary" link @click="goToBackup">详细分析</el-button>
                  </div>
                </template>
                <div class="preview-content">
                  备份管理、恢复、下载等
                </div>
              </el-card>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>

      <el-tab-pane name="analysis" label="分析工具">
        <div class="tab-content">
          <el-row :gutter="16">
            <el-col :span="8">
              <el-card shadow="never">
                <template #header>
                  <div class="card-header">
                    <span>漏斗分析</span>
                    <el-button type="primary" link @click="goToFunnel">详细分析</el-button>
                  </div>
                </template>
                <div class="preview-content">
                  转化漏斗、流失分析等
                </div>
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card shadow="never">
                <template #header>
                  <div class="card-header">
                    <span>异动归因</span>
                    <el-button type="primary" link @click="goToAttribution">详细分析</el-button>
                  </div>
                </template>
                <div class="preview-content">
                  异动分析、归因分析等
                </div>
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card shadow="never">
                <template #header>
                  <div class="card-header">
                    <span>预测分析</span>
                    <el-button type="primary" link @click="goToPrediction">详细分析</el-button>
                  </div>
                </template>
                <div class="preview-content">
                  销量预测、趋势预测等
                </div>
              </el-card>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>

      <el-tab-pane name="ai" label="AI智能">
        <div class="tab-content">
          <el-row :gutter="16">
            <el-col :span="8">
              <el-card shadow="never">
                <template #header>
                  <div class="card-header">
                    <span>智能选品</span>
                    <el-button type="primary" link @click="goToRecommendation">详细分析</el-button>
                  </div>
                </template>
                <div class="preview-content">
                  AI推荐、选品分析等
                </div>
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card shadow="never">
                <template #header>
                  <div class="card-header">
                    <span>自动报告</span>
                    <el-button type="primary" link @click="goToReport">详细分析</el-button>
                  </div>
                </template>
                <div class="preview-content">
                  自动生成、报告模板等
                </div>
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card shadow="never">
                <template #header>
                  <div class="card-header">
                    <span>数据质量</span>
                    <el-button type="primary" link @click="goToDataQuality">详细分析</el-button>
                  </div>
                </template>
                <div class="preview-content">
                  数据质量检测、异常修复等
                </div>
              </el-card>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>

      <el-tab-pane name="system" label="系统管理">
        <div class="tab-content">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-card shadow="never">
                <template #header>
                  <div class="card-header">
                    <span>系统设置</span>
                    <el-button type="primary" link @click="goToSettings">详细分析</el-button>
                  </div>
                </template>
                <div class="preview-content">
                  用户权限、系统配置等
                </div>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card shadow="never">
                <template #header>
                  <div class="card-header">
                    <span>可视化工具</span>
                    <el-button type="primary" link @click="goToVisualization">详细分析</el-button>
                  </div>
                </template>
                <div class="preview-content">
                  高级图表、AI智能分析等
                </div>
              </el-card>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import GlobalTimeFilter from '@/components/GlobalTimeFilter.vue'

const router = useRouter()
const activeTab = ref('data')

const refreshAll = () => {
  ElMessage.success('正在刷新所有数据...')
  window.location.reload()
}

const goToImportCenter = () => {
  router.push('/import-center')
}

const goToBackup = () => {
  router.push('/backup')
}

const goToFunnel = () => {
  router.push('/funnel')
}

const goToAttribution = () => {
  router.push('/attribution')
}

const goToPrediction = () => {
  router.push('/prediction')
}

const goToRecommendation = () => {
  router.push('/recommendation')
}

const goToReport = () => {
  router.push('/report')
}

const goToDataQuality = () => {
  router.push('/data-quality')
}

const goToSettings = () => {
  router.push('/settings')
}

const goToVisualization = () => {
  router.push('/data-visualization')
}

onMounted(() => {
  console.log('工具与系统指挥中心已加载')
})
</script>

<style scoped>
.tools-system-center {
  width: 100%;
}

.header-card {
  margin-bottom: 16px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.left-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: #303133;
}

.page-subtitle {
  margin: 0;
  font-size: 14px;
  color: #909399;
}

.right-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.main-tabs {
  background: #fff;
  border-radius: 8px;
}

.tab-content {
  padding: 20px 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.preview-content {
  padding: 40px 20px;
  text-align: center;
  color: #909399;
}
</style>
