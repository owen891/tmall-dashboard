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
          <span class="meta-item"><el-icon><User /></el-icon> {{ product.manager || '-' }}</span>
          <span class="meta-item"><el-icon><Folder /></el-icon> {{ product.category }}</span>
          <span class="meta-item"><el-icon><Brush /></el-icon> {{ product.style }}</span>
          <span class="meta-item"><el-icon><Location /></el-icon> {{ product.scene }}</span>
          <span class="product-id">{{ product.product_id }}</span>
        </div>
        <div class="product-meta secondary">
          <span class="meta-item">
            <el-icon><Calendar /></el-icon> 上架时间: {{ formatDate(product.list_date) }}
          </span>
          <span class="meta-item" v-if="product.operations">
            <el-icon><Document /></el-icon> 运营动作: {{ product.operations }}
          </span>
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
import { User, Folder, Brush, Location, Calendar, Document, Star } from '@element-plus/icons-vue'

defineProps({ product: Object })
defineEmits(['toggleStar'])

const getTierType = (tier) => {
  const types = { '引流款': 'primary', '利润款': 'success', '形象款': 'warning' }
  return types[tier] || 'info'
}

const formatDate = (date) => {
  if (!date) return '-'
  const d = new Date(date)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
</script>

<style scoped>
.product-header {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}
.product-image-large {
  width: 140px;
  height: 140px;
  border-radius: 8px;
  overflow: hidden;
  background: #f5f7fa;
  flex-shrink: 0;
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
  margin: 0 0 12px 0;
  font-size: 20px;
  line-height: 1.4;
}
.product-meta {
  display: flex;
  gap: 12px;
  align-items: center;
  color: #666;
  flex-wrap: wrap;
}
.product-meta.secondary {
  margin-top: 10px;
  color: #909399;
}
.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.product-id {
  font-family: monospace;
  background: #f0f0f0;
  padding: 4px 10px;
  border-radius: 4px;
}
</style>
