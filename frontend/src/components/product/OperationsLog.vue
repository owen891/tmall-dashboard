<template>
  <div class="operations-log">
    <el-table :data="operations" stripe style="width: 100%">
      <el-table-column prop="action_date" label="日期" width="120" />
      <el-table-column prop="action_type" label="动作类型" width="150" />
      <el-table-column prop="description" label="描述" />
      <el-table-column prop="operator" label="操作人" width="100" />
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/api'

const props = defineProps({ productId: String })
const operations = ref([])

const loadOperations = async () => {
  try {
    const res = await api.getProductOperations(props.productId)
    operations.value = res.data || []
  } catch (error) {
    operations.value = []
  }
}

onMounted(() => loadOperations())
</script>

<style scoped>
.operations-log {
  padding: 10px;
}
</style>
