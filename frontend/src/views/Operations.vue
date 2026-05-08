<template>
  <div class="operations-container page-container">
    <div class="header">
      <h2>操作效果统计</h2>
      <el-button type="primary" @click="showAddOp = true">记录操作</el-button>
    </div>

    <el-card class="stats-card">
      <el-row :gutter="20">
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-value">{{ stats.total_operations }}</div>
            <div class="stat-label">总操作数</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-value">{{ stats.avg_effectiveness }}</div>
            <div class="stat-label">平均效果分</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-value">{{ stats.positive_rate }}%</div>
            <div class="stat-label">正向效果率</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-value">{{ topAction }}</div>
            <div class="stat-label">最常用操作</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-card class="list-card">
      <el-table :data="operations" stripe>
        <el-table-column prop="action_date" label="日期" width="120" />
        <el-table-column prop="product_title" label="商品" />
        <el-table-column prop="action_type" label="操作类型">
          <template #default="{ row }">
            <el-tag>{{ row.action_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="action_detail" label="操作详情" />
        <el-table-column label="效果评分" width="120">
          <template #default="{ row }">
            <el-tag :type="(row.effectiveness?.score || 0) > 0 ? 'success' : 'info'">
              {{ row.effectiveness?.score || 0 }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showAddOp" title="记录操作" width="500px">
      <el-form :model="opForm" label-width="100px">
        <el-form-item label="商品">
          <el-select v-model="opForm.product_id" placeholder="选择商品" filterable>
            <el-option v-for="p in products" :key="p.product_id" :label="p.title" :value="p.product_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="操作类型">
          <el-select v-model="opForm.action_type" placeholder="选择类型">
            <el-option label="加付费" value="加付费" />
            <el-option label="减付费" value="减付费" />
            <el-option label="观察分析" value="观察分析" />
            <el-option label="换图/内容" value="换图/内容" />
            <el-option label="优化主图" value="优化主图" />
            <el-option label="报名活动" value="报名活动" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="操作详情">
          <el-input v-model="opForm.action_detail" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddOp = false">取消</el-button>
        <el-button type="primary" @click="addOperation">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

const showAddOp = ref(false)
const products = ref([])
const operations = ref([])
const stats = ref({
  total_operations: 0,
  by_type: {},
  avg_effectiveness: 0,
  positive_rate: 0,
  top_performers: []
})
const opForm = ref({
  product_id: null,
  action_type: '',
  action_detail: ''
})

const topAction = computed(() => {
  const byType = stats.value.by_type || {}
  let maxCount = 0
  let topName = '-'
  for (const [name, info] of Object.entries(byType)) {
    if (info.count > maxCount) {
      maxCount = info.count
      topName = name
    }
  }
  return topName
})

const loadData = async () => {
  try {
    const productsRes = await api.get('/products')
    if (productsRes?.data) {
      products.value = productsRes.data.data || productsRes.data || []
    }

    const opsRes = await api.get('/operations')
    if (opsRes?.data) {
      operations.value = opsRes.data.operations || opsRes.data || []
    }

    const statsRes = await api.get('/operations/statistics')
    if (statsRes?.data) {
      stats.value = statsRes.data
    }
  } catch (error) {
    console.error('加载数据失败:', error)
  }
}

const addOperation = async () => {
  try {
    await api.post('/operations', opForm.value)
    ElMessage.success('添加成功')
    showAddOp.value = false
    opForm.value = { product_id: null, action_type: '', action_detail: '' }
    loadData()
  } catch (error) {
    ElMessage.error('添加失败')
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.operations-container {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header h2 {
  margin: 0;
}

.stats-card {
  margin-bottom: 20px;
}

.stat-item {
  text-align: center;
  padding: 10px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.stat-label {
  color: #909399;
  margin-top: 5px;
}
</style>
