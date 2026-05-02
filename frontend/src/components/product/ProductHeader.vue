<template>
  <el-card class="info-card" style="margin-top: 20px">
    <div class="product-header">
      <div class="product-image-large" v-if="product.image_url">
        <img :src="product.image_url" :alt="product.title" @error="$event.target.style.display='none'" />
      </div>
      <div class="product-info">
        <h2>{{ product.title }}</h2>
        <div class="product-meta">
          <el-tag :type="getTierType(product.tier)">{{ product.tier }}</el-tag>
          <span>{{ product.category }}</span>
          <span>{{ product.style }} / {{ product.scene }}</span>
          <span class="product-id">{{ product.product_id }}</span>
        </div>
      </div>
      <div class="product-actions">
        <el-button :type="product.starred ? 'warning' : 'default'" @click="$emit('toggleStar')">
          <el-icon><Star /></el-icon>
          {{ product.starred ? '已收藏' : '收藏' }}
        </el-button>
      </div>
    </div>
  </el-card>
</template>

<script setup>
defineProps({ product: Object })
defineEmits(['toggleStar'])

const getTierType = (tier) => {
  const types = { 'A': 'success', 'B': 'warning', 'C': 'danger' }
  return types[tier] || 'info'
}
</script>

<style scoped>
.product-header {
  display: flex;
  gap: 20px;
  align-items: center;
}
.product-image-large {
  width: 120px;
  height: 120px;
  border-radius: 8px;
  overflow: hidden;
  background: #f5f7fa;
}
.product-image-large img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.product-info {
  flex: 1;
}
.product-info h2 {
  margin: 0 0 10px 0;
  font-size: 20px;
}
.product-meta {
  display: flex;
  gap: 10px;
  align-items: center;
  color: #666;
}
.product-id {
  font-family: monospace;
  background: #f0f0f0;
  padding: 2px 8px;
  border-radius: 4px;
}
</style>
