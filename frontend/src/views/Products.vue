<template>
  <div class="products">
    <el-card class="filter-card">
      <template #header>
        <div class="filter-header">
          <span class="filter-title">
            <el-icon><Search /></el-icon>
            筛选条件
          </span>
          <el-button link @click="showFilters = !showFilters">
            <el-icon><ArrowDown v-if="!showFilters" /><ArrowUp v-else /></el-icon>
            {{ showFilters ? '收起' : '展开' }}
          </el-button>
        </div>
      </template>
      <el-collapse-transition>
        <div v-show="showFilters">
          <el-form :inline="true" :model="filters" class="filter-form">
            <el-form-item label="搜索">
              <el-input v-model="filters.search" placeholder="商品名称/ID" clearable size="default" @keyup.enter="loadProducts">
                <template #prefix><el-icon><Search /></el-icon></template>
              </el-input>
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
              <el-button type="primary" @click="loadProducts" size="default">
                <el-icon><Search /></el-icon> 查询
              </el-button>
              <el-button @click="resetFilters" size="default">
                <el-icon><RefreshLeft /></el-icon> 重置
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-collapse-transition>
      <div class="filter-actions">
        <el-dropdown split-button type="success" @click="handleExport" size="default">
          <el-icon><Download /></el-icon> 导出
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="handleExport('csv')">导出为 CSV</el-dropdown-item>
              <el-dropdown-item @click="handleExport('json')">导出为 JSON</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button @click="loadProducts" size="default" :loading="loading">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
        <el-button @click="showColumnConfig = true" size="default">
          <el-icon><Setting /></el-icon> 列配置
        </el-button>
      </div>
    </el-card>

    <el-card class="table-card">
      <div class="table-toolbar" v-if="selectedProducts.length > 0">
        <span class="selected-count">
          <el-icon><Check /></el-icon>
          已选择 <strong>{{ selectedProducts.length }}</strong> 项
        </span>
        <el-button size="small" type="primary" @click="showBatchUpdate = true">
          <el-icon><Edit /></el-icon> 批量修改
        </el-button>
        <el-button size="small" @click="selectedProducts = []">取消选择</el-button>
      </div>
      
      <el-table 
        :data="products" 
        stripe 
        v-loading="loading"
        element-loading-text="正在加载商品数据..."
        size="small"
        :cell-style="{ padding: '8px 6px' }"
        :header-cell-style="{ padding: '10px 6px', background: 'var(--el-fill-color-light)' }"
        @selection-change="handleSelectionChange"
        @sort-change="handleSortChange"
        empty-text="暂无商品数据，请先导入数据"
      >
        <el-table-column type="selection" width="45" fixed="left" />
        <el-table-column width="55" fixed="left" label="收藏">
          <template #default="{ row }">
            <el-tooltip :content="row.starred ? '取消收藏' : '收藏商品'" placement="top">
              <el-icon 
                :color="row.starred ? '#e6a23c' : '#c0c4cc'" 
                style="cursor: pointer; font-size: 16px; transition: all 0.3s"
                @click="toggleStar(row)"
                class="star-icon"
                :class="{ 'star-active': row.starred }"
              >
                <Star />
              </el-icon>
            </el-tooltip>
          </template>
        </el-table-column>

        <el-table-column label="商品信息" min-width="280" fixed="left">
          <template #default="{ row }">
            <div class="product-info-compact" @click="goToDetail(row)" style="cursor: pointer">
              <div class="product-image-compact">
                <img 
                  :src="row.image_url || 'https://via.placeholder.com/50x50/f0f2f5/909399?text=商'" 
                  :alt="row.title" 
                  loading="lazy" 
                  @error="$event.target.src='https://via.placeholder.com/50x50/f0f2f5/909399?text=商'" 
                />
              </div>
              <div class="product-content-compact">
                <div class="product-title-compact" :title="row.title">{{ row.title }}</div>
                <div class="product-tags-compact">
                  <el-tag size="small" v-if="row.tier" :type="getTierType(row.tier)" effect="plain">{{ row.tier }}</el-tag>
                  <el-tag size="small" v-if="row.category" type="info" effect="plain">{{ row.category }}</el-tag>
                  <el-tag size="small" v-if="row.style" type="success" effect="plain">{{ row.style }}</el-tag>
                  <el-tag size="small" v-if="row.scene" type="warning" effect="plain">{{ row.scene }}</el-tag>
                </div>
                <div class="product-id-compact">ID: {{ row.product_id }}</div>
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
          :sort-orders="['descending', 'ascending', null]"
        >
          <template #default="{ row }">
            <span v-if="['payment_amount', 'refund_amount', 'net_sales', 'ad_spend', 'avg_order_value'].includes(field.key)" :class="getNumberClass(row[field.key], field.key)">
              {{ formatNumber(row[field.key], 2) }}
            </span>
            <span v-else-if="['payment_conversion', 'cart_rate', 'fav_rate', 'refund_rate', 'ad_ratio'].includes(field.key)" :class="getPercentClass(row[field.key], field.key)">
              {{ formatPercent(row[field.key]) }}
            </span>
            <span v-else>
              {{ row[field.key] != null ? row[field.key] : '-' }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="90" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-tooltip content="查看详情" placement="top">
                <el-button type="primary" link size="small" @click="goToDetail(row)">
                  <el-icon><View /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="记录运营动作" placement="top">
                <el-button type="success" link size="small" @click="openActionForProduct(row)">
                  <el-icon><EditPen /></el-icon>
                </el-button>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.page_size"
        :total="pagination.total"
        :page-sizes="[20, 50, 100, 200]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadProducts"
        @current-change="loadProducts"
        class="pagination-bar"
      />
    </el-card>

    <el-dialog v-model="actionDialogVisible" title="添加运营动作" width="600px" :close-on-click-modal="false">
      <el-form :model="actionForm" label-width="100px" ref="actionFormRef" :rules="actionFormRules">
        <el-form-item label="商品ID" prop="product_id">
          <el-input v-model="actionForm.product_id" placeholder="请输入商品ID" />
        </el-form-item>
        <el-form-item label="动作类型" prop="action_type">
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
        <el-form-item label="动作描述" prop="action_detail">
          <el-input v-model="actionForm.action_detail" type="textarea" :rows="3" placeholder="请描述具体动作" />
        </el-form-item>
        <el-form-item label="执行日期">
          <el-date-picker v-model="actionForm.action_date" type="date" placeholder="选择日期" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="actionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAction" :loading="submitting">提交</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showBatchUpdate" title="批量修改" width="500px" :close-on-click-modal="false">
      <el-alert title="提示：批量修改将影响选中的所有商品" type="info" show-icon :closable="false" style="margin-bottom: 16px" />
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
        <el-button type="primary" @click="submitBatchUpdate" :loading="submitting">确定修改</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showColumnConfig" title="列配置" width="600px">
      <div class="column-config">
        <div class="column-section" v-for="category in fieldCategories" :key="category.key">
          <h4 class="column-category">{{ category.label }}</h4>
          <el-checkbox-group v-model="selectedFields">
            <el-checkbox 
              v-for="field in category.fields" 
              :key="field.key" 
              :label="field.key"
            >
              {{ field.label }}
            </el-checkbox>
          </el-checkbox-group>
        </div>
      </div>
      <template #footer>
        <el-button @click="showColumnConfig = false">取消</el-button>
        <el-button type="primary" @click="saveColumnConfig">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  View, Edit, EditPen, Refresh, RefreshLeft, Download, Search, Check, Star,
  ArrowDown, ArrowUp, Setting
} from '@element-plus/icons-vue'
import api from '@/api'
import { fieldCategories, loadColumnConfig, getFieldConfig, defaultVisibleFields } from '@/config/columns'
import { useTimeStore } from '@/stores/time'
import { formatNumber, formatPercent, getTierType } from '@/utils/format'

const router = useRouter()
const timeStore = useTimeStore()

const loading = ref(false)
const exporting = ref(false)
const submitting = ref(false)
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
const actionDialogVisible = ref(false)
const actionFormRef = ref(null)
const actionForm = ref({
  product_id: '',
  action_type: '',
  action_detail: '',
  action_date: ''
})
const actionFormRules = {
  product_id: [{ required: true, message: '请输入商品ID', trigger: 'blur' }],
  action_type: [{ required: true, message: '请选择动作类型', trigger: 'change' }],
  action_detail: [{ required: true, message: '请描述具体动作', trigger: 'blur' }],
}
const selectedProducts = ref([])
const showBatchUpdate = ref(false)
const showFilters = ref(true)
const showColumnConfig = ref(false)
const batchForm = ref({
  tier: '',
  style: '',
  manager: ''
})

const visibleColumns = computed(() => {
  return selectedFields.value.map(key => getFieldConfig(key)).filter(Boolean)
})

function getNumberClass(value, field) {
  if (!value || value <= 0) return 'text-muted'
  if (['ad_spend', 'refund_amount'].includes(field)) return 'text-danger'
  return 'text-primary'
}

function getPercentClass(value, field) {
  if (!value) return 'text-muted'
  const pct = value * 100
  if (field === 'refund_rate' && pct > 20) return 'text-danger'
  if (field === 'payment_conversion' && pct < 2) return 'text-warning'
  return 'text-success'
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
    
    if (timeStore.startDate && timeStore.endDate) {
      params.start_date = timeStore.startDate
      params.end_date = timeStore.endDate
    }
    
    const res = await api.getProducts(params)
    const resData = res.data || {}
    products.value = resData.data || []
    pagination.value.total = resData.total || 0
    
    if (products.value.length === 0) {
      ElMessage.info('未找到匹配的商品数据')
    }
  } catch (error) {
    console.error('Load products error:', error)
    ElMessage.error(`加载商品列表失败: ${error.message || '网络错误'}`)
    products.value = []
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
  ElMessage.success('筛选条件已重置')
}

const handleSortChange = ({ prop, order }) => {
  if (!order) {
    loadProducts()
    return
  }
  const sortMap = { descending: 'desc', ascending: 'asc' }
  filters.value.sort = prop
  filters.value.order = sortMap[order]
  loadProducts()
}

const toggleStar = async (product) => {
  try {
    await api.toggleProductStar(product.product_id)
    product.starred = !product.starred
    ElMessage.success({
      message: product.starred ? '已收藏' : '已取消收藏',
      duration: 1500,
    })
  } catch (error) {
    console.error('Toggle star error:', error)
    ElMessage.error('操作失败，请重试')
  }
}

const goToDetail = (product) => {
  router.push(`/product/${product.product_id}`)
}

const openActionForProduct = (product) => {
  actionForm.value.product_id = product.product_id
  actionDialogVisible.value = true
}

const handleExport = async (format = 'csv') => {
  ElMessage.info(`正在准备导出${format.toUpperCase()}文件...`)
  exporting.value = true
  try {
    const params = {
      ...filters.value,
      columns: selectedFields.value.join(','),
      format
    }
    const response = await api.exportProducts(params)
    const blob = new Blob([response], { type: format === 'csv' ? 'text/csv;charset=utf-8' : 'application/json' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `products_${new Date().toISOString().slice(0, 10)}.${format}`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success(`导出成功！共 ${products.value.length} 条数据`)
  } catch (error) {
    console.error('Export error:', error)
    ElMessage.error(`导出失败: ${error.message || '未知错误'}`)
  } finally {
    exporting.value = false
  }
}

const submitAction = async () => {
  if (!actionFormRef.value) return
  
  try {
    await actionFormRef.value.validate()
  } catch {
    ElMessage.warning('请检查必填项')
    return
  }
  
  submitting.value = true
  try {
    await api.createAction(actionForm.value)
    ElMessage.success('运营动作添加成功')
    actionDialogVisible.value = false
    actionForm.value = { product_id: '', action_type: '', action_detail: '', action_date: '' }
  } catch (error) {
    console.error('Submit action error:', error)
    ElMessage.error(`添加失败: ${error.message || '未知错误'}`)
  } finally {
    submitting.value = false
  }
}

const handleSelectionChange = (selection) => {
  selectedProducts.value = selection
}

const saveColumnConfig = () => {
  localStorage.setItem('product_column_config', JSON.stringify(selectedFields.value))
  showColumnConfig.value = false
  ElMessage.success('列配置已保存')
}

const submitBatchUpdate = async () => {
  if (!batchForm.value.tier && !batchForm.value.style && !batchForm.value.manager) {
    ElMessage.warning('请至少选择一项要修改的内容')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要修改选中的 ${selectedProducts.value.length} 个商品吗？此操作不可撤销。`,
      '批量修改确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  
  submitting.value = true
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
    ElMessage.error(`批量修改失败: ${error.message || '未知错误'}`)
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  const config = loadColumnConfig()
  selectedFields.value = config.visibleFields || defaultVisibleFields
  loadFilterOptions()
  loadProducts()
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeyDown)
})

onMounted(() => {
  document.addEventListener('keydown', handleKeyDown)
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

.filter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filter-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 15px;
}

.filter-form {
  margin: 0;
  padding: 16px 0;
  border-bottom: 1px solid #ebeef5;
}

.filter-actions {
  display: flex;
  gap: 12px;
  padding-top: 16px;
}

.column-config {
  max-height: 400px;
  overflow-y: auto;
}

.column-section {
  margin-bottom: 20px;
}

.column-category {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}

.table-card {
  width: 100%;
}

.table-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid #ebeef5;
  margin-bottom: 12px;
}

.selected-count {
  color: #409eff;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;
}

.star-icon {
  transition: all 0.3s;
}
.star-icon:hover {
  transform: scale(1.2);
}
.star-active {
  animation: starPulse 0.6s ease-in-out;
}

@keyframes starPulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.3); }
}

.pagination-bar {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.product-info-compact {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 2px 0;
  transition: background 0.2s;
}
.product-info-compact:hover {
  background: var(--el-fill-color-light);
  border-radius: 4px;
}

.product-image-compact {
  flex-shrink: 0;
  width: 56px;
  height: 56px;
  border-radius: 6px;
  overflow: hidden;
  background: #f5f7fa;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
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
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--el-text-color-primary);
}

.product-tags-compact {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 4px;
}

.product-id-compact {
  color: #909399;
  font-size: 11px;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 8px;
}

.text-muted {
  color: #c0c4cc;
}
.text-primary {
  color: #409eff;
  font-weight: 500;
}
.text-success {
  color: #67c23a;
}
.text-warning {
  color: #e6a23c;
}
.text-danger {
  color: #f56c6c;
}

:deep(.dark) .product-image-compact {
  background: #333;
}
:deep(.dark) .table-toolbar {
  border-bottom-color: #333;
}
</style>
