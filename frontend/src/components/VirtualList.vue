<template>
  <div
    class="virtual-list-container"
    ref="containerRef"
    @scroll="handleScroll"
  >
    <div class="virtual-list-phantom" :style="{ height: totalHeight + 'px' }"></div>
    <div class="virtual-list-content" :style="{ transform: `translateY(${offset}px)` }">
      <div
        v-for="(item, index) in visibleData"
        :key="getItemKey ? getItemKey(item) : index"
        class="virtual-list-item"
        :style="{ height: itemHeight + 'px' }"
      >
        <slot :item="item" :index="startIndex + index"></slot>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps({
  data: {
    type: Array,
    required: true,
  },
  itemHeight: {
    type: Number,
    default: 50,
  },
  bufferSize: {
    type: Number,
    default: 5,
  },
  getItemKey: {
    type: Function,
    default: null,
  },
})

const containerRef = ref(null)
const scrollTop = ref(0)

const startIndex = computed(() => {
  return Math.max(0, Math.floor(scrollTop.value / props.itemHeight) - props.bufferSize)
})

const endIndex = computed(() => {
  const visibleCount = Math.ceil(
    (containerRef.value?.clientHeight || 400) / props.itemHeight
  )
  return Math.min(
    props.data.length,
    startIndex.value + visibleCount + props.bufferSize * 2
  )
})

const visibleData = computed(() => {
  return props.data.slice(startIndex.value, endIndex.value)
})

const offset = computed(() => {
  return startIndex.value * props.itemHeight
})

const totalHeight = computed(() => {
  return props.data.length * props.itemHeight
})

const handleScroll = () => {
  if (containerRef.value) {
    scrollTop.value = containerRef.value.scrollTop
  }
}
</script>

<style scoped>
.virtual-list-container {
  height: 100%;
  overflow-y: auto;
  position: relative;
}

.virtual-list-phantom {
  position: absolute;
  left: 0;
  top: 0;
  right: 0;
}

.virtual-list-content {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
}

.virtual-list-item {
  box-sizing: border-box;
}
</style>
