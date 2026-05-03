<template>
  <div 
    class="hexagon-card"
    :class="{ 'clickable': to }"
    @click="handleClick"
  >
    <div class="hexagon-shape">
      <div class="hexagon-inner">
        <div class="icon-wrapper" :style="{ backgroundColor: color }">
          <el-icon :size="28" color="#fff">
            <component :is="icon" />
          </el-icon>
        </div>
        
        <div class="content">
          <h3 class="title">{{ title }}</h3>
          
          <div class="stats">
            <div class="stat-item" v-for="stat in stats" :key="stat.label">
              <span class="stat-value">{{ stat.value }}</span>
              <span class="stat-label">{{ stat.label }}</span>
              <span 
                v-if="stat.change" 
                class="stat-change" 
                :class="stat.change >= 0 ? 'up' : 'down'"
              >
                {{ stat.change >= 0 ? '↑' : '↓' }}{{ Math.abs(stat.change) }}%
              </span>
            </div>
          </div>
        </div>
        
        <div class="actions" v-if="actions.length > 0">
          <el-button 
            v-for="action in actions" 
            :key="action.label"
            size="small" 
            :type="action.type || 'primary'"
            text
            @click.stop="handleAction(action)"
          >
            {{ action.label }}
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const props = defineProps({
  title: {
    type: String,
    required: true
  },
  icon: {
    type: String,
    required: true
  },
  color: {
    type: String,
    default: '#409eff'
  },
  stats: {
    type: Array,
    default: () => []
  },
  actions: {
    type: Array,
    default: () => []
  },
  to: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['action'])

const router = useRouter()

const handleClick = () => {
  if (props.to) {
    router.push(props.to)
  }
}

const handleAction = (action) => {
  emit('action', action)
}
</script>

<style scoped>
.hexagon-card {
  position: relative;
  cursor: default;
}

.hexagon-card.clickable {
  cursor: pointer;
  transition: transform 0.3s ease;
}

.hexagon-card.clickable:hover {
  transform: translateY(-5px);
}

.hexagon-shape {
  position: relative;
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  transition: all 0.3s ease;
  overflow: hidden;
}

.hexagon-shape::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--hex-color, #409eff), var(--hex-color-light, #66b1ff));
}

.hexagon-card:hover .hexagon-shape {
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
}

.hexagon-inner {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.icon-wrapper {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.content {
  flex: 1;
}

.title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 12px 0;
}

.stats {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.stat-label {
  font-size: 13px;
  color: #909399;
}

.stat-change {
  font-size: 12px;
  font-weight: 500;
  padding: 2px 6px;
  border-radius: 4px;
}

.stat-change.up {
  color: #67c23a;
  background: #f0f9eb;
}

.stat-change.down {
  color: #f56c6c;
  background: #fef0f0;
}

.actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  flex-wrap: wrap;
}
</style>
