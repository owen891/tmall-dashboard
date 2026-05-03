<template>
  <el-container class="app-container">
    <el-aside :width="isCollapsed ? '64px' : '220px'" class="app-aside">
      <div class="logo">
        <el-icon size="24" color="#fff"><DataBoard /></el-icon>
        <span v-if="!isCollapsed" class="logo-text">六边形指挥塔</span>
      </div>
      
      <el-scrollbar class="menu-scrollbar">
        <el-menu
          :default-active="activeMenu"
          :collapse="isCollapsed"
          :collapse-transition="false"
          router
          background-color="#1f2329"
          text-color="#9da3af"
          active-text-color="#ffffff"
        >
          <el-menu-item index="/">
            <el-icon><DataLine /></el-icon>
            <template #title>指挥驾驶舱</template>
          </el-menu-item>
          
          <el-menu-item index="/data-goals">
            <el-icon><TrendCharts /></el-icon>
            <template #title>数据与目标</template>
          </el-menu-item>
          
          <el-menu-item index="/experiment-asset">
            <el-icon><DataLine /></el-icon>
            <template #title>实验与资产</template>
          </el-menu-item>
          
          <el-menu-item index="/execute-monitor">
            <el-icon><Monitor /></el-icon>
            <template #title>执行与监控</template>
          </el-menu-item>
          
          <el-menu-item index="/tools-system">
            <el-icon><Setting /></el-icon>
            <template #title>工具与系统</template>
          </el-menu-item>
          
          <el-menu-item index="/dashboard">
            <el-icon><Odometer /></el-icon>
            <template #title>数据概览</template>
          </el-menu-item>

          <el-sub-menu index="product">
            <template #title>
              <el-icon><Goods /></el-icon>
              <span>商品中心</span>
            </template>
            <el-menu-item index="/products">
              <span>商品列表</span>
            </el-menu-item>
            <el-menu-item index="/channel">
              <span>渠道分析</span>
            </el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="analysis">
            <template #title>
              <el-icon><DataAnalysis /></el-icon>
              <span>数据分析</span>
            </template>
            <el-menu-item index="/kpi">
              <span>KPI分析</span>
            </el-menu-item>
            <el-menu-item index="/profit">
              <span>利润分析</span>
            </el-menu-item>
            <el-menu-item index="/trends">
              <span>趋势分析</span>
            </el-menu-item>
            <el-menu-item index="/compare">
              <span>同比对比</span>
            </el-menu-item>
            <el-menu-item index="/quadrant">
              <span>四象限分析</span>
            </el-menu-item>
            <el-menu-item index="/ads">
              <span>广告投放</span>
            </el-menu-item>
            <el-menu-item index="/promotion">
              <span>多渠道推广</span>
            </el-menu-item>
            <el-menu-item index="/product-ranking">
              <span>商品排行榜</span>
            </el-menu-item>
            <el-menu-item index="/traffic-analysis">
              <span>流量分析</span>
            </el-menu-item>
            <el-menu-item index="/promotion-analysis">
              <span>推广效果分析</span>
            </el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="operations">
            <template #title>
              <el-icon><Monitor /></el-icon>
              <span>运营监控</span>
            </template>
            <el-menu-item index="/health">
              <span>健康度评分</span>
            </el-menu-item>
            <el-menu-item index="/inventory">
              <span>库存预警</span>
            </el-menu-item>
            <el-menu-item index="/operations">
              <span>操作统计</span>
            </el-menu-item>
            <el-menu-item index="/refunds">
              <span>退款分析</span>
            </el-menu-item>
            <el-menu-item index="/alerts">
              <span>异常告警</span>
            </el-menu-item>
            <el-menu-item index="/backup-management">
              <span>数据备份</span>
            </el-menu-item>
            <el-menu-item index="/advanced-import">
              <span>批量导入</span>
            </el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="visual">
            <template #title>
              <el-icon><DataBoard /></el-icon>
              <span>可视化工具</span>
            </template>
            <el-menu-item index="/data-visualization">
              <span>高级图表</span>
            </el-menu-item>
            <el-menu-item index="/ai-analytics">
              <span>AI智能分析</span>
            </el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="command">
            <template #title>
              <el-icon><Trophy /></el-icon>
              <span>六边形指挥塔</span>
            </template>
            <el-menu-item index="/crowd-asset">
              <span>人群资产归因</span>
            </el-menu-item>
            <el-menu-item index="/abtest-sop">
              <span>策略实验与SOP</span>
            </el-menu-item>
            <el-menu-item index="/efficiency">
              <span>人效精准度量</span>
            </el-menu-item>
            <el-menu-item index="/smart-alert">
              <span>智能告警中心</span>
            </el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="tools">
            <template #title>
              <el-icon><TrendCharts /></el-icon>
              <span>运营工具</span>
            </template>
            <el-menu-item index="/lifecycle">
              <span>生命周期</span>
            </el-menu-item>
            <el-menu-item index="/prediction">
              <span>预测分析</span>
            </el-menu-item>
            <el-menu-item index="/data-quality">
              <span>数据质量</span>
            </el-menu-item>
            <el-menu-item index="/reviews">
              <span>评价分析</span>
            </el-menu-item>
            <el-menu-item index="/market">
              <span>市场分析</span>
            </el-menu-item>
            <el-menu-item index="/targets">
              <span>目标管理</span>
            </el-menu-item>
            <el-menu-item index="/pace">
              <span>Pace 监控</span>
            </el-menu-item>
            <el-menu-item index="/attribution">
              <span>异动归因</span>
            </el-menu-item>
            <el-menu-item index="/funnel">
              <span>漏斗转化</span>
            </el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="smart">
            <template #title>
              <el-icon><MagicStick /></el-icon>
              <span>智能工具</span>
            </template>
            <el-menu-item index="/recommendation">
              <span>智能选品</span>
            </el-menu-item>
            <el-menu-item index="/report">
              <span>自动报告</span>
            </el-menu-item>
            <el-menu-item index="/toolbox">
              <span>运营工具箱</span>
            </el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="system">
            <template #title>
              <el-icon><Setting /></el-icon>
              <span>系统管理</span>
            </template>
            <el-menu-item index="/import">
              <el-icon><Upload /></el-icon>
              <span>数据导入</span>
            </el-menu-item>
            <el-menu-item index="/backup">
              <el-icon><FolderOpened /></el-icon>
              <span>数据备份</span>
            </el-menu-item>
            <el-menu-item index="/settings">
              <el-icon><Tools /></el-icon>
              <span>系统设置</span>
            </el-menu-item>
          </el-sub-menu>
        </el-menu>
      </el-scrollbar>
    </el-aside>

    <el-container class="main-container">
      <el-header class="app-header">
        <div class="header-left">
          <el-button 
            :icon="isCollapsed ? 'Expand' : 'Fold'" 
            @click="isCollapsed = !isCollapsed"
            text
            class="collapse-btn"
          />
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="pageTitle !== '数据概览'">{{ pageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="header-right">
          <GlobalTimeFilter />
          
          <el-button size="small" @click="handleRefresh">
            <el-icon><Refresh /></el-icon>
          </el-button>
          <el-button type="primary" size="small" @click="$router.push('/import-center')">
            <el-icon><Upload /></el-icon>
            <span>导入</span>
          </el-button>
        </div>
      </el-header>

      <el-main class="app-main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import GlobalTimeFilter from '@/components/GlobalTimeFilter.vue'

const route = useRoute()
const isCollapsed = ref(false)

const activeMenu = computed(() => route.path)

const pageTitle = computed(() => {
  const titles = {
    '/': '指挥驾驶舱',
    '/data-goals': '数据与目标',
    '/experiment-asset': '实验与资产',
    '/execute-monitor': '执行与监控',
    '/tools-system': '工具与系统',
    '/dashboard': '数据概览',
    '/products': '商品列表',
    '/product': '商品详情',
    '/channel': '渠道分析',
    '/import': '数据导入',
    '/import-center': '数据导入中心',
    '/quadrant': '四象限分析',
    '/kpi': 'KPI分析',
    '/trends': '趋势分析',
    '/ads': '广告投放',
    '/health': '健康度评分',
    '/operations': '操作统计',
    '/refunds': '退款分析',
    '/targets': '目标管理',
    '/alerts': '异常告警',
    '/reviews': '评价分析',
    '/market': '市场分析',
    '/toolbox': '运营工具箱',
    '/promotion': '多渠道推广',
    '/lifecycle': '生命周期',
    '/compare': '周期对比',
    '/recommendation': '智能选品',
    '/report': '自动报告',
    '/attribution': '异动归因',
    '/funnel': '漏斗转化',
    '/prediction': '预测分析',
    '/data-quality': '数据质量',
    '/settings': '系统设置',
    '/backup': '数据备份',
    '/crowd-asset': '人群资产归因',
    '/abtest-sop': '策略实验与SOP',
    '/efficiency': '人效精准度量',
    '/smart-alert': '智能告警中心',
    '/import-center': '数据导入中心',
    '/product-ranking': '商品排行榜',
    '/traffic-analysis': '流量分析',
    '/promotion-analysis': '推广效果分析',
    '/backup-management': '数据备份与恢复',
    '/advanced-import': '批量导入中心',
    '/data-visualization': '高级数据可视化',
    '/ai-analytics': 'AI智能分析'
  }
  
  const path = route.path
  if (path.startsWith('/product/')) return '商品详情'
  if (path.startsWith('/channel/')) return '渠道分析'
  return titles[path] || '数据概览'
})

const handleRefresh = () => {
  window.location.reload()
}

onMounted(() => {
  // 初始化
})
</script>

<style scoped>
.app-container {
  height: 100vh;
  overflow: hidden;
}

.app-aside {
  background-color: #1f2329;
  overflow: hidden;
  transition: width 0.3s;
  display: flex;
  flex-direction: column;
}

.logo {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 0 16px;
  background-color: #16181c;
  border-bottom: 1px solid #2a2d32;
}

.logo-text {
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
}

.menu-scrollbar {
  flex: 1;
  height: calc(100vh - 56px);
}

.menu-scrollbar :deep(.el-scrollbar__wrap) {
  overflow-x: hidden;
}

.el-menu {
  border-right: none;
}

.el-menu:not(.el-menu--collapse) {
  width: 220px;
}

.el-menu--collapse {
  width: 64px;
}

:deep(.el-menu-item),
:deep(.el-sub-menu__title) {
  height: 44px;
  line-height: 44px;
  margin: 2px 8px;
  border-radius: 6px;
}

:deep(.el-menu-item:hover),
:deep(.el-sub-menu__title:hover) {
  background-color: rgba(255, 255, 255, 0.08) !important;
}

:deep(.el-menu-item.is-active) {
  background-color: #409eff !important;
}

:deep(.el-sub-menu .el-menu-item) {
  padding-left: 20px !important;
  min-width: auto;
}

.main-container {
  display: flex;
  flex-direction: column;
}

.app-header {
  background-color: #fff;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  height: 56px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.collapse-btn {
  font-size: 18px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.date-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.app-main {
  background-color: #f5f7fa;
  padding: 16px 20px;
  overflow-y: auto;
  height: calc(100vh - 56px);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
