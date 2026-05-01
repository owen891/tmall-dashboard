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
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="table-card">
      <el-table :data="products" stripe v-loading="loading">
        <el-table-column width="60">
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
        <el-table-column label="商品信息" min-width="300">
          <template #default="{ row }">
            <div class="product-info">
              <div class="product-title">{{ row.title }}</div>
              <div class="product-meta">
                <el-tag size="small" :type="getTierType(row.tier)">{{ row.tier }}</el-tag>
                <span class="product-id">{{ row.product_id }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="类目" width="150" />
        <el-table-column prop="style" label="风格" width="100" />
        <el-table-column prop="scene" label="场景" width="100" />
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
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'

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

const getTierType = (tier) => {
  const types = {
    '引流款': 'success',
    '利润款': 'primary',
    '潜力款': 'warning'
  }
  return types[tier] || 'info'
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

onMounted(() => {
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
  flex-direction: column;
}

.product-title {
  font-weight: 500;
  margin-bottom: 5px;
}

.product-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.product-id {
  color: #909399;
  font-size: 12px;
}
</style>
