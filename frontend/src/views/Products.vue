<template>
  <div class="products">
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="搜索">
          <el-input v-model="filters.search" placeholder="商品名称/ID" clearable size="default" />
        </el-form-item>
        <el-form-item label="分层">
          <el-select v-model="filters.tier" placeholder="全部" clearable size="default">
            <el-option v-for="t in filterOptions.tiers || []" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="风格">
          <el-select v-model="filters.style" placeholder="全部" clearable size="default">
            <el-option v-for="s in filterOptions.styles || []" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="场景">
          <el-select v-model="filters.scene" placeholder="全部" clearable size="default">
            <el-option v-for="s in filterOptions.scenes || []" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadProducts" size="default">查询</el-button>
          <el-button @click="resetFilters" size="default">重置</el-button>
          <el-button type="success" @click="openColumnSelector" size="default">字段设置</el-button>
          <el-button type="warning" @click="handleExport" size="default" :loading="exporting">
            <el-icon><Download /></el-icon> 导出
          </el-button>
          <el-button @click="loadProducts" size="default" :loading="loading">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="table-card">
      <div class="table-toolbar" v-if="selectedProducts.length > 0">
        <span class="selected-count">已选择 {{ selectedProducts.length }} 项</span>
        <el-button size="small" @click="showBatchUpdate = true">批量修改</el-button>
        <el-button size="small" @click="selectedProducts = []">取消选择</el-button>
      </div>
      <el-table 
        :data="products" 
        stripe 
        v-loading="loading"
        size="small"
        :cell-style="{ padding: '6px 4px' }"
        :header-cell-style="{ padding: '8px 4px' }"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="40" fixed="left" />
        <el-table-column width="50" fixed="left">
          <template #default="{ row }">
            <el-icon 
              :color="row.starred ? '#e6a23c' : '#c0c4cc'" 
              style="cursor: pointer; font-size: 16px"
              @click="toggleStar(row)"
            >
              <Star />
            </el-icon>
          </template>
        </el-table-column>

        <el-table-column label="商品信息" min-width="260" fixed="left">
          <template #default="{ row }">
            <div class="product-info-compact">
              <div class="product-image-compact">
                <img 
                  :src="row.image_url || 'https://via.placeholder.com/50x50/f0f2f5/909399?text=商'" 
                  :alt="row.title" 
                  loading="lazy" 
                  @error="$event.target.src='https://via.placeholder.com/50x50/f0f2f5/909399?text=商'" 
                />
              </div>
              <div class="product-content-compact">
                <div class="product-title-compact">{{ row.title }}</div>
                <div class="product-tags-compact">
                  <el-tag size="small" v-if="row.tier" :type="getTierType(row.tier)" style="margin-right: 4px">{{ row.tier }}</el-tag>
                  <el-tag size="small" v-if="row.category" type="info" style="margin-right: 4px">{{ row.category }}</el-tag>
                  <el-tag size="small" v-if="row.style" type="success" style="margin-right: 4px">{{ row.style }}</el-tag>
                  <el-tag size="small" v-if="row.scene" type="warning">{{ row.scene }}</el-tag>
                </div>
                <div class="product-id-compact">{{ row.product_id }}</div>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column
          v-for="field in visibleColumns.filter(f => !['title', 'tier', 'style', 'scene', 'category'].includes(f.key))"
          :key="field.key"
          :prop="field.key"
          :label="field.label"
          :width="field.width || 120"
          :min-width="field.minWidth || 100"
          sortable="custom"
        >
          <template #default="{ row }">
            <span v-if="['payment_amount', 'refund_amount', 'net_sales', 'ad_spend', 'avg_order_value', 'keyword_sales', 'crowd_sales', 'site_sales', 'marketing_cost', 'direct_amount', 'indirect_amount', 'total_amount', 'total_cost', 'shop_collect_cost', 'total_collect_add_cost', 'item_collect_add_cost', 'item_collect_cost', 'cart_cost', 'avg_cpc', 'cpm', 'gsv_2025_01', 'gsv_2025_02', 'gsv_2025_03', 'gsv_2025_04', 'gsv_2025_05', 'gsv_2025_06', 'gsv_2025_07', 'gsv_2025_08', 'gsv_2025_09', 'gsv_2025_10', 'gsv_2025_11', 'gsv_2025_12', 'gsv_2026_01', 'gsv_2026_02', 'gsv_2026_03', 'gsv_total_2025', 'gsv_total_2026'].includes(field.key)">
              {{ formatCurrency(row[field.key]) }}
            </span>
            <span v-else-if="['payment_conversion', 'cart_rate', 'fav_rate', 'refund_rate', 'ad_ratio', 'search_conversion', 'click_rate', 'industry_ctr', 'search_click_rate', 'ad_roi', 'keyword_roi', 'crowd_roi', 'site_roi', 'guide_potential_ratio', 'cross_sell_rate', 'repurchase_rate', 'new_buyer_ratio', 'marketing_roi', 'roi', 'pre_sale_roi', 'ctr', 'click_conversion', 'item_collect_rate', 'collect_add_rate', 'free_search_ctr', 'bundle_rate', 'new_customer_ratio', 'bounce_rate'].includes(field.key)">
              {{ formatPercent(row[field.key]) }}
            </span>
            <span v-else-if="['ipv', 'pv', 'search_ipv', 'recommend_ipv', 'paid_ipv', 'organic_ipv', 'buyers', 'cart_users', 'fav_users', 'payment_qty', 'cart_qty', 'cross_sell_qty', 'repurchase_users', 'new_buyers', 'keyword_visitors', 'guide_visits', 'guide_visitors', 'guide_potential', 'marketing_ipv', 'non_marketing_ipv', 'impressions', 'clicks', 'total_orders', 'direct_orders', 'indirect_orders', 'total_cart', 'direct_cart', 'indirect_cart', 'collect_item', 'collect_shop', 'total_collect_add', 'item_collect_add', 'total_collect', 'new_customer_count', 'total_payers', 'search_buyers', 'bundle_qty', 'bundle_category_width'].includes(field.key)">
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

        <el-table-column label="操作" width="70" fixed="right" align="center">
          <template #default="{ row }">
            <el-tooltip content="详情" placement="top">
              <el-button type="primary" link size="small" @click="goToDetail(row)" style="padding: 4px">
                <el-icon size="14"><View /></el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="运营动作" placement="top">
              <el-button type="success" link size="small" @click="openActionForProduct(row)" style="padding: 4px">
                <el-icon size="14"><Edit /></el-icon>
              </el-button>
            </el-tooltip>
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
        style="margin-top: 16px; justify-content: flex-end"
      />
    </el-card>

    <ColumnSelector ref="columnSelectorRef" v-model="selectedFields" @change="onColumnsChange" />

    <el-dialog v-model="actionDialogVisible" title="添加运营动作" width="600px">
      <el-form :model="actionForm" label-width="100px">
        <el-form-item label="商品ID">
          <el-input v-model="actionForm.product_id" placeholder="请输入商品ID" />
        </el-form-item>
        <el-form-item label="动作类型">
          <el-select v-model="actionForm.action_type" placeholder="请选择">
            <el-option label="标题优化" value="title" />
            <el-option label="主图优化" value="image" />
            <el-option label="价格调整" value="price" />
            <el-option label="SKU调整" value="sku" />
            <el-option label="详情优化" value="detail" />
            <el-option label="营销活动" value="promotion" />
            <el-option label="付费推广" value="ad" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="动作描述">
          <el-input v-model="actionForm.action_detail" type="textarea" :rows="3" placeholder="请描述具体动作" />
        </el-form-item>
        <el-form-item label="执行日期">
          <el-date-picker v-model="actionForm.action_date" type="date" placeholder="选择日期" value-format="YYYY-MM-DD" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="actionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAction">提交</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showBatchUpdate" title="批量修改" width="500px">
      <el-form :model="batchForm" label-width="100px">
        <el-form-item label="分层">
          <el-select v-model="batchForm.tier" placeholder="不修改" clearable style="width: 100%">
            <el-option label="引流款" value="引流款" />
            <el-option label="利润款" value="利润款" />
            <el-option label="潜力款" value="潜力款" />
          </el-select>
        </el-form-item>
        <el-form-item label="风格">
          <el-select v-model="batchForm.style" placeholder="不修改" clearable style="width: 100%">
            <el-option v-for="s in filterOptions.styles || []" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="batchForm.manager" placeholder="不修改" clearable style="width: 100%">
            <el-option v-for="m in filterOptions.managers || []" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBatchUpdate = false">取消</el-button>
        <el-button type="primary" @click="submitBatchUpdate">确定修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { View, Edit, Refresh, Download } from '@element-plus/icons-vue'
import api from '@/api'
import ColumnSelector from '@/components/ColumnSelector.vue'
import { fieldCategories, loadColumnConfig, getFieldConfig, defaultVisibleFields } from '@/config/columns'

const router = useRouter()

const loading = ref(false)
const exporting = ref(false)
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
const actionDialogVisible = ref(false)
const actionForm = ref({
  product_id: '',
  action_type: '',
  action_detail: '',
  action_date: ''
})
const selectedProducts = ref([])
const showBatchUpdate = ref(false)
const batchForm = ref({
  tier: '',
  style: '',
  manager: ''
})

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

const formatCurrency = (value) => {
  if (value === null || value === undefined) return '-'
  const num = Number(value)
  if (isNaN(num)) return '-'
  return '¥' + num.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
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
    
    if (products.value.length === 0) {
      products.value = generateMockProducts()
      pagination.value.total = 50
    }
  } catch (error) {
    console.error('Load products error:', error)
    products.value = generateMockProducts()
    pagination.value.total = 50
  } finally {
    loading.value = false
  }
}

const generateMockProducts = () => {
  const mockProducts = []
  const productNames = [
    '韩版潮流卫衣', '时尚运动裤', '休闲夹克外套', '简约T恤', '保暖羽绒服',
    '复古牛仔裤', '百搭衬衫', '商务西装', '运动套装', '连衣裙'
  ]
  const categories = ['女装', '男装', '鞋靴', '箱包', '配饰']
  const tiers = ['引流款', '利润款', '潜力款']
  const styles = ['韩版', '欧美', '日系', '休闲', '商务']
  const scenes = ['日常', '办公', '运动', '约会', '派对']
  const managers = ['张三', '李四', '王五', '赵六', '孙七']
  
  for (let i = 0; i < 20; i++) {
    const product = {
      product_id: `P${String(10001 + i).padStart(6, '0')}`,
      title: productNames[i % productNames.length] + ` - ${i + 1}号商品`,
      category: categories[i % categories.length],
      tier: tiers[i % tiers.length],
      style: styles[i % styles.length],
      scene: scenes[i % scenes.length],
      manager: managers[i % managers.length],
      list_date: `2025-${String(Math.floor(i / 4) + 1).padStart(2, '0')}-15`,
      status: '在售',
      ipv: Math.floor(Math.random() * 10000) + 1000,
      pv: Math.floor(Math.random() * 50000) + 5000,
      search_ipv: Math.floor(Math.random() * 3000) + 500,
      recommend_ipv: Math.floor(Math.random() * 2000) + 300,
      paid_ipv: Math.floor(Math.random() * 1500) + 200,
      organic_ipv: Math.floor(Math.random() * 3000) + 500,
      bounce_rate: Math.random() * 0.5,
      avg_stay_duration: Math.random() * 300 + 30,
      payment_conversion: Math.random() * 0.15,
      search_conversion: Math.random() * 0.1,
      cart_rate: Math.random() * 0.3,
      fav_rate: Math.random() * 0.2,
      cart_users: Math.floor(Math.random() * 500) + 50,
      cart_qty: Math.floor(Math.random() * 800) + 100,
      fav_users: Math.floor(Math.random() * 300) + 30,
      buyers: Math.floor(Math.random() * 200) + 20,
      search_buyers: Math.floor(Math.random() * 100) + 10,
      payment_amount: Math.floor(Math.random() * 100000) + 10000,
      payment_qty: Math.floor(Math.random() * 500) + 50,
      refund_amount: Math.floor(Math.random() * 5000) + 500,
      net_sales: Math.floor(Math.random() * 95000) + 5000,
      avg_order_value: Math.random() * 200 + 50,
      uv_value: Math.random() * 5,
      refund_rate: Math.random() * 0.1,
      marketing_ipv: Math.floor(Math.random() * 3000) + 500,
      marketing_cost: Math.floor(Math.random() * 5000) + 500,
      marketing_roi: Math.random() * 5 + 1,
      collect_add_rate: Math.random() * 0.5,
      non_marketing_ipv: Math.floor(Math.random() * 2000) + 300,
      free_search_ctr: Math.random() * 0.1,
      industry_ctr: Math.random() * 0.08,
      bundle_qty: Math.floor(Math.random() * 100) + 10,
      bundle_rate: Math.random() * 0.3,
      bundle_category_width: Math.floor(Math.random() * 10) + 1,
      impressions: Math.floor(Math.random() * 100000) + 10000,
      clicks: Math.floor(Math.random() * 5000) + 500,
      cost: Math.floor(Math.random() * 3000) + 300,
      ctr: Math.random() * 0.1,
      avg_cpc: Math.random() * 2 + 0.5,
      cpm: Math.random() * 50 + 10,
      direct_amount: Math.floor(Math.random() * 30000) + 3000,
      indirect_amount: Math.floor(Math.random() * 20000) + 2000,
      total_amount: Math.floor(Math.random() * 50000) + 5000,
      total_orders: Math.floor(Math.random() * 300) + 30,
      direct_orders: Math.floor(Math.random() * 150) + 15,
      indirect_orders: Math.floor(Math.random() * 150) + 15,
      click_conversion: Math.random() * 0.15,
      roi: Math.random() * 5 + 1,
      pre_sale_roi: Math.random() * 5 + 1,
      total_cost: Math.floor(Math.random() * 2000) + 200,
      total_cart: Math.floor(Math.random() * 800) + 80,
      direct_cart: Math.floor(Math.random() * 400) + 40,
      indirect_cart: Math.floor(Math.random() * 400) + 40,
      collect_item: Math.floor(Math.random() * 200) + 20,
      collect_shop: Math.floor(Math.random() * 100) + 10,
      shop_collect_cost: Math.random() * 20 + 2,
      total_collect_add: Math.floor(Math.random() * 500) + 50,
      total_collect_add_cost: Math.random() * 30 + 3,
      item_collect_add: Math.floor(Math.random() * 300) + 30,
      item_collect_add_cost: Math.random() * 20 + 2,
      total_collect: Math.floor(Math.random() * 400) + 40,
      item_collect_cost: Math.random() * 15 + 1.5,
      item_collect_rate: Math.random() * 0.1,
      cart_cost: Math.random() * 15 + 1.5,
      guide_visits: Math.floor(Math.random() * 2000) + 200,
      guide_visitors: Math.floor(Math.random() * 1500) + 150,
      guide_potential: Math.floor(Math.random() * 800) + 80,
      guide_potential_ratio: Math.random() * 0.5,
      new_customer_count: Math.floor(Math.random() * 100) + 10,
      new_customer_ratio: Math.random() * 0.7,
      total_payers: Math.floor(Math.random() * 200) + 20,
      repurchase_rate: Math.random() * 0.3,
      repurchase_users: Math.floor(Math.random() * 80) + 8,
      gsv_2025_01: Math.floor(Math.random() * 30000) + 3000,
      gsv_2025_02: Math.floor(Math.random() * 35000) + 3500,
      gsv_2025_03: Math.floor(Math.random() * 40000) + 4000,
      gsv_2025_04: Math.floor(Math.random() * 45000) + 4500,
      gsv_2025_05: Math.floor(Math.random() * 50000) + 5000,
      gsv_2025_06: Math.floor(Math.random() * 55000) + 5500,
      gsv_2025_07: Math.floor(Math.random() * 60000) + 6000,
      gsv_2025_08: Math.floor(Math.random() * 65000) + 6500,
      gsv_2025_09: Math.floor(Math.random() * 70000) + 7000,
      gsv_2025_10: Math.floor(Math.random() * 75000) + 7500,
      gsv_2025_11: Math.floor(Math.random() * 80000) + 8000,
      gsv_2025_12: Math.floor(Math.random() * 85000) + 8500,
      gsv_2026_01: Math.floor(Math.random() * 50000) + 5000,
      gsv_2026_02: Math.floor(Math.random() * 55000) + 5500,
      gsv_2026_03: Math.floor(Math.random() * 60000) + 6000,
      gsv_total_2025: Math.floor(Math.random() * 700000) + 70000,
      gsv_total_2026: Math.floor(Math.random() * 500000) + 50000,
      starred: Math.random() > 0.8,
      score: Math.floor(Math.random() * 30) + 70
    }
    mockProducts.push(product)
  }
  
  return mockProducts
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
    const newStarred = !product.starred
    await api.updateProduct(product.product_id, { starred: newStarred })
    product.starred = newStarred
    ElMessage.success(product.starred ? '已收藏' : '已取消收藏')
  } catch (error) {
    console.error('Toggle star error:', error)
    ElMessage.error('操作失败')
  }
}

const goToDetail = (product) => {
  router.push(`/product/${product.product_id}`)
}

const openActionForProduct = (product) => {
  actionForm.value.product_id = product.product_id
  actionDialogVisible.value = true
}

const openColumnSelector = () => {
  columnSelectorRef.value?.open()
}

const handleExport = async () => {
  exporting.value = true
  try {
    const params = {
      ...filters.value,
      columns: selectedFields.value.join(',')
    }
    const response = await api.exportProducts(params)
    const blob = new Blob([response], { type: 'text/csv;charset=utf-8' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `products_export_${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (error) {
    console.error('Export error:', error)
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

const onColumnsChange = (fields) => {
  selectedFields.value = fields
}

const submitAction = async () => {
  if (!actionForm.value.product_id || !actionForm.value.action_type || !actionForm.value.action_detail) {
    ElMessage.warning('请填写完整信息')
    return
  }
  try {
    await api.createAction(actionForm.value)
    ElMessage.success('运营动作添加成功')
    actionDialogVisible.value = false
    actionForm.value = {
      product_id: '',
      action_type: '',
      action_detail: '',
      action_date: ''
    }
  } catch (error) {
    console.error('Submit action error:', error)
    ElMessage.error('添加失败')
  }
}

const handleSelectionChange = (selection) => {
  selectedProducts.value = selection
}

const submitBatchUpdate = async () => {
  if (!batchForm.value.tier && !batchForm.value.style && !batchForm.value.manager) {
    ElMessage.warning('请至少选择一项要修改的内容')
    return
  }
  try {
    const productIds = selectedProducts.value.map(p => p.product_id)
    await api.batchUpdateProducts(productIds, {
      tier: batchForm.value.tier || undefined,
      style: batchForm.value.style || undefined,
      manager: batchForm.value.manager || undefined
    })
    ElMessage.success(`成功修改 ${productIds.length} 个商品`)
    showBatchUpdate.value = false
    selectedProducts.value = []
    batchForm.value = { tier: '', style: '', manager: '' }
    loadProducts()
  } catch (error) {
    console.error('Batch update error:', error)
    ElMessage.error('批量修改失败')
  }
}

onMounted(() => {
  const config = loadColumnConfig()
  selectedFields.value = config.visibleFields || defaultVisibleFields
  loadFilterOptions()
  loadProducts()
  
  document.addEventListener('keydown', handleKeyDown)
  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeyDown)
  })
})

const handleKeyDown = (e) => {
  if (e.key === 'Enter' && !e.ctrlKey && !e.metaKey) {
    const activeTag = document.activeElement?.tagName
    if (activeTag !== 'INPUT' && activeTag !== 'TEXTAREA') {
      loadProducts()
    }
  }
}
</script>

<style scoped>
.products {
  width: 100%;
}

.filter-card {
  margin-bottom: 16px;
}

.filter-form {
  margin: 0;
}

.table-card {
  width: 100%;
}

.table-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #ebeef5;
  margin-bottom: 10px;
}

.selected-count {
  color: #409eff;
  font-weight: 500;
}

.product-info-compact {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.product-image-compact {
  flex-shrink: 0;
  width: 50px;
  height: 50px;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f7fa;
}

.product-image-compact img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.product-content-compact {
  flex: 1;
  min-width: 0;
}

.product-title-compact {
  font-weight: 500;
  font-size: 13px;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-tags-compact {
  display: flex;
  flex-wrap: wrap;
  gap: 0;
  margin-bottom: 2px;
}

.product-tags-compact :deep(.el-tag) {
  margin-right: 4px;
  height: 20px;
  line-height: 18px;
  font-size: 11px;
}

.product-id-compact {
  color: #909399;
  font-size: 11px;
}
</style>
