<template>
  <el-container class="app-container">
    <el-aside width="240px" class="app-aside">
      <div class="logo">
        <h2>海贝海数据</h2>
      </div>
      <el-menu
        :default-active="activeMenu"
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
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="app-header">
        <div class="header-left">
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
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeMenu = computed(() => route.path)
const pageTitle = computed(() => {
  const titles = {
    '/': '仪表盘',
    '/products': '商品列表',
    '/import': '数据导入',
    '/quadrant': '四象限分析'
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
}

.logo {
  height: 60px;
  line-height: 60px;
  text-align: center;
  color: white;
  background-color: #2b3a4a;
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
