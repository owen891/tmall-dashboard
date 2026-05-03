<template>
  <div class="alert-bar">
    <div class="alert-bar-header">
      <div class="title">
        <el-icon><Warning /></el-icon>
        <span>实时告警</span>
        <el-tag type="danger" size="small" v-if="urgentCount > 0">{{ urgentCount }} 紧急</el-tag>
        <el-tag type="warning" size="small" v-if="warningCount > 0">{{ warningCount }} 警告</el-tag>
      </div>
      <el-button type="primary" size="small" text @click="viewAll">查看全部</el-button>
    </div>
    
    <div class="alert-list" v-if="alerts.length > 0">
      <div 
        v-for="alert in displayAlerts" 
        :key="alert.id" 
        class="alert-item"
        :class="alert.level"
      >
        <div class="alert-content">
          <el-icon class="alert-icon">
            <Warning v-if="alert.level === 'urgent'" />
            <InfoFilled v-else />
          </el-icon>
          <div class="alert-text">
            <span class="alert-title">{{ alert.title }}</span>
            <span class="alert-desc">{{ alert.desc }}</span>
          </div>
        </div>
        <div class="alert-meta">
          <span class="alert-time">{{ alert.time }}</span>
          <el-button type="primary" size="small" text @click="handleAlert(alert)">处理</el-button>
        </div>
      </div>
    </div>
    
    <el-empty v-else description="暂无告警" :image-size="60" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Warning, InfoFilled } from '@element-plus/icons-vue'

const props = defineProps({
  alerts: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['alert-click'])

const router = useRouter()

const urgentCount = computed(() => 
  props.alerts.filter(a => a.level === 'urgent').length
)

const warningCount = computed(() => 
  props.alerts.filter(a => a.level === 'warning').length
)

const displayAlerts = computed(() => 
  props.alerts.slice(0, 5)
)

const viewAll = () => {
  router.push('/smart-alert')
}

const handleAlert = (alert) => {
  ElMessage.success(`已处理告警: ${alert.title}`)
  emit('alert-click', alert)
}
</script>

<style scoped>
.alert-bar {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.alert-bar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.alert-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.alert-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-radius: 8px;
  background: #f5f7fa;
  transition: all 0.3s ease;
}

.alert-item:hover {
  background: #ecf5ff;
}

.alert-item.urgent {
  background: #fef0f0;
  border-left: 3px solid #f56c6c;
}

.alert-item.warning {
  background: #fdf6ec;
  border-left: 3px solid #e6a23c;
}

.alert-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.alert-icon {
  font-size: 20px;
  flex-shrink: 0;
}

.alert-item.urgent .alert-icon {
  color: #f56c6c;
}

.alert-item.warning .alert-icon {
  color: #e6a23c;
}

.alert-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.alert-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.alert-desc {
  font-size: 13px;
  color: #909399;
}

.alert-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.alert-time {
  font-size: 12px;
  color: #c0c4cc;
}
</style>
