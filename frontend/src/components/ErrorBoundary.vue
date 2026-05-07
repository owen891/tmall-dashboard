<template>
  <div v-if="hasError" class="error-boundary">
    <el-result
      icon="error"
      :title="errorTitle"
      :sub-title="errorMessage"
    >
      <template #extra>
        <el-button type="primary" @click="handleRetry">重试</el-button>
        <el-button @click="handleReset">返回首页</el-button>
      </template>
    </el-result>
  </div>
  <slot v-else />
</template>

<script setup>
import { ref, onErrorCaptured } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const router = useRouter()
const hasError = ref(false)
const errorTitle = ref('页面加载出错')
const errorMessage = ref('抱歉，页面发生了错误')
const errorInfo = ref(null)

onErrorCaptured((err, instance, info) => {
  console.error('ErrorBoundary caught:', err, info)
  hasError.value = true
  errorInfo.value = info
  errorMessage.value = err?.message || '未知错误'
  
  ElMessage.error(`页面错误: ${errorMessage.value}`)
  
  return false
})

const handleRetry = () => {
  hasError.value = false
  errorInfo.value = null
}

const handleReset = () => {
  hasError.value = false
  errorInfo.value = null
  router.push('/')
}
</script>

<style scoped>
.error-boundary {
  padding: 40px;
  min-height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
