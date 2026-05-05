<template>
  <div class="smart-table">
    <div class="smart-table-toolbar">
      <div class="toolbar-left">
        <el-input
          v-if="searchable"
          v-model="searchText"
          placeholder="搜索表格内容..."
          clearable
          class="table-search"
          @input="debouncedSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select
          v-if="filterColumns.length > 0"
          v-model="activeFilters"
          multiple
          collapse-tags
          collapse-tags-tooltip
          placeholder="筛选"
          clearable
          class="table-filter"
          @change="applyFilters"
        >
          <el-option
            v-for="col in filterColumns"
            :key="col.prop"
            :label="col.label"
            :value="col.prop"
          />
        </el-select>
        <slot name="toolbar-left"></slot>
        <span v-if="filteredData.length > 0" class="result-count">
          共 {{ filteredData.length }} 条记录
        </span>
      </div>
      <div class="toolbar-right">
        <el-dropdown v-if="exportable" trigger="click" @command="handleExport">
          <el-button type="success" :icon="Download">
            导出
            <el-icon><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="csv">导出为 CSV</el-dropdown-item>
              <el-dropdown-item command="json">导出为 JSON</el-dropdown-item>
              <el-dropdown-item command="excel" v-if="supportExcel">导出为 Excel</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        
        <el-popover trigger="click" placement="bottom-end" width="300">
          <template #reference>
            <el-button :icon="Setting" circle title="列设置" />
          </template>
          <div class="column-settings">
            <div class="settings-header">
              <el-checkbox 
                v-model="allColumnsSelected" 
                @change="toggleAllColumns"
              >
                全选
              </el-checkbox>
              <el-button size="small" text @click="resetColumns">
                重置
              </el-button>
            </div>
            <div class="column-list">
              <div 
                v-for="(col, index) in allColumns" 
                :key="col.prop"
                class="column-item"
              >
                <el-icon v-if="col.fixed" class="fixed-icon"><Lock /></el-icon>
                <el-checkbox 
                  v-model="visibleColumns" 
                  :value="col.prop"
                  :disabled="col.fixed"
                >
                  {{ col.label }}
                </el-checkbox>
                <el-tag v-if="col.sortable" size="small" type="info">可排序</el-tag>
              </div>
            </div>
          </div>
        </el-popover>
        
        <el-button 
          :icon="refreshing ? Loading : Refresh" 
          circle 
          title="刷新" 
          :loading="refreshing"
          @click="handleRefresh" 
        />
      </div>
    </div>
    
    <el-table
      v-loading="loading"
      element-loading-text="正在加载数据..."
      :data="paginatedData"
      :border="border"
      stripe
      highlight-current-row
      :row-key="rowKey"
      class="smart-table-main"
      empty-text="暂无数据，请先导入或添加数据"
      @selection-change="handleSelectionChange"
      @sort-change="handleSortChange"
      v-bind="$attrs"
    >
      <el-table-column v-if="selection" type="selection" width="55" fixed="left" />
      
      <el-table-column v-if="indexColumn" type="index" label="序号" width="60" fixed="left" />
      
      <template v-for="col in filteredColumns" :key="col.prop">
        <el-table-column
          :prop="col.prop"
          :label="col.label"
          :width="getColumnWidth(col.prop)"
          :min-width="col.minWidth || 100"
          :fixed="col.fixed"
          :sortable="col.sortable"
          :formatter="col.formatter"
          :align="col.align || 'left'"
          :show-overflow-tooltip="col.showTooltip !== false"
        >
          <template v-if="col.slot" #default="scope">
            <slot :name="col.slot" :row="scope.row" :index="scope.$index"></slot>
          </template>
          <template v-else-if="col.render" #default="scope">
            <component :is="col.render(scope.row, scope.$index)" />
          </template>
        </el-table-column>
      </template>
      
      <el-table-column v-if="$slots.default" v-bind="$attrs">
        <slot></slot>
      </el-table-column>
      
      <el-table-column v-if="operationColumn" label="操作" :width="operationWidth" fixed="right" align="center">
        <template #default="scope">
          <slot name="operation" :row="scope.row" :index="scope.$index"></slot>
        </template>
      </el-table-column>
    </el-table>
    
    <div class="smart-table-footer" v-if="showPagination">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="currentPageSize"
        :page-sizes="pageSizes"
        :total="filteredData.length"
        :layout="paginationLayout"
        background
        @size-change="handleSizeChange"
        @current-change="handlePageChange"
      />
    </div>
    
    <div v-if="selectedRows.length > 0 && selection" class="smart-table-selection-bar">
      <el-alert
        :title="`已选择 ${selectedRows.length} 项`"
        type="info"
        :closable="false"
        show-icon
      >
        <template #default>
          <slot name="selection-actions" :selected="selectedRows"></slot>
          <el-button size="small" text @click="clearSelection">
            取消选择
          </el-button>
        </template>
      </el-alert>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { 
  Setting, Refresh, Download, Search, ArrowDown, 
  Lock, Loading 
} from '@element-plus/icons-vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  columns: { type: Array, default: null },
  total: { type: Number, default: 0 },
  currentPage: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
  pageSizes: { type: Array, default: () => [10, 20, 50, 100] },
  searchable: { type: Boolean, default: true },
  exportable: { type: Boolean, default: false },
  supportExcel: { type: Boolean, default: false },
  selection: { type: Boolean, default: false },
  border: { type: Boolean, default: true },
  rowKey: { type: String, default: 'id' },
  showPagination: { type: Boolean, default: true },
  paginationLayout: { type: String, default: 'total, sizes, prev, pager, next, jumper' },
  indexColumn: { type: Boolean, default: false },
  operationColumn: { type: Boolean, default: false },
  operationWidth: { type: Number, default: 150 },
  searchDelay: { type: Number, default: 300 },
})

const emit = defineEmits([
  'refresh', 
  'export', 
  'size-change', 
  'page-change', 
  'search',
  'selection-change',
  'sort-change'
])

const searchText = ref('')
const currentPage = ref(props.currentPage)
const currentPageSize = ref(props.pageSize)
const visibleColumns = ref(props.columns ? props.columns.map(c => c.prop) : [])
const selectedRows = ref([])
const refreshing = ref(false)
const activeFilters = ref([])
const sortState = ref({ prop: null, order: null })
let searchTimer = null

const allColumns = computed(() => props.columns || [])
const filterColumns = computed(() => {
  return props.columns?.filter(c => c.filterable) || []
})

const filteredColumns = computed(() => {
  if (!props.columns) return []
  return props.columns.filter(c => visibleColumns.value.includes(c.prop))
})

const allColumnsSelected = computed({
  get() {
    return visibleColumns.value.length === props.columns?.length
  },
  set(val) {
    if (val) {
      visibleColumns.value = props.columns.map(c => c.prop)
    }
  }
})

const filteredData = computed(() => {
  let result = [...props.data]
  
  if (searchText.value) {
    const keyword = searchText.value.toLowerCase()
    result = result.filter(row => {
      return Object.values(row).some(val => 
        String(val).toLowerCase().includes(keyword)
      )
    })
  }
  
  if (sortState.value.prop && sortState.value.order) {
    const { prop, order } = sortState.value
    result.sort((a, b) => {
      const valA = a[prop] ?? 0
      const valB = b[prop] ?? 0
      return order === 'ascending' ? valA - valB : valB - valA
    })
  }
  
  return result
})

const paginatedData = computed(() => {
  if (!props.showPagination) return filteredData.value
  const start = (currentPage.value - 1) * currentPageSize.value
  return filteredData.value.slice(start, start + currentPageSize.value)
})

function debouncedSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    emit('search', searchText.value)
    currentPage.value = 1
  }, props.searchDelay)
}

function applyFilters() {
  emit('search', { text: searchText.value, filters: activeFilters.value })
  currentPage.value = 1
}

function handleRefresh() {
  refreshing.value = true
  emit('refresh')
  setTimeout(() => {
    refreshing.value = false
  }, 500)
}

function handleExport(format) {
  ElMessage.success(`正在导出为 ${format.toUpperCase()} 格式...`)
  emit('export', format, filteredData.value)
}

function toggleAllColumns() {
  if (allColumnsSelected.value) {
    visibleColumns.value = props.columns
      .filter(c => c.fixed)
      .map(c => c.prop)
  } else {
    visibleColumns.value = props.columns.map(c => c.prop)
  }
}

function resetColumns() {
  visibleColumns.value = props.columns.map(c => c.prop)
  ElMessage.success('列设置已重置')
}

function getColumnWidth(prop) {
  const col = props.columns?.find(c => c.prop === prop)
  return col?.width || undefined
}

function handleSelectionChange(selection) {
  selectedRows.value = selection
  emit('selection-change', selection)
}

function clearSelection() {
  selectedRows.value = []
  emit('selection-change', [])
}

function handleSortChange({ prop, order }) {
  sortState.value = { prop, order }
  emit('sort-change', { prop, order })
}

function handleSizeChange(size) {
  emit('size-change', size)
}

function handlePageChange(page) {
  emit('page-change', page)
}

watch(() => props.currentPage, (v) => { currentPage.value = v })
watch(() => props.pageSize, (v) => { currentPageSize.value = v })
</script>

<style scoped>
.smart-table {
  background: white;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.smart-table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}

.toolbar-left, .toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.table-search {
  width: 250px;
}

.table-filter {
  width: 180px;
}

.result-count {
  font-size: 13px;
  color: #909399;
  margin-left: 8px;
}

.column-settings {
  max-height: 400px;
  overflow-y: auto;
}

.settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #ebeef5;
  margin-bottom: 8px;
}

.column-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.column-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.fixed-icon {
  color: #e6a23c;
  font-size: 12px;
}

.smart-table-main {
  border-radius: 8px;
  overflow: hidden;
}

.smart-table-footer {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.smart-table-selection-bar {
  margin-top: 12px;
}

:deep(.el-pagination) {
  justify-content: flex-end;
}

:deep(.dark) .smart-table {
  background: #1f1f1f;
}

:deep(.dark) .settings-header {
  border-bottom-color: #333;
}

:deep(.dark) .result-count {
  color: #8c8c8c;
}
</style>
