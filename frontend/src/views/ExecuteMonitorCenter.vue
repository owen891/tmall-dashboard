<template>
  <div class="execute-monitor-center">
    <el-card class="header-card" shadow="never">
      <div class="header-content">
        <div class="left-section">
          <h1 class="page-title">🎯 执行与监控指挥中心</h1>
          <p class="page-subtitle">实时监控与运营执行管理</p>
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

    <el-alert
      title="智能预警"
      type="warning"
      :closable="false"
      style="margin-bottom: 16px"
    >
      当前有 3 个重要预警需要处理
    </el-alert>

    <el-tabs v-model="activeTab" type="card" class="main-tabs">
      <el-tab-pane name="alert" label="智能预警">
        <div class="tab-content">
          <el-card shadow="never">
            <template #header>
              <div class="card-header">
                <span>预警中心</span>
                <el-button type="primary" link @click="goToSmartAlert">详细分析</el-button>
              </div>
            </template>
            <div class="preview-content">
              实时告警、历史告警、告警规则配置等
            </div>
          </el-card>
        </div>
      </el-tab-pane>

      <el-tab-pane name="efficiency" label="人效监控">
        <div class="tab-content">
          <el-card shadow="never">
            <template #header>
              <div class="card-header">
                <span>人效管理</span>
                <el-button type="primary" link @click="goToEfficiency">详细分析</el-button>
              </div>
            </template>
            <div class="preview-content">
              人效排行榜、任务看板、KPI追踪等
            </div>
          </el-card>
        </div>
      </el-tab-pane>

      <el-tab-pane name="operation" label="运营监控">
        <div class="tab-content">
          <el-card shadow="never">
            <template #header>
              <div class="card-header">
                <span>运营管理</span>
                <el-button type="primary" link @click="goToOperations">详细分析</el-button>
              </div>
            </template>
            <div class="preview-content">
              健康度、库存预警、退款分析、操作统计等
            </div>
          </el-card>
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
const activeTab = ref('alert')

const refreshAll = () => {
  ElMessage.success('正在刷新所有数据...')
  window.location.reload()
}

const goToSmartAlert = () => {
  router.push('/smart-alert')
}

const goToEfficiency = () => {
  router.push('/efficiency')
}

const goToOperations = () => {
  router.push('/operations')
}

onMounted(() => {
  console.log('执行与监控指挥中心已加载')
})
</script>

<style scoped>
.execute-monitor-center {
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
