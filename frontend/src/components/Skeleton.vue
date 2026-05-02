<template>
  <div class="skeleton" :style="{ height: height + 'px', width: width }">
    <div class="skeleton-content" :class="{ 'skeleton-animated': animated }"></div>
  </div>
</template>

<script setup>
defineProps({
  height: {
    type: Number,
    default: 20,
  },
  width: {
    type: String,
    default: '100%',
  },
  animated: {
    type: Boolean,
    default: true,
  },
})
</script>

<style scoped>
.skeleton {
  background: linear-gradient(90deg, #f2f2f2 25%, #e6e6e6 37%, #f2f2f2 63%);
  background-size: 400% 100%;
  border-radius: 4px;
  overflow: hidden;
}

.skeleton-content {
  width: 100%;
  height: 100%;
}

.skeleton-animated {
  animation: skeleton-loading 1.4s ease infinite;
}

@keyframes skeleton-loading {
  0% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0 50%;
  }
}

.dark .skeleton {
  background: linear-gradient(90deg, #2d2d2d 25%, #3a3a3a 37%, #2d2d2d 63%);
  background-size: 400% 100%;
}
</style>
