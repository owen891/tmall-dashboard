<template>
  <div class="product-detail">
    <el-page-header @back="goBack" content="商品详情" />

    <!-- 产品头部信息 -->
    <ProductHeader
      :product="product"
      @toggle-star="toggleStar"
    />

    <!-- KPI 指标卡片 -->
    <KPICards :kpis="kpis" />

    <!-- 数据详情标签页 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <span>数据详情</span>
      </template>
      <el-tabs v-model="activeDetailTab" type="card">
        <el-tab-pane label="流量来源" name="traffic">
          <TrafficSources :data="latestData" />
        </el-tab-pane>
        <el-tab-pane label="销售趋势" name="sales">
          <SalesChart :product-id="productId" />
        </el-tab-pane>
        <el-tab-pane label="运营动作" name="operations">
          <OperationsLog :product-id="productId" />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'
import ProductHeader from '@/components/product/ProductHeader.vue'
import KPICards from '@/components/product/KPICards.vue'
import TrafficSources from '@/components/product/TrafficSources.vue'
import SalesChart from '@/components/product/SalesChart.vue'
import OperationsLog from '@/components/product/OperationsLog.vue'

const route = useRoute()
const router = useRouter()
const productId = route.params.id

const product = ref({})
const latestData = ref({})
const kpis = ref([])
const activeDetailTab = ref('traffic')

const goBack = () => router.push('/products')

const toggleStar = async () => {
  try {
    await api.updateProduct(productId, { starred: !product.value.starred })
    product.value.starred = !product.value.starred
    ElMessage.success(product.value.starred ? '已收藏' : '已取消收藏')
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const loadData = async () => {
  try {
    const res = await api.getProduct(productId)
    product.value = res.data || {}

    const detailRes = await api.getProductDetail(productId)
    latestData.value = detailRes.data || {}

    // 生成 KPI 数据
    kpis.value = [
      { key: 'ipv', label: '访客数', value: latestData.value.visitors || 0 },
      { key: 'gmv', label: '销售额', value: formatCurrency(latestData.value.gmv) },
      { key: 'roi', label: 'ROI', value: latestData.value.roi || '-' },
      { key: 'conversion', label: '转化率', value: (latestData.value.conversion_rate || 0) + '%' }
    ]
  } catch (error) {
    ElMessage.error('加载失败')
  }
}

const formatCurrency = (val) => {
  if (!val) return '¥0'
  return '¥' + Number(val).toLocaleString()
}

const getTierType = (tier) => {
  const types = { 'A': 'success', 'B': 'warning', 'C': 'danger' }
  return types[tier] || 'info'
}

onMounted(() => loadData())
</script>

<style scoped>
.product-detail {
  padding: 20px;
}
</style>
