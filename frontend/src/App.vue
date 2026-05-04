<template>
  <el-container class="app-container">
    <el-aside :width="isCollapsed ? '64px' : '240px'" class="app-aside">
      <div class="logo">
        <el-icon size="28" color="#fff"><DataBoard /></el-icon>
        <span v-if="!isCollapsed" class="logo-text">海贝海</span>
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
            <el-icon><DataBoard /></el-icon>
            <template #title>指挥塔</template>
          </el-menu-item>
          
          <el-sub-menu index="products-group">
            <template #title>
              <el-icon><Goods /></el-icon>
              <span>商品运营</span>
            </template>
            <el-menu-item index="/products">商品列表</el-menu-item>
            <el-menu-item index="/product-ranking">商品排行</el-menu-item>
            <el-menu-item index="/quadrant">四象限分析</el-menu-item>
            <el-menu-item index="/lifecycle">生命周期</el-menu-item>
            <el-menu-item index="/compare">商品对比</el-menu-item>
          </el-sub-menu>
          
          <el-sub-menu index="analysis-group">
            <template #title>
              <el-icon><TrendCharts /></el-icon>
              <span>数据分析</span>
            </template>
            <el-menu-item index="/trends">趋势分析</el-menu-item>
            <el-menu-item index="/traffic-analysis">流量分析</el-menu-item>
            <el-menu-item index="/funnel">转化漏斗</el-menu-item>
            <el-menu-item index="/ads">广告投放</el-menu-item>
            <el-menu-item index="/profit">利润分析</el-menu-item>
            <el-menu-item index="/kpi">KPI管理</el-menu-item>
            <el-menu-item index="/reviews">评价分析</el-menu-item>
            <el-menu-item index="/data-visualization">数据可视化</el-menu-item>
          </el-sub-menu>
          
          <el-sub-menu index="operation-group">
            <template #title>
              <el-icon><Monitor /></el-icon>
              <span>运营管理</span>
            </template>
            <el-menu-item index="/inventory">库存预警</el-menu-item>
            <el-menu-item index="/targets">目标管理</el-menu-item>
            <el-menu-item index="/promotion">促销活动</el-menu-item>
            <el-menu-item index="/promotion-analysis">促销分析</el-menu-item>
            <el-menu-item index="/operations">运营动作</el-menu-item>
            <el-menu-item index="/health">健康分析</el-menu-item>
            <el-menu-item index="/efficiency">效率分析</el-menu-item>
            <el-menu-item index="/attribution">归因分析</el-menu-item>
            <el-menu-item index="/refunds">退款分析</el-menu-item>
            <el-menu-item index="/crowd-asset">人群资产</el-menu-item>
            <el-menu-item index="/market">市场分析</el-menu-item>
            <el-menu-item index="/channel-detail">渠道详情</el-menu-item>
          </el-sub-menu>
          
          <el-sub-menu index="smart-group">
            <template #title>
              <el-icon><Tools /></el-icon>
              <span>智能工具</span>
            </template>
            <el-menu-item index="/ai-analytics">AI智能分析</el-menu-item>
            <el-menu-item index="/prediction">预测分析</el-menu-item>
            <el-menu-item index="/recommendation">智能推荐</el-menu-item>
            <el-menu-item index="/smart-alert">智能预警</el-menu-item>
          </el-sub-menu>
          
          <el-sub-menu index="tool-group">
            <template #title>
              <el-icon><DataAnalysis /></el-icon>
              <span>系统工具</span>
            </template>
            <el-menu-item index="/import-center">数据导入</el-menu-item>
            <el-menu-item index="/smart-import">智能导入</el-menu-item>
            <el-menu-item index="/advanced-import-center">高级导入</el-menu-item>
            <el-menu-item index="/import">简易导入</el-menu-item>
            <el-menu-item index="/toolbox">工具箱</el-menu-item>
            <el-menu-item index="/data-quality">数据质量</el-menu-item>
            <el-menu-item index="/backup-management">备份管理</el-menu-item>
            <el-menu-item index="/backup">备份</el-menu-item>
            <el-menu-item index="/settings">系统设置</el-menu-item>
          </el-sub-menu>
          
          <el-menu-item index="/report">
            <el-icon><DataLine /></el-icon>
            <template #title>报告生成</template>
          </el-menu-item>
          
          <el-menu-item index="/pace">
            <el-icon><Trophy /></el-icon>
            <template #title>目标进度</template>
          </el-menu-item>
          
          <el-menu-item index="/abtest-sop">
            <el-icon><User /></el-icon>
            <template #title>AB测试</template>
          </el-menu-item>
          
          <el-menu-item index="/collaboration">
            <el-icon><Money /></el-icon>
            <template #title>协作管理</template>
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
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { 
  DataBoard, DataLine, Goods, Monitor,
  TrendCharts, Trophy, Expand, Fold, Sunny, Moon,
  FullScreen, Tools, DataAnalysis, User, Money
} from '@element-plus/icons-vue'

const route = useRoute()
const isCollapsed = ref(false)
const isDark = ref(false)

const activeMenu = computed(() => route.path)

const pageTitle = computed(() => {
  const titles = {
    '/': '指挥塔',
    '/products': '商品列表',
    '/product': '商品详情',
    '/product-ranking': '商品排行',
    '/quadrant': '四象限分析',
    '/lifecycle': '生命周期',
    '/compare': '商品对比',
    '/inventory': '库存预警',
    '/reviews': '评价分析',
    '/traffic-analysis': '流量分析',
    '/funnel': '转化漏斗',
    '/ads': '广告投放',
    '/profit': '利润分析',
    '/kpi': 'KPI管理',
    '/trends': '趋势分析',
    '/data-visualization': '数据可视化',
    '/targets': '目标管理',
    '/promotion': '促销活动',
    '/promotion-analysis': '促销分析',
    '/operations': '运营动作',
    '/health': '健康分析',
    '/efficiency': '效率分析',
    '/attribution': '归因分析',
    '/refunds': '退款分析',
    '/crowd-asset': '人群资产',
    '/market': '市场分析',
    '/channel-detail': '渠道详情',
    '/ai-analytics': 'AI智能分析',
    '/prediction': '预测分析',
    '/recommendation': '智能推荐',
    '/smart-alert': '智能预警',
    '/import-center': '数据导入',
    '/smart-import': '智能导入',
    '/advanced-import-center': '高级导入',
    '/import': '简易导入',
    '/toolbox': '工具箱',
    '/data-quality': '数据质量',
    '/backup-management': '备份管理',
    '/backup': '备份',
    '/settings': '系统设置',
    '/report': '报告生成',
    '/pace': '目标进度',
    '/abtest-sop': 'AB测试',
    '/collaboration': '协作管理'
  }
  return titles[route.path] || '运营系统'
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
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-weight: bold;
  font-size: 18px;
}

.logo-text {
  white-space: nowrap;
  overflow: hidden;
}

.menu-scrollbar {
  height: calc(100vh - 64px);
}

.menu-scrollbar :deep(.el-scrollbar__view) {
  height: 100%;
}

.el-menu {
  border-right: none;
}

.el-menu-item,
.el-sub-menu__title {
  height: 48px;
  line-height: 48px;
  margin: 2px 8px;
  border-radius: 8px;
}

.el-menu-item:hover,
.el-sub-menu__title:hover {
  background-color: rgba(255, 255, 255, 0.08) !important;
}

.el-menu-item.is-active {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.3) 0%, rgba(118, 75, 162, 0.3) 100%) !important;
}

.app-header {
  background: white;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  height: 64px;
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
  font-size: 20px;
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
  padding: 20px;
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
