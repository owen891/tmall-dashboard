<template>
  <div class="products">
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="搜索">
          <el-input v-model="filters.search" placeholder="商品名称/ID" clearable />
        </el-form-item>
        <el-form-item label="分层">
          <el-select v-model="filters.tier" placeholder="全部" clearable>
            <el-option v-for="t in filterOptions.tiers || []" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="风格">
          <el-select v-model="filters.style" placeholder="全部" clearable>
            <el-option v-for="s in filterOptions.styles || []" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="场景">
          <el-select v-model="filters.scene" placeholder="全部" clearable>
            <el-option v-for="s in filterOptions.scenes || []" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadProducts">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
          <el-button type="success" @click="openColumnSelector">字段设置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="table-card">
      <el-table :data="products" stripe v-loading="loading">
        <el-table-column width="60" fixed="left">
          <template #default="{ row }">
            <el-icon 
              :color="row.starred ? '#e6a23c' : '#c0c4cc'" 
              style="cursor: pointer; font-size: 20px"
              @click="toggleStar(row)"
            >
              <Star />
            </el-icon>
          </template>
        </el-table-column>

        <el-table-column label="商品信息" min-width="320" fixed="left">
          <template #default="{ row }">
            <div class="product-info">
              <div class="product-image">
                <img 
                  :src="row.image_url || 'https://via.placeholder.com/60x60/f0f2f5/909399?text=商品'" 
                  :alt="row.title" 
                  loading="lazy" 
                  @error="$event.target.src='https://via.placeholder.com/60x60/f0f2f5/909399?text=商品'" 
                />
              </div>
              <div class="product-content">
                <div class="product-title">{{ row.title }}</div>
                <div class="product-meta">
                  <span class="product-id">{{ row.product_id }}</span>
                </div>
                <div class="product-tags" v-if="row.category || row.tier || row.style || row.scene">
                  <el-tag size="small" v-if="row.tier" :type="getTierType(row.tier)">{{ row.tier }}</el-tag>
                  <el-tag size="small" v-if="row.category" type="info">{{ row.category }}</el-tag>
                  <el-tag size="small" v-if="row.style" type="success">{{ row.style }}</el-tag>
                  <el-tag size="small" v-if="row.scene" type="warning">{{ row.scene }}</el-tag>
                </div>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column
          v-for="field in visibleColumns.filter(f => !['title', 'tier', 'style', 'scene', 'category'].includes(f.key))"
          :key="field.key"
          :prop="field.key"
          :label="field.label"
          :width="field.width"
          :min-width="field.minWidth"
        >
          <template #default="{ row }">
            <span v-if="['payment_amount', 'refund_amount', 'net_sales', 'ad_spend', 'avg_order_value', 'keyword_sales', 'crowd_sales', 'site_sales'].includes(field.key)">
              {{ formatNumber(row[field.key], 2) }}
            </span>
            <span v-else-if="['payment_conversion', 'cart_rate', 'fav_rate', 'refund_rate', 'ad_ratio', 'search_conversion', 'click_rate', 'industry_ctr', 'search_click_rate', 'ad_roi', 'keyword_roi', 'crowd_roi', 'site_roi', 'guide_potential_ratio', 'cross_sell_rate', 'repurchase_rate', 'new_buyer_ratio'].includes(field.key)">
              {{ formatPercent(row[field.key]) }}
            </span>
            <span v-else-if="['ipv', 'pv', 'search_ipv', 'recommend_ipv', 'paid_ipv', 'organic_ipv', 'buyers', 'cart_users', 'fav_users', 'payment_qty', 'cart_qty', 'cross_sell_qty', 'repurchase_users', 'new_buyers', 'keyword_visitors', 'guide_visits', 'guide_visitors', 'guide_potential'].includes(field.key)">
              {{ formatNumber(row[field.key], 0) }}
            </span>
            <span v-else-if="['avg_stay_duration', 'uv_value'].includes(field.key)">
              {{ formatNumber(row[field.key], 2) }}
            </span>
            <span v-else>
              {{ row[field.key] || '-' }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="goToDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.page_size"
        :total="pagination.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadProducts"
        @current-change="loadProducts"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>

    <ColumnSelector ref="columnSelectorRef" v-model="selectedFields" @change="onColumnsChange" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'
import ColumnSelector from '@/components/ColumnSelector.vue'
import { fieldCategories, loadColumnConfig, getFieldConfig, defaultVisibleFields } from '@/config/columns'

const router = useRouter()

const loading = ref(false)
const products = ref([])
const filterOptions = ref({})
const filters = ref({
  search: '',
  category: '',
  tier: '',
  style: '',
  scene: ''
})
const pagination = ref({
  page: 1,
  page_size: 20,
  total: 0
})
const selectedFields = ref([])
const columnSelectorRef = ref(null)

const visibleColumns = computed(() => {
  return selectedFields.value.map(key => getFieldConfig(key)).filter(Boolean)
})

const getTierType = (tier) => {
  const types = {
    '引流款': 'success',
    '利润款': 'primary',
    '潜力款': 'warning'
  }
  return types[tier] || 'info'
}

const formatNumber = (value, decimals = 2) => {
  if (value === null || value === undefined) return '-'
  const num = Number(value)
  if (isNaN(num)) return '-'
  return num.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  })
}

const formatPercent = (value) => {
  if (value === null || value === undefined) return '-'
  const num = Number(value)
  if (isNaN(num)) return '-'
  return `${(num * 100).toFixed(2)}%`
}

const loadFilterOptions = async () => {
  try {
    const res = await api.getFilterOptions()
    filterOptions.value = res.data || {}
  } catch (error) {
    console.error('Load filter options error:', error)
  }
}

const loadProducts = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.value.page,
      page_size: pagination.value.page_size,
      ...filters.value
    }
    const res = await api.getProducts(params)
    const resData = res.data || {}
    products.value = resData.data || []
    pagination.value.total = resData.total || 0
  } catch (error) {
    console.error('Load products error:', error)
    ElMessage.error('加载商品列表失败')
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.value = {
    search: '',
    category: '',
    tier: '',
    style: '',
    scene: ''
  }
  pagination.value.page = 1
  loadProducts()
}

const toggleStar = async (product) => {
  try {
    await api.toggleProductStar(product.product_id)
    product.starred = !product.starred
    ElMessage.success(product.starred ? '已收藏' : '已取消收藏')
  } catch (error) {
    console.error('Toggle star error:', error)
    ElMessage.error('操作失败')
  }
}

const goToDetail = (product) => {
  router.push(`/product/${product.product_id}`)
}

const openColumnSelector = () => {
  columnSelectorRef.value?.open()
}

const onColumnsChange = (fields) => {
  selectedFields.value = fields
}

onMounted(() => {
  const config = loadColumnConfig()
  selectedFields.value = config.visibleFields || defaultVisibleFields
  loadFilterOptions()
  loadProducts()
})
</script>

<style scoped>
.products {
  width: 100%;
}

.filter-card {
  margin-bottom: 20px;
}

.filter-form {
  margin: 0;
}

.table-card {
  width: 100%;
}

.product-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.product-image {
  flex-shrink: 0;
  width: 60px;
  height: 60px;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f7fa;
}

.product-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.product-content {
  flex: 1;
  min-width: 0;
}

.product-title {
  font-weight: 500;
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
}

.product-id {
  color: #909399;
  font-size: 12px;
}

.product-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
</style>
