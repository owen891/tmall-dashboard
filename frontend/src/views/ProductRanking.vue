<template>
  <div class="page-container ranking-page">
    <div class="page-header">
      <h1>商品排行榜</h1>
      <ExportButton 
        :table-data="products" 
        :file-name="`商品排行榜_${activeTab}_${new Date().toISOString().split('T')[0]}`"
        button-text="导出数据"
        type="primary"
        size="small"
      />
    </div>

    <el-tabs v-model="activeTab" type="card" @tab-change="handleTabChange">
      <el-tab-pane label="销售额排行" name="gmv" />
      <el-tab-pane label="销量排行" name="quantity" />
      <el-tab-pane label="转化率排行" name="conversion" />
      <el-tab-pane label="退款率排行" name="refund" />
    </el-tabs>

    <div v-loading="loading" class="ranking-content">
      <el-table :data="products" style="width: 100%">
        <el-table-column label="排名" width="80">
          <template #default="{ $index }">
            <div class="rank-badge" :class="getRankClass($index)">
              {{ $index + 1 }}
            </div>
          </template>
        </el-table-column>
        
        <el-table-column label="商品信息" min-width="300">
          <template #default="{ row }">
            <div class="product-info">
              <el-image 
                :src="row.image_url" 
                fit="cover"
                style="width: 60px; height: 60px; border-radius: 4px;"
              />
              <div class="product-detail">
                <div class="product-title">{{ row.title }}</div>
                <div class="product-meta">
                  <el-tag size="small" v-if="row.tier">{{ row.tier }}</el-tag>
                  <span class="category">{{ row.category }}</span>
                </div>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="销售额" width="120" sortable>
          <template #default="{ row }">
            <span class="amount">¥{{ formatNumber(row.payment_amount) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="销量" width="100" sortable>
          <template #default="{ row }">
            {{ formatNumber(row.payment_count || 0) }}
          </template>
        </el-table-column>

        <el-table-column label="访客数" width="100" sortable>
          <template #default="{ row }">
            {{ formatNumber(row.visitors) }}
          </template>
        </el-table-column>

        <el-table-column label="转化率" width="100" sortable>
          <template #default="{ row }">
            <span :class="getConversionClass(row.conversion)">
              {{ (row.conversion * 100).toFixed(2) }}%
            </span>
          </template>
        </el-table-column>

        <el-table-column label="退款率" width="100" sortable>
          <template #default="{ row }">
            <span :class="getRefundClass(row.refund_rate)">
              {{ (row.refund_rate * 100).toFixed(2) }}%
            </span>
          </template>
        </el-table-column>

        <el-table-column label="ROI" width="100" sortable>
          <template #default="{ row }">
            <span :class="getRoiClass(row.roi)">
              {{ row.roi?.toFixed(2) || '-' }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewProduct(row)">详情</el-button>
            <el-button size="small" @click="viewTrend(row)">趋势</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import ExportButton from '@/components/ExportButton.vue'
import api from '@/api'
import { formatNumber } from '@/utils/format'

const router = useRouter()
const loading = ref(false)
const activeTab = ref('gmv')
const products = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

const loadProducts = async () => {
  loading.value = true
  try {
    const res = await api.productsApi.getRanking({
      limit: pageSize.value,
      offset: (currentPage.value - 1) * pageSize.value,
      sort_by: activeTab.value,
      sort_order: 'desc'
    })
    
    const data = res?.data || {}
    products.value = (data.products || []).map(p => ({
      product_id: p.product_id || '',
      title: p.title || '未知商品',
      image_url: p.image_url || '',
      category: p.category || '',
      tier: p.tier || '',
      payment_amount: p.payment_amount || 0,
      payment_count: p.payment_count || 0,
      visitors: p.visitors || 0,
      conversion: p.conversion || 0,
      refund_rate: p.refund_rate || 0,
      roi: p.roi || 0
    }))
    total.value = data.total || 0
  } catch (error) {
    console.error('加载排行榜失败:', error)
    ElMessage.error('加载排行榜失败')
    products.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const getRankClass = (index) => {
  if (index === 0) return 'gold'
  if (index === 1) return 'silver'
  if (index === 2) return 'bronze'
  return ''
}

const getConversionClass = (conversion) => {
  if (conversion >= 0.03) return 'high'
  if (conversion >= 0.01) return 'medium'
  return 'low'
}

const getRefundClass = (refundRate) => {
  if (refundRate <= 0.05) return 'low'
  if (refundRate <= 0.15) return 'medium'
  return 'high'
}

const getRoiClass = (roi) => {
  if (roi >= 5) return 'high'
  if (roi >= 2) return 'medium'
  return 'low'
}

const handleTabChange = () => {
  currentPage.value = 1
  loadProducts()
}

const handleSizeChange = () => {
  currentPage.value = 1
  loadProducts()
}

const handlePageChange = () => {
  loadProducts()
}

const viewProduct = (row) => {
  router.push(`/product/${row.product_id}`)
}

const viewTrend = (row) => {
  ElMessage.info(`查看 ${row.title} 的趋势`)
}

onMounted(() => {
  loadProducts()
})
</script>

<style scoped>
.ranking-page {
}

.page-header {
  margin-bottom: 20px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 600;
  margin: 0;
}

.ranking-content {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #f0f0f0;
  font-weight: 600;
  color: #666;
}

.rank-badge.gold {
  background: linear-gradient(135deg, #FFD700, #FFA500);
  color: white;
}

.rank-badge.silver {
  background: linear-gradient(135deg, #C0C0C0, #A0A0A0);
  color: white;
}

.rank-badge.bronze {
  background: linear-gradient(135deg, #CD7F32, #B87333);
  color: white;
}

.product-info {
  display: flex;
  gap: 12px;
  align-items: center;
}

.product-detail {
  flex: 1;
}

.product-title {
  font-weight: 500;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.product-meta {
  display: flex;
  gap: 8px;
  align-items: center;
}

.category {
  font-size: 12px;
  color: #999;
}

.amount {
  font-weight: 600;
  color: #409EFF;
}

.high {
  color: #67C23A;
  font-weight: 500;
}

.medium {
  color: #E6A23C;
}

.low {
  color: #F56C6C;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
