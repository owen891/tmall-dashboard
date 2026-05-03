<template>
  <div class="core-indicators">
    <div class="indicator-card" v-for="(item, index) in indicators" :key="index">
      <div class="card-left">
        <div class="icon" :style="{ backgroundColor: item.color }">
          <el-icon :size="24" color="#fff">
            <component :is="item.icon" />
          </el-icon>
        </div>
      </div>
      <div class="card-right">
        <div class="label">{{ item.label }}</div>
        <div class="value">{{ item.value }}</div>
        <div class="change" :class="item.change >= 0 ? 'up' : 'down'">
          <span class="arrow">{{ item.change >= 0 ? '↑' : '↓' }}</span>
          <span class="percent">{{ Math.abs(item.change) }}%</span>
          <span class="vs">vs 上期</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  indicators: {
    type: Array,
    default: () => []
  }
})
</script>

<style scoped>
.core-indicators {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.indicator-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  gap: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  transition: all 0.3s ease;
}

.indicator-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
}

.card-left {
  flex-shrink: 0;
}

.icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-right {
  flex: 1;
}

.label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 6px;
}

.value {
  font-size: 26px;
  font-weight: 700;
  color: #303133;
  margin-bottom: 4px;
}

.change {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}

.change.up {
  color: #67c23a;
}

.change.down {
  color: #f56c6c;
}

.arrow {
  font-size: 16px;
  font-weight: 600;
}

.percent {
  font-weight: 500;
}

.vs {
  color: #909399;
}
</style>
