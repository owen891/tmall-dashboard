<template>
  <el-container class="app-container">
    <el-aside :width="isCollapsed ? '64px' : '220px'" class="app-aside">
      <div class="logo">
        <el-icon size="24" color="#fff"><DataBoard /></el-icon>
        <span v-if="!isCollapsed" class="logo-text">数据仪表盘</span>
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
          <!-- 数据概览 -->
          <el-menu-item index="/">
            <el-icon><Odometer /></el-icon>
            <template #title>数据概览</template>
          </el-menu-item>

          <!-- 商品管理 -->
          <el-sub-menu index="product">
            <template #title>
              <el-icon><Goods /></el-icon>
              <span>商品管理</span>
            </template>
            <el-menu-item index="/products">
              <span>商品列表</span>
            </el-menu-item>
            <el-menu-item index="/channel">
              <span>渠道分析</span>
            </el-menu-item>
          </el-sub-menu>

          <!-- 数据导入 -->
          <el-menu-item index="/import">
            <el-icon><Upload /></el-icon>
            <template #title>数据导入</template>
          </el-menu-item>

          <!-- 核心分析 -->
          <div class="menu-divider">
            <span v-if="!isCollapsed">核心分析</span>
          </div>
          
          <el-sub-menu index="analysis">
            <template #title>
              <el-icon><DataAnalysis /></el-icon>
              <span>核心分析</span>
            </template>
            <el-menu-item index="/quadrant">
              <span>四象限分析</span>
            </el-menu-item>
            <el-menu-item index="/kpi">
              <span>KPI分析</span>
            </el-menu-item>
            <el-menu-item index="/trends">
              <span>趋势分析</span>
            </el-menu-item>
          </el-sub-menu>

          <!-- 推广分析 -->
          <el-sub-menu index="ads">
            <template #title>
              <el-icon><Promotion /></el-icon>
              <span>推广分析</span>
            </template>
            <el-menu-item index="/ads">
              <span>广告投放</span>
            </el-menu-item>
            <el-menu-item index="/health">
              <span>健康度评分</span>
            </el-menu-item>
          </el-sub-menu>

          <!-- 运营监控 -->
          <div class="menu-divider">
            <span v-if="!isCollapsed">运营监控</span>
          </div>

          <el-sub-menu index="operations">
            <template #title>
              <el-icon><Monitor /></el-icon>
              <span>运营监控</span>
            </template>
            <el-menu-item index="/operations">
              <span>操作统计</span>
            </el-menu-item>
            <el-menu-item index="/refunds">
              <span>退款分析</span>
            </el-menu-item>
            <el-menu-item index="/alerts">
              <span>异常告警</span>
            </el-menu-item>
          </el-sub-menu>

          <!-- 评价市场 -->
          <el-sub-menu index="review-market">
            <template #title>
              <el-icon><ChatLineSquare /></el-icon>
              <span>评价与市场</span>
            </template>
            <el-menu-item index="/reviews">
              <span>评价分析</span>
            </el-menu-item>
            <el-menu-item index="/market">
              <span>市场分析</span>
            </el-menu-item>
          </el-sub-menu>

          <!-- 目标管理 -->
          <el-menu-item index="/targets">
            <el-icon><Aim /></el-icon>
            <template #title>目标管理</template>
          </el-menu-item>

          <!-- 智能工具 -->
          <div class="menu-divider">
            <span v-if="!isCollapsed">智能工具</span>
          </div>

          <el-menu-item index="/toolbox">
            <el-icon><Tools /></el-icon>
            <template #title>运营工具箱</template>
          </el-menu-item>
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

        <div class="header-center">
          <div class="date-selector">
            <el-radio-group v-model="dateRangeType" size="default" @change="handleDateRangeChange">
              <el-radio-button label="day">今日</el-radio-button>
              <el-radio-button label="week">本周</el-radio-button>
              <el-radio-button label="month">本月</el-radio-button>
              <el-radio-button label="custom">自定义</el-radio-button>
            </el-radio-group>
            
            <el-date-picker
              v-if="dateRangeType === 'custom'"
              v-model="customDateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              size="default"
              @change="handleCustomDateChange"
            />
            
            <div v-else-if="dateRangeType !== 'custom'" class="quick-date">
              <el-date-picker
                v-model="currentDate"
                type="date"
                placeholder="选择日期"
                size="default"
                :disabled-date="disabledDate"
                @change="handleDateChange"
              />
            </div>
          </div>
        </div>

        <div class="header-right">
          <el-button-group>
            <el-button size="small" @click="handleRefresh">
              <el-icon><Refresh /></el-icon>
            </el-button>
          </el-button-group>
          <el-button type="primary" size="small" @click="$router.push('/import')">
            <el-icon><Upload /></el-icon>
            <span>导入数据</span>
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

const route = useRoute()
const isCollapsed = ref(false)
const dateRangeType = ref('month')
const currentDate = ref(new Date())
const customDateRange = ref([])

const activeMenu = computed(() => route.path)

const pageTitle = computed(() => {
  const titles = {
    '/': '数据概览',
    '/products': '商品列表',
    '/product': '商品详情',
    '/channel': '渠道分析',
    '/import': '数据导入',
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
    '/toolbox': '运营工具箱'
  }
  
  const path = route.path
  if (path.startsWith('/product/')) return '商品详情'
  return titles[path] || '数据概览'
})

const handleDateChange = (date) => {
  if (date) {
    ElMessage.success(`已切换到 ${formatDate(date)}`)
  }
}

const handleCustomDateChange = (range) => {
  if (range && range.length === 2) {
    ElMessage.success(`已切换到 ${formatDate(range[0])} 至 ${formatDate(range[1])}`)
  }
}

const handleDateRangeChange = (type) => {
  if (type === 'day') {
    currentDate.value = new Date()
  } else if (type === 'week') {
    const now = new Date()
    const dayOfWeek = now.getDay() || 7
    currentDate.value = new Date(now.setDate(now.getDate() - dayOfWeek + 1))
  } else if (type === 'month') {
    const now = new Date()
    currentDate.value = new Date(now.getFullYear(), now.getMonth(), 1)
  }
}

const handleRefresh = () => {
  window.location.reload()
}

const formatDate = (date) => {
  if (!date) return ''
  const d = new Date(date)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const disabledDate = (time) => {
  return time.getTime() > Date.now()
}

onMounted(() => {
  handleDateRangeChange('month')
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

.menu-divider {
  padding: 16px 20px 8px;
  font-size: 12px;
  color: #5a5e6a;
  text-transform: uppercase;
  letter-spacing: 1px;
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

.header-center {
  display: flex;
  align-items: center;
  gap: 12px;
}

.date-selector {
  display: flex;
  align-items: center;
  gap: 12px;
}

.quick-date {
  margin-left: 12px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
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
