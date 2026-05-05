<template>
  <el-empty 
    v-if="!hasData" 
    :description="description" 
    :image-size="imageSize"
    class="page-empty"
  >
    <slot>
      <el-button type="primary" @click="handleAction">
        {{ actionText }}
      </el-button>
    </slot>
  </el-empty>
</template>

<script setup>
defineProps({
  hasData: { type: Boolean, default: false },
  description: { type: String, default: '暂无数据' },
  imageSize: { type: Number, default: 120 },
  actionText: { type: String, default: '刷新' },
})

const emit = defineEmits(['action'])
const handleAction = () => emit('action')
</script>

<style scoped>
.page-empty {
  padding: 40px 0;
}
</style>
