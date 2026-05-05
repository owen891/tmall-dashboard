<template>
  <div class="operations-container">
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
            <div class="stat-value">{{ stats.top_action }}</div>
            <div class="stat-label">最常用操作</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-card class="list-card">
      <el-table :data="operations" stripe>
        <el-table-column prop="action_date" label="日期" width="120" />
        <el-table-column prop="product_name" label="商品" />
        <el-table-column prop="action_type" label="操作类型">
          <template #default="{ row }">
            <el-tag>{{ row.action_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="action_detail" label="操作详情" />
        <el-table-column label="操作前" width="150">
          <template #default="{ row }">
            <div>GMV: {{ formatNumber(row.before_gmv) }}</div>
            <div>访客: {{ row.before_visitors }}</div>
          </template>
        </el-table-column>
        <el-table-column label="操作后" width="150">
          <template #default="{ row }">
            <div>GMV: {{ formatNumber(row.after_gmv) }}</div>
            <div>访客: {{ row.after_visitors }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="effectiveness_score" label="效果分">
          <template #default="{ row }">
            <el-tag :type="row.effectiveness_score > 0 ? 'success' : 'danger'">
              {{ row.effectiveness_score }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showAddOp" title="记录操作" width="500px">
      <el-form :model="opForm" label-width="100px">
        <el-form-item label="商品">
          <el-select v-model="opForm.product_id" placeholder="选择商品">
            <el-option v-for="p in products" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="操作类型">
          <el-select v-model="opForm.action_type" placeholder="选择类型">
            <el-option label="降价" value="price_down" />
            <el-option label="提价" value="price_up" />
            <el-option label="增加投放" value="increase_ad" />
            <el-option label="减少投放" value="decrease_ad" />
            <el-option label="优化主图" value="optimize_image" />
            <el-option label="优化详情" value="optimize_detail" />
            <el-option label="参加活动" value="join_activity" />
            <el-option label="其他" value="other" />
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
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { formatNumber } from '@/utils/format'

const showAddOp = ref(false)
const products = ref([])
const operations = ref([])
const stats = ref({
  total_operations: 0,
  avg_effectiveness: 0,
  positive_rate: 0,
  top_action: ''
})
const opForm = ref({
  product_id: null,
  action_type: '',
  action_detail: ''
})

const loadData = async () => {
  try {
    const productsRes = await api.get('/products')
    if (productsRes.code === 200 || productsRes.data) {
      products.value = productsRes.data || productsRes
    }

    const opsRes = await api.get('/operations')
    if (opsRes.code === 200 || opsRes.data) {
      operations.value = opsRes.data || opsRes
    }

    const statsRes = await api.get('/operations/statistics')
    if (statsRes.code === 200 || statsRes.data) {
      stats.value = statsRes.data || statsRes
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
