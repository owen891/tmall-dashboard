<template>
  <div class="targets-container page-container">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="店铺目标" name="shop">
        <div class="header">
          <h3>店铺目标</h3>
          <el-button type="primary" @click="showShopTarget = true">设置目标</el-button>
        </div>

        <el-card class="comparison-card">
          <template #header>
            <span>目标对比 ({{ selectedMetric }})</span>
            <el-select v-model="selectedMetric" @change="loadComparison" style="width: 150px; margin-left: 10px;">
              <el-option label="GMV" value="gmv" />
              <el-option label="访客" value="visitors" />
              <el-option label="转化率" value="conversion" />
              <el-option label="ROI" value="roi" />
            </el-select>
          </template>
          <div ref="shopChartRef" style="width: 100%; height: 300px;"></div>
        </el-card>

        <el-table :data="shopTargets" stripe>
          <el-table-column prop="target_month" label="月份" width="100" />
          <el-table-column label="GMV">
            <template #default="{ row }">
              <div>目标: {{ formatNumber(row.gmv_target) }}</div>
              <div>实际: {{ formatNumber(row.gmv_actual) }}</div>
              <el-progress :percentage="row.gmv_progress" :color="getProgressColor(row.gmv_progress)" />
            </template>
          </el-table-column>
          <el-table-column label="访客">
            <template #default="{ row }">
              <div>目标: {{ row.visitors_target }}</div>
              <div>实际: {{ row.visitors_actual }}</div>
              <el-progress :percentage="row.visitors_progress" :color="getProgressColor(row.visitors_progress)" />
            </template>
          </el-table-column>
          <el-table-column label="转化率">
            <template #default="{ row }">
              <div>目标: {{ row.conversion_target }}%</div>
              <div>实际: {{ row.conversion_actual }}%</div>
              <el-progress :percentage="row.conversion_progress" :color="getProgressColor(row.conversion_progress)" />
            </template>
          </el-table-column>
          <el-table-column label="ROI">
            <template #default="{ row }">
              <div>目标: {{ row.roi_target }}</div>
              <div>实际: {{ row.roi_actual }}</div>
              <el-progress :percentage="row.roi_progress" :color="getProgressColor(row.roi_progress)" />
            </template>
          </el-table-column>
          <el-table-column prop="notes" label="备注" />
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="商品目标" name="product">
        <div class="header">
          <h3>商品目标</h3>
          <el-button type="primary" @click="showProductTarget = true">设置目标</el-button>
        </div>

        <el-table :data="productTargets" stripe>
          <el-table-column prop="product_name" label="商品" />
          <el-table-column prop="target_month" label="月份" width="100" />
          <el-table-column label="销售额">
            <template #default="{ row }">
              <div>目标: {{ formatNumber(row.sales_target) }}</div>
              <div>实际: {{ formatNumber(row.sales_actual) }}</div>
              <el-progress :percentage="row.sales_progress" :color="getProgressColor(row.sales_progress)" />
            </template>
          </el-table-column>
          <el-table-column label="ROI">
            <template #default="{ row }">
              <div>目标: {{ row.roi_target }}</div>
              <div>实际: {{ row.roi_actual }}</div>
              <el-progress :percentage="row.roi_progress" :color="getProgressColor(row.roi_progress)" />
            </template>
          </el-table-column>
          <el-table-column prop="notes" label="备注" />
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="showShopTarget" title="设置店铺目标" width="400px">
      <el-form :model="shopTargetForm" label-width="100px">
        <el-form-item label="月份">
          <el-date-picker v-model="shopTargetForm.target_month" type="month" placeholder="选择月份" value-format="YYYY-MM" />
        </el-form-item>
        <el-form-item label="GMV目标">
          <el-input-number v-model="shopTargetForm.gmv_target" :min="0" />
        </el-form-item>
        <el-form-item label="访客目标">
          <el-input-number v-model="shopTargetForm.visitors_target" :min="0" />
        </el-form-item>
        <el-form-item label="转化率目标">
          <el-input-number v-model="shopTargetForm.conversion_target" :min="0" :step="0.1" />
        </el-form-item>
        <el-form-item label="ROI目标">
          <el-input-number v-model="shopTargetForm.roi_target" :min="0" :step="0.1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showShopTarget = false">取消</el-button>
        <el-button type="primary" @click="saveShopTarget">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showProductTarget" title="设置商品目标" width="400px">
      <el-form :model="productTargetForm" label-width="100px">
        <el-form-item label="商品">
          <el-select v-model="productTargetForm.product_id" placeholder="选择商品">
            <el-option v-for="p in products" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="月份">
          <el-date-picker v-model="productTargetForm.target_month" type="month" placeholder="选择月份" value-format="YYYY-MM" />
        </el-form-item>
        <el-form-item label="销售额目标">
          <el-input-number v-model="productTargetForm.sales_target" :min="0" />
        </el-form-item>
        <el-form-item label="ROI目标">
          <el-input-number v-model="productTargetForm.roi_target" :min="0" :step="0.1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showProductTarget = false">取消</el-button>
        <el-button type="primary" @click="saveProductTarget">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import * as echarts from 'echarts'
import { formatNumber } from '@/utils/format'

const activeTab = ref('shop')
const selectedMetric = ref('gmv')
const shopChartRef = ref(null)
let shopChart = null
let handleResize = null

const shopTargets = ref([])
const productTargets = ref([])
const products = ref([])
const comparison = ref([])
const showShopTarget = ref(false)
const showProductTarget = ref(false)

const shopTargetForm = ref({
  target_month: '',
  gmv_target: 0,
  visitors_target: 0,
  conversion_target: 0,
  roi_target: 0
})

const productTargetForm = ref({
  product_id: null,
  target_month: '',
  sales_target: 0,
  roi_target: 0
})

const loadShopTargets = async () => {
  try {
    const res = await api.get('/targets/shop')
    if (res.code === 200 || res.data) {
      shopTargets.value = res.data || res
    }
  } catch (error) {
    console.error('加载店铺目标失败:', error)
  }
}

const loadProductTargets = async () => {
  try {
    const res = await api.get('/targets/product')
    if (res.code === 200 || res.data) {
      productTargets.value = res.data || res
    }
  } catch (error) {
    console.error('加载商品目标失败:', error)
  }
}

const loadProducts = async () => {
  try {
    const res = await api.get('/products')
    if (res.code === 200 || res.data) {
      products.value = res.data || res
    }
  } catch (error) {
    console.error('加载商品失败:', error)
  }
}

const loadComparison = async () => {
  try {
    const res = await api.get(`/targets/comparison?metric=${selectedMetric.value}`)
    if (res.code === 200 || res.data) {
      comparison.value = res.data || res
      updateShopChart()
    }
  } catch (error) {
    console.error('加载对比数据失败:', error)
  }
}

const saveShopTarget = async () => {
  try {
    await api.post('/targets/shop', shopTargetForm.value)
    ElMessage.success('保存成功')
    showShopTarget.value = false
    loadShopTargets()
    loadComparison()
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

const saveProductTarget = async () => {
  try {
    const product = products.value.find(p => p.id === productTargetForm.value.product_id)
    await api.post('/targets/product', {
      ...productTargetForm.value,
      product_name: product?.name || ''
    })
    ElMessage.success('保存成功')
    showProductTarget.value = false
    loadProductTargets()
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

const updateShopChart = () => {
  if (!shopChart) return

  shopChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['目标', '实际', '完成率'] },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: comparison.value.map(c => c.month) },
    yAxis: [
      { type: 'value', name: '金额/数量' },
      { type: 'value', name: '完成率(%)', min: 0, max: 150 }
    ],
    series: [
      { name: '目标', type: 'bar', data: comparison.value.map(c => c.target) },
      { name: '实际', type: 'bar', data: comparison.value.map(c => c.actual) },
      { name: '完成率', type: 'line', yAxisIndex: 1, data: comparison.value.map(c => c.progress) }
    ]
  })
}

const getProgressColor = (percentage) => {
  if (percentage >= 100) return '#67c23a'
  if (percentage >= 80) return '#e6a23c'
  return '#f56c6c'
}

onMounted(() => {
  shopChart = echarts.init(shopChartRef.value)
  loadShopTargets()
  loadProductTargets()
  loadProducts()
  loadComparison()
  handleResize = () => shopChart?.resize()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  shopChart?.dispose()
})
</script>

<style scoped>
.targets-container {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header h3 {
  margin: 0;
}

.comparison-card,
.el-table {
  margin-bottom: 20px;
}
</style>
