<template>
  <div class="data-goals-center">
    <el-card class="header-card" shadow="never">
      <div class="header-content">
        <div class="left-section">
          <h1 class="page-title">📊 数据与目标指挥中心</h1>
          <p class="page-subtitle">一站式数据管理与目标追踪</p>
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
      <el-tab-pane name="overview" label="数据概览">
        <div class="tab-content">
          <DashboardComponent />
        </div>
      </el-tab-pane>

      <el-tab-pane name="products" label="商品分析">
        <div class="tab-content">
          <el-row :gutter="16">
            <el-col :span="24">
              <el-card shadow="never">
                <template #header>
                  <div class="card-header">
                    <span>商品分析</span>
                    <el-button type="primary" link @click="goToProducts">详细分析</el-button>
                  </div>
                </template>
                <ProductsPreview />
              </el-card>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>

      <el-tab-pane name="traffic" label="流量分析">
        <div class="tab-content">
          <el-card shadow="never">
            <template #header>
              <div class="card-header">
                <span>流量分析</span>
                <el-button type="primary" link @click="goToTraffic">详细分析</el-button>
              </div>
            </template>
            <TrafficPreview />
          </el-card>
        </div>
      </el-tab-pane>

      <el-tab-pane name="promotion" label="推广分析">
        <div class="tab-content">
          <el-card shadow="never">
            <template #header>
              <div class="card-header">
                <span>推广分析</span>
                <el-button type="primary" link @click="goToPromotion">详细分析</el-button>
              </div>
            </template>
            <PromotionPreview />
          </el-card>
        </div>
      </el-tab-pane>

      <el-tab-pane name="kpi" label="利润与KPI">
        <div class="tab-content">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-card shadow="never">
                <template #header>
                  <div class="card-header">
                    <span>KPI分析</span>
                    <el-button type="primary" link @click="goToKPI">详细分析</el-button>
                  </div>
                </template>
                <KpiPreview />
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card shadow="never">
                <template #header>
                  <div class="card-header">
                    <span>利润分析</span>
                    <el-button type="primary" link @click="goToProfit">详细分析</el-button>
                  </div>
                </template>
                <ProfitPreview />
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
import DashboardComponent from './Dashboard.vue'

const router = useRouter()
const activeTab = ref('overview')

const refreshAll = () => {
  ElMessage.success('正在刷新所有数据...')
  window.location.reload()
}

const goToProducts = () => {
  router.push('/products')
}

const goToTraffic = () => {
  router.push('/traffic-analysis')
}

const goToPromotion = () => {
  router.push('/promotion')
}

const goToKPI = () => {
  router.push('/kpi')
}

const goToProfit = () => {
  router.push('/profit')
}

const ProductsPreview = {
  template: '<div style="padding: 40px 20px; text-align: center; color: #909399;">商品分析预览 - 包含商品列表、排行榜、四象限分析</div>'
}

const TrafficPreview = {
  template: '<div style="padding: 40px 20px; text-align: center; color: #909399;">流量分析预览 - 包含流量来源、关键词、转化分析</div>'
}

const PromotionPreview = {
  template: '<div style="padding: 40px 20px; text-align: center; color: #909399;">推广分析预览 - 包含多渠道、直通车、引力魔方等</div>'
}

const KpiPreview = {
  template: '<div style="padding: 40px 0; text-align: center; color: #909399;">KPI分析预览图表</div>'
}

const ProfitPreview = {
  template: '<div style="padding: 40px 0; text-align: center; color: #909399;">利润分析预览图表</div>'
}

onMounted(() => {
  console.log('数据与目标指挥中心已加载')
})
</script>

<style scoped>
.data-goals-center {
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
</style>
