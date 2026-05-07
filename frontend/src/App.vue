<template>
  <el-container class="app-container">
    <el-aside :width="isCollapsed ? '64px' : '220px'" class="app-aside">
      <div class="logo">
        <el-icon size="24" color="#fff"><DataBoard /></el-icon>
        <span v-if="!isCollapsed" class="logo-text">运营系统</span>
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
          
          <el-sub-menu index="products">
            <template #title>
              <el-icon><Goods /></el-icon>
              <span>商品运营</span>
            </template>
            <el-menu-item index="/products">商品列表</el-menu-item>
            <el-menu-item index="/lifecycle">生命周期</el-menu-item>
            <el-menu-item index="/profit">利润分析</el-menu-item>
            <el-menu-item index="/product-ranking">商品排行</el-menu-item>
            <el-menu-item index="/quadrant">四象限分析</el-menu-item>
          </el-sub-menu>
          
          <el-sub-menu index="analysis">
            <template #title>
              <el-icon><TrendCharts /></el-icon>
              <span>数据分析</span>
            </template>
            <el-menu-item index="/traffic-analysis">流量分析</el-menu-item>
            <el-menu-item index="/ads">广告投放</el-menu-item>
            <el-menu-item index="/kpi">KPI管理</el-menu-item>
            <el-menu-item index="/trends">趋势分析</el-menu-item>
            <el-menu-item index="/funnel">转化漏斗</el-menu-item>
            <el-menu-item index="/compare">对比分析</el-menu-item>
            <el-menu-item index="/prediction">预测分析</el-menu-item>
          </el-sub-menu>
          
          <el-sub-menu index="operations">
            <template #title>
              <el-icon><Tools /></el-icon>
              <span>运营管理</span>
            </template>
            <el-menu-item index="/operations">运营动作</el-menu-item>
            <el-menu-item index="/targets">目标管理</el-menu-item>
            <el-menu-item index="/promotion">促销活动</el-menu-item>
            <el-menu-item index="/alerts">告警管理</el-menu-item>
            <el-menu-item index="/health">健康度分析</el-menu-item>
          </el-sub-menu>
          
          <el-sub-menu index="data">
            <template #title>
              <el-icon><DataAnalysis /></el-icon>
              <span>数据中心</span>
            </template>
            <el-menu-item index="/import-center">数据导入</el-menu-item>
            <el-menu-item index="/smart-import">智能导入</el-menu-item>
            <el-menu-item index="/report">报表中心</el-menu-item>
            <el-menu-item index="/backup">数据备份</el-menu-item>
            <el-menu-item index="/data-quality">数据质量</el-menu-item>
          </el-sub-menu>
          
          <el-menu-item index="/settings">
            <el-icon><Setting /></el-icon>
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
          <el-breadcrumb v-if="breadcrumbItems.length" separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-for="(item, index) in breadcrumbItems" :key="index" :to="item.to || undefined">
              {{ item.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
          <h2 class="page-title">{{ pageTitle }}</h2>
        </div>
        <div class="header-right">
          <GlobalSearch />
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
          <transition :name="transitionName" mode="out-in">
            <ErrorBoundary :key="$route.path">
              <component :is="Component" />
            </ErrorBoundary>
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { 
  DataBoard, DataLine, Odometer, Goods, Monitor,
  TrendCharts, Trophy, Expand, Fold, Sunny, Moon,
  FullScreen, Tools, DataAnalysis, Setting
} from '@element-plus/icons-vue'
import GlobalSearch from '@/components/GlobalSearch.vue'
import ErrorBoundary from '@/components/ErrorBoundary.vue'


const route = useRoute()
const isCollapsed = ref(false)
const isDark = ref(false)
const transitionName = ref('fade')

const activeMenu = computed(() => route.path)

const pageTitles = {
  '/': '指挥塔',
  '/products': '商品列表',
  '/product': '商品详情',
  '/product-ranking': '商品排行',
  '/lifecycle': '生命周期',
  '/profit': '利润分析',
  '/quadrant': '四象限分析',
  '/traffic-analysis': '流量分析',
  '/ads': '广告投放',
  '/kpi': 'KPI管理',
  '/trends': '趋势分析',
  '/funnel': '转化漏斗',
  '/compare': '对比分析',
  '/prediction': '预测分析',
  '/operations': '运营动作',
  '/targets': '目标管理',
  '/promotion': '促销活动',
  '/alerts': '告警管理',
  '/health': '健康度分析',
  '/import-center': '数据导入',
  '/smart-import': '智能导入',
  '/report': '报表中心',
  '/backup': '数据备份',
  '/data-quality': '数据质量',
  '/settings': '系统设置',
  '/inventory': '库存预警',
  '/reviews': '评价分析'
}

const pageTitle = computed(() => pageTitles[route.path] || '运营系统')

const breadcrumbItems = computed(() => {
  const path = route.path
  if (path === '/') return []
  const segments = path.split('/').filter(Boolean)
  if (segments.length === 1) return []
  return segments.map((seg, i) => ({
    title: pageTitles['/' + segments.slice(0, i + 1).join('/')] || seg,
    to: '/' + segments.slice(0, i + 1).join('/'),
  }))
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

watch(() => route.meta.transitionName, (name) => {
  if (name) transitionName.value = name
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
  
  .date-range-header {
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
