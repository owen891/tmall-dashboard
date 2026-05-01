<template>
  <el-container class="app-container">
    <el-aside :width="isCollapsed ? '64px' : '240px'" class="app-aside">
      <div class="logo">
        <h2 v-if="!isCollapsed">数据看板</h2>
        <el-icon v-else size="24"><DataBoard /></el-icon>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapsed"
        :collapse-transition="false"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
      >
        <el-menu-item index="/">
          <el-icon><DataBoard /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/products">
          <el-icon><Goods /></el-icon>
          <span>商品列表</span>
        </el-menu-item>
        <el-menu-item index="/import">
          <el-icon><Upload /></el-icon>
          <span>数据导入</span>
        </el-menu-item>
        <el-menu-item index="/quadrant">
          <el-icon><DataLine /></el-icon>
          <span>四象限分析</span>
        </el-menu-item>

        <el-sub-menu index="analysis">
          <template #title>
            <el-icon><TrendCharts /></el-icon>
            <span>数据分析</span>
          </template>
          <el-menu-item index="/kpi">KPI分析</el-menu-item>
          <el-menu-item index="/trends">趋势分析</el-menu-item>
          <el-menu-item index="/ads">广告分析</el-menu-item>
          <el-menu-item index="/health">健康度</el-menu-item>
          <el-menu-item index="/operations">操作统计</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="management">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>运营管理</span>
          </template>
          <el-menu-item index="/refunds">退款分析</el-menu-item>
          <el-menu-item index="/targets">目标管理</el-menu-item>
          <el-menu-item index="/alerts">异常告警</el-menu-item>
          <el-menu-item index="/reviews">评价分析</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="market-tools">
          <template #title>
            <el-icon><Shop /></el-icon>
            <span>市场工具</span>
          </template>
          <el-menu-item index="/market">市场分析</el-menu-item>
          <el-menu-item index="/toolbox">运营工具箱</el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="app-header">
        <div class="header-left">
          <el-button 
            :icon="isCollapsed ? 'Expand' : 'Fold'" 
            @click="isCollapsed = !isCollapsed"
            text
          />
          <span class="page-title">{{ pageTitle }}</span>
        </div>
        <div class="header-right">
          <el-button type="primary" @click="$router.push('/import')">
            <el-icon><Upload /></el-icon>
            导入数据
          </el-button>
        </div>
      </el-header>
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const isCollapsed = ref(false)
const activeMenu = computed(() => route.path)
const pageTitle = computed(() => {
  const titles = {
    '/': '仪表盘',
    '/products': '商品列表',
    '/import': '数据导入',
    '/quadrant': '四象限分析',
    '/kpi': 'KPI分析',
    '/trends': '趋势分析',
    '/ads': '广告分析',
    '/health': '健康度评分',
    '/operations': '操作统计',
    '/refunds': '退款分析',
    '/targets': '目标管理',
    '/alerts': '异常告警',
    '/reviews': '评价分析',
    '/market': '市场分析',
    '/toolbox': '运营工具箱'
  }
  return titles[route.path] || '仪表盘'
})
</script>

<style scoped>
.app-container {
  height: 100vh;
}

.app-aside {
  background-color: #304156;
  overflow: hidden;
  transition: width 0.3s;
}

.logo {
  height: 60px;
  line-height: 60px;
  text-align: center;
  color: white;
  background-color: #2b3a4a;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo h2 {
  margin: 0;
  font-size: 18px;
}

.app-header {
  background-color: white;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
}

.app-main {
  background-color: #f0f2f5;
  padding: 20px;
  overflow: auto;
}
</style>
