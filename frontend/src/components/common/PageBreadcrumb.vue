<template>
  <el-breadcrumb separator="/" class="page-breadcrumb">
    <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
    <el-breadcrumb-item v-for="(item, index) in items" :key="index" :to="item.to || undefined">
      {{ item.title }}
    </el-breadcrumb-item>
  </el-breadcrumb>
</template>

<script setup>
defineProps({
  items: { type: Array, default: () => [] },
})
</script>

<style scoped>
.page-breadcrumb {
  margin-bottom: 12px;
  font-size: 13px;
}
</style>
