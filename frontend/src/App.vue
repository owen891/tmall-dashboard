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
            <el-icon><Trophy /></el-icon>
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
          
          <el-divider></el-divider>
          
          <el-menu-item index="/products">
            <el-icon><Goods /></el-icon>
            <template #title>商品列表</template>
          </el-menu-item>
          
          <el-menu-item index="/settings">
            <el-icon><Tools /></el-icon>
            <template #title>系统设置</template>
          </el-menu-item>
        </el-menu>
      </el-scrollbar>
    </el-aside>
    
    <el-container>
      <el-header class="app-header">
        <div class="header-left">
          <el-button 
            link 
            @click="toggleSidebar"
            class="toggle-btn"
          >
            <el-icon size="20"><Expand v-if="isCollapsed" /><Fold v-else /></el-icon>
          </el-button>
          <h2 class="page-title">{{ pageTitle }}</h2>
        </div>
        <div class="header-right">
          <GlobalTimeFilter />
          <el-button 
            link 
            @click="toggleTheme"
            class="theme-btn"
          >
            <el-icon size="20"><Sunny v-if="isDark" /><Moon /></el-icon>
          </el-button>
          <el-button 
            link 
            @click="handleFullScreen"
            class="fullscreen-btn"
          >
            <el-icon size="20"><FullScreen /></el-icon>
          </el-button>
        </div>
      </el-header>
      
      <el-main class="app-main">
        <router-view v-slot="{ Component }">
          <transition name="fade-slide" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { 
  DataBoard, DataLine, Odometer, Goods, Monitor, Setting,
  TrendCharts, Trophy, Expand, Fold, Sunny, Moon,
  FullScreen, Tools, DataAnalysis, User, ShoppingCart, 
  Coin, WarningFilled, Refresh, Upload, TrendCharts as TrendChartsIcon
} from '@element-plus/icons-vue'

const route = useRoute()
const isCollapsed = ref(false)
const isDark = ref(false)

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
    '/product-ranking': '商品排行榜',
    '/traffic-analysis': '流量分析',
    '/promotion-analysis': '推广效果分析',
    '/backup-management': '数据备份与恢复',
    '/advanced-import': '批量导入中心',
    '/data-visualization': '高级数据可视化',
    '/ai-analytics': 'AI智能分析',
    '/profit': '利润分析',
    '/inventory': '库存预警'
  }
  return titles[route.path] || '电商运营系统'
})

const toggleSidebar = () => {
  isCollapsed.value = !isCollapsed.value
}

const toggleTheme = () => {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
}

const handleFullScreen = () => {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen()
  } else {
    document.exitFullscreen()
  }
}

onMounted(() => {
  if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    isDark.value = true
    document.documentElement.classList.add('dark')
  }
})
</script>

<style scoped>
.app-container {
  height: 100vh;
}

.app-aside {
  background-color: #1f2329;
  transition: width 0.3s;
  overflow: hidden;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-weight: bold;
  font-size: 16px;
}

.logo-text {
  white-space: nowrap;
  overflow: hidden;
}

.menu-scrollbar {
  height: calc(100vh - 60px);
}

.menu-scrollbar :deep(.el-scrollbar__view) {
  height: 100%;
}

.el-menu {
  border-right: none;
}

.el-menu-item {
  height: 50px;
  line-height: 50px;
  margin: 4px 8px;
  border-radius: 8px;
}

.el-menu-item:hover {
  background-color: rgba(255, 255, 255, 0.08) !important;
}

.el-menu-item.is-active {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.3) 0%, rgba(118, 75, 162, 0.3) 100%) !important;
}

.el-divider {
  margin: 16px 16px;
  background-color: rgba(255, 255, 255, 0.1);
}

.app-header {
  background: white;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  height: 60px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.toggle-btn,
.theme-btn,
.fullscreen-btn {
  color: #606266;
}

.toggle-btn:hover,
.theme-btn:hover,
.fullscreen-btn:hover {
  color: #409eff;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.app-main {
  background-color: #f5f7fa;
  padding: 16px;
  overflow-y: auto;
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

:deep(.dark) {
  .app-aside {
    background-color: #141414;
  }
  
  .app-header {
    background-color: #1f1f1f;
    border-bottom-color: #333;
  }
  
  .page-title {
    color: #e0e0e0;
  }
  
  .toggle-btn,
  .theme-btn,
  .fullscreen-btn {
    color: #a0a0a0;
  }
  
  .app-main {
    background-color: #0a0a0a;
  }
}
</style>
