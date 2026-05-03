<template>
  <div class="experiment-asset-center">
    <el-card class="header-card" shadow="never">
      <div class="header-content">
        <div class="left-section">
          <h1 class="page-title">🧪 实验与资产指挥中心</h1>
          <p class="page-subtitle">策略实验与人群资产管理</p>
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
      <el-tab-pane name="crowd" label="人群资产">
        <div class="tab-content">
          <el-card shadow="never">
            <template #header>
              <div class="card-header">
                <span>人群资产分析</span>
                <el-button type="primary" link @click="goToCrowdAsset">详细分析</el-button>
              </div>
            </template>
            <div class="preview-content">
              人群资产归因、AIPL分析、效率矩阵等
            </div>
          </el-card>
        </div>
      </el-tab-pane>

      <el-tab-pane name="experiment" label="策略实验">
        <div class="tab-content">
          <el-card shadow="never">
            <template #header>
              <div class="card-header">
                <span>A/B测试与实验</span>
                <el-button type="primary" link @click="goToABTest">详细分析</el-button>
              </div>
            </template>
            <div class="preview-content">
              A/B测试管理、实验结果分析、SOP库等
            </div>
          </el-card>
        </div>
      </el-tab-pane>

      <el-tab-pane name="activity" label="活动管理">
        <div class="tab-content">
          <el-card shadow="never">
            <template #header>
              <div class="card-header">
                <span>营销活动</span>
                <el-button type="primary" link @click="goToToolbox">详细分析</el-button>
              </div>
            </template>
            <div class="preview-content">
              活动全流程管理、SOP模板、复盘报告等
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
const activeTab = ref('crowd')

const refreshAll = () => {
  ElMessage.success('正在刷新所有数据...')
  window.location.reload()
}

const goToCrowdAsset = () => {
  router.push('/crowd-asset')
}

const goToABTest = () => {
  router.push('/abtest-sop')
}

const goToToolbox = () => {
  router.push('/toolbox')
}

onMounted(() => {
  console.log('实验与资产指挥中心已加载')
})
</script>

<style scoped>
.experiment-asset-center {
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
