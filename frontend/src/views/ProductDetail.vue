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
        <el-tab-pane label="生意参谋" name="shengyi">
          <ShengyiData :product-id="productId" :data="shengyiData" />
        </el-tab-pane>
        <el-tab-pane label="营销推广" name="marketing">
          <MarketingData :product-id="productId" :data="marketingData" />
        </el-tab-pane>
        <el-tab-pane label="付费报表" name="paid">
          <PaidReport :product-id="productId" :data="paidData" />
        </el-tab-pane>
        <el-tab-pane label="生命周期GSV" name="lifecycle">
          <LifecycleGsv :product-id="productId" :data="lifecycleData" />
        </el-tab-pane>
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
import ShengyiData from '@/components/product/ShengyiData.vue'
import MarketingData from '@/components/product/MarketingData.vue'
import PaidReport from '@/components/product/PaidReport.vue'
import LifecycleGsv from '@/components/product/LifecycleGsv.vue'

const route = useRoute()
const router = useRouter()
const productId = route.params.id

const product = ref({})
const latestData = ref({})
const kpis = ref([])
const shengyiData = ref({})
const marketingData = ref({})
const paidData = ref({})
const lifecycleData = ref({})
const activeDetailTab = ref('shengyi')

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
    const res = await api.getProductDetail(productId)
    const productData = res.data || {}
    product.value = {
      product_id: productData.product_id,
      title: productData.title,
      image_url: productData.image_url,
      category: productData.category,
      tier: productData.tier,
      style: productData.style,
      scene: productData.scene,
      manager: productData.manager,
      list_date: productData.list_date,
      status: productData.status,
      starred: productData.starred,
      operations: productData.operations || '4月C周复盘'
    }

    const trendList = productData.trend || []
    if (trendList.length > 0) {
      const latest = trendList[trendList.length - 1]
      latestData.value = latest

      // 生成 KPI 数据
      kpis.value = [
        { key: 'visitors', label: '访客数', value: formatNumber(latest.visitors || 0) },
        { key: 'gmv', label: '销售额', value: formatCurrency(latest.payment_amount || 0) },
        { key: 'roi', label: 'ROI', value: latest.roi || '-' },
        { key: 'conversion', label: '转化率', value: (latest.conversion || 0) + '%' }
      ]
    }

    // 设置各模块数据（模拟数据）
    shengyiData.value = productData.shengyi || {
      visitors: 12345,
      pageViews: 23456,
      conversion: 3.2,
      payAmount: 123456,
      trend: trendList
    }

    marketingData.value = productData.marketing || {
      marketingIpv: 5678,
      marketingCost: 8900,
      marketingRoi: 3.5,
      repurchaseRate: 12.5,
      searchIpv: 7890,
      unitPrice: 128
    }

    paidData.value = productData.paid || {
      impressions: 100000,
      clicks: 3200,
      cost: 5000,
      ctr: 3.2,
      roi: 3.8,
      totalAmount: 19000
    }

    lifecycleData.value = productData.lifecycle || {}
  } catch (error) {
    ElMessage.error('加载失败')
  }
}

const formatCurrency = (val) => {
  if (!val) return '¥0'
  return '¥' + Number(val).toLocaleString()
}

const formatNumber = (num) => {
  if (!num && num !== 0) return '0'
  return Number(num).toLocaleString()
}

const getTierType = (tier) => {
  const types = { '引流款': 'primary', '利润款': 'success', '形象款': 'warning' }
  return types[tier] || 'info'
}

onMounted(() => loadData())
</script>

<style scoped>
.product-detail {
  padding: 20px;
}
</style>
