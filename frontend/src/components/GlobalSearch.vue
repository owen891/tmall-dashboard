<template>
  <div class="global-search">
    <el-input
      ref="searchInputRef"
      v-model="searchText"
      placeholder="搜索商品、功能... (Ctrl+K)"
      :prefix-icon="Search"
      clearable
      @focus="showDropdown = true"
      @blur="handleBlur"
      @input="handleSearch"
      @keydown="handleKeydown"
    />
    
    <teleport to="body">
      <div v-if="showDropdown && (filteredPages.length > 0 || filteredProducts.length > 0)" class="search-dropdown">
        <div v-if="filteredPages.length > 0" class="search-section">
          <div class="section-title">功能页面</div>
          <div 
            v-for="(page, index) in filteredPages" 
            :key="page.path"
            class="search-item"
            :class="{ active: activeIndex === index }"
            @mousedown="goToPage(page.path)"
          >
            <el-icon><component :is="page.icon" /></el-icon>
            <span>{{ page.title }}</span>
          </div>
        </div>
        
        <div v-if="filteredProducts.length > 0" class="search-section">
          <div class="section-title">商品</div>
          <div 
            v-for="(product, index) in filteredProducts" 
            :key="product.product_id"
            class="search-item product-item"
            :class="{ active: activeIndex === filteredPages.length + index }"
            @mousedown="goToProduct(product)"
          >
            <el-image :src="product.image_url || defaultImage" class="product-image" />
            <div class="product-info">
              <div class="product-title">{{ product.title }}</div>
              <div class="product-meta">{{ product.tier }} · {{ product.style }}</div>
            </div>
          </div>
        </div>
        
        <div v-if="searchText && filteredPages.length === 0 && filteredProducts.length === 0" class="search-empty">
          <el-icon><Search /></el-icon>
          <span>未找到相关结果</span>
        </div>
      </div>
    </teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { Search, DataBoard, Goods, TrendCharts, Tools, DataAnalysis, Setting, Odometer, Trophy } from '@element-plus/icons-vue'
import api from '@/api'

const router = useRouter()
const searchText = ref('')
const showDropdown = ref(false)
const searchInputRef = ref(null)
const activeIndex = ref(0)
const products = ref([])

const defaultImage = 'https://via.placeholder.com/40x40/f0f2f5/909399?text=商'

// 可搜索的页面列表
const pages = [
  { path: '/', title: '指挥塔', icon: 'DataBoard', keywords: ['首页', '仪表盘', 'dashboard'] },
  { path: '/products', title: '商品列表', icon: 'Goods', keywords: ['商品', '产品', 'product'] },
  { path: '/lifecycle', title: '生命周期', icon: 'Odometer', keywords: ['生命周期', 'lifecycle'] },
  { path: '/profit', title: '利润分析', icon: 'DataAnalysis', keywords: ['利润', 'profit'] },
  { path: '/traffic-analysis', title: '流量分析', icon: 'TrendCharts', keywords: ['流量', 'traffic'] },
  { path: '/ads', title: '广告投放', icon: 'Tools', keywords: ['广告', 'ads', '推广'] },
  { path: '/kpi', title: 'KPI管理', icon: 'Trophy', keywords: ['kpi', '指标', '绩效'] },
  { path: '/trends', title: '趋势分析', icon: 'TrendCharts', keywords: ['趋势', 'trend'] },
  { path: '/health', title: '健康度分析', icon: 'DataAnalysis', keywords: ['健康', 'health'] },
  { path: '/settings', title: '系统设置', icon: 'Setting', keywords: ['设置', 'setting'] }
]

// 过滤页面
const filteredPages = computed(() => {
  if (!searchText.value) return []
  const query = searchText.value.toLowerCase()
  return pages.filter(p => 
    p.title.toLowerCase().includes(query) ||
    p.keywords.some(k => k.includes(query))
  )
})

// 过滤商品
const filteredProducts = computed(() => {
  if (!searchText.value) return []
  const query = searchText.value.toLowerCase()
  return products.value.filter(p => 
    p.title?.toLowerCase().includes(query) ||
    p.product_id?.toString().includes(query)
  ).slice(0, 5)
})

// 搜索商品
let searchTimer = null
const handleSearch = () => {
  activeIndex.value = 0
  if (searchTimer) clearTimeout(searchTimer)
  if (searchText.value.length >= 2) {
    searchTimer = setTimeout(async () => {
      try {
        const res = await api.getProducts({ search: searchText.value, limit: 10 })
        products.value = res.data?.data || []
      } catch (e) {
        console.error('Search error:', e)
      }
    }, 300)
  } else {
    products.value = []
  }
}

// 键盘导航
const handleKeydown = (e) => {
  const total = filteredPages.value.length + filteredProducts.value.length
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex.value = (activeIndex.value + 1) % total
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value = (activeIndex.value - 1 + total) % total
  } else if (e.key === 'Enter') {
    e.preventDefault()
    selectActiveItem()
  } else if (e.key === 'Escape') {
    showDropdown.value = false
  }
}

// 选择当前项
const selectActiveItem = () => {
  if (activeIndex.value < filteredPages.value.length) {
    goToPage(filteredPages.value[activeIndex.value].path)
  } else {
    const productIndex = activeIndex.value - filteredPages.value.length
    if (filteredProducts.value[productIndex]) {
      goToProduct(filteredProducts.value[productIndex])
    }
  }
}

// 跳转页面
const goToPage = (path) => {
  router.push(path)
  showDropdown.value = false
  searchText.value = ''
}

// 跳转商品详情
const goToProduct = (product) => {
  router.push(`/product/${product.product_id}`)
  showDropdown.value = false
  searchText.value = ''
}

// 处理失焦
const handleBlur = () => {
  setTimeout(() => {
    showDropdown.value = false
  }, 200)
}

// 全局快捷键
const handleGlobalKeydown = (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault()
    searchInputRef.value?.focus()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleGlobalKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleGlobalKeydown)
})
</script>

<style scoped>
.global-search {
  width: 280px;
}

.global-search :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: none;
}

.global-search :deep(.el-input__inner) {
  color: #fff;
}

.global-search :deep(.el-input__inner::placeholder) {
  color: rgba(255, 255, 255, 0.6);
}

.global-search :deep(.el-input__prefix) {
  color: rgba(255, 255, 255, 0.6);
}

.search-dropdown {
  position: fixed;
  top: 60px;
  left: 50%;
  transform: translateX(-50%);
  width: 480px;
  max-height: 400px;
  overflow-y: auto;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
  z-index: 9999;
  padding: 8px 0;
}

.search-section {
  padding: 8px 0;
}

.section-title {
  padding: 8px 16px;
  font-size: 12px;
  color: #909399;
  font-weight: 500;
}

.search-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.2s;
}

.search-item:hover,
.search-item.active {
  background: #f5f7fa;
}

.search-item .el-icon {
  font-size: 18px;
  color: #409eff;
}

.product-item {
  gap: 12px;
}

.product-image {
  width: 40px;
  height: 40px;
  border-radius: 6px;
  flex-shrink: 0;
}

.product-info {
  flex: 1;
  min-width: 0;
}

.product-title {
  font-size: 14px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-meta {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.search-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px;
  color: #909399;
}
</style>
