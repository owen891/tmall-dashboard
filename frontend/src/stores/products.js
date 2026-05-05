import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import productsApi from '@/api/products'

export const useProductsStore = defineStore('products', () => {
  const products = ref([])
  const currentProduct = ref(null)
  const filterOptions = ref({})
  const loading = ref(false)
  const error = ref(null)
  const total = ref(0)
  const currentPage = ref(1)
  const pageSize = ref(20)

  const totalPages = computed(() => Math.ceil(total.value / pageSize.value))

  async function fetchProducts(params = {}) {
    loading.value = true
    error.value = null
    try {
      const response = await productsApi.getList({
        page: currentPage.value,
        page_size: pageSize.value,
        ...params
      })
      products.value = response.data?.data || []
      total.value = response.data?.total || 0
      return response
    } catch (err) {
      error.value = err.message || '获取商品列表失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchFilterOptions() {
    try {
      const response = await productsApi.getFilterOptions()
      filterOptions.value = response.data || {}
    } catch (err) {
      console.error('获取筛选选项失败:', err)
    }
  }

  async function fetchProductDetail(productId, params = {}) {
    loading.value = true
    error.value = null
    try {
      const response = await productsApi.getDetail(productId, params)
      currentProduct.value = response.data || null
      return response
    } catch (err) {
      error.value = err.message || '获取商品详情失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function updateProductField(productId, field, value) {
    try {
      await productsApi.updateField(productId, field, value)
      if (currentProduct.value?.product_id === productId) {
        currentProduct.value[field] = value
      }
    } catch (err) {
      error.value = err.message || '更新商品失败'
      throw err
    }
  }

  function setPage(page) {
    currentPage.value = page
  }

  function setPageSize(size) {
    pageSize.value = size
    currentPage.value = 1
  }

  function reset() {
    products.value = []
    currentProduct.value = null
    total.value = 0
    currentPage.value = 1
    error.value = null
  }

  return {
    products,
    currentProduct,
    filterOptions,
    loading,
    error,
    total,
    currentPage,
    pageSize,
    totalPages,
    fetchProducts,
    fetchFilterOptions,
    fetchProductDetail,
    updateProductField,
    setPage,
    setPageSize,
    reset
  }
})
