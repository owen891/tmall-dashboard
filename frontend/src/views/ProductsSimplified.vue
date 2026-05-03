<template>
  <div class="products-page">
    <div class="page-header">
      <div class="header-left">
        <h2>📦 商品矩阵</h2>
        <span class="subtitle">商品分析与库存管理</span>
      </div>
      <div class="header-right">
        <el-input v-model="searchKeyword" placeholder="搜索商品" style="width: 240px" clearable />
        <el-select v-model="selectedTier" placeholder="商品分层" clearable style="width: 140px">
          <el-option label="引流款" value="引流款" />
          <el-option label="利润款" value="利润款" />
          <el-option label="潜力款" value="潜力款" />
        </el-select>
        <el-button type="primary" @click="refresh">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-icon" style="background: #409eff">📊</div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.totalProducts }}</div>
            <div class="stat-label">商品总数</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-icon" style="background: #67c23a">💰</div>
          <div class="stat-content">
            <div class="stat-value">¥{{ formatNumber(stats.totalSales) }}</div>
            <div class="stat-label">总销售额</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-icon" style="background: #e6a23c">⚠️</div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.lowStockCount }}</div>
            <div class="stat-label">库存告急</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-icon" style="background: #f56c6c">💀</div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.slowMovingCount }}</div>
            <div class="stat-label">滞销商品</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="content-section">
      <el-tabs v-model="activeTab" type="card" class="content-tabs">
        <el-tab-pane label="商品列表" name="list">
          <div class="table-container">
            <el-table :data="products" stripe style="width: 100%">
              <el-table-column type="index" label="排名" width="60" align="center" />
              <el-table-column prop="title" label="商品名称" min-width="280" />
              <el-table-column prop="tier" label="分层" width="100">
                <template #default="{ row }">
                  <el-tag :type="getTierType(row.tier)">{{ row.tier || '未分类' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="sales" label="销售额" width="120" align="right">
                <template #default="{ row }">
                  ¥{{ formatNumber(row.sales) }}
                </template>
              </el-table-column>
              <el-table-column prop="stock" label="库存" width="100" align="right">
                <template #default="{ row }">
                  <el-tag :type="getStockType(row.stock, row.safetyStock)">
                    {{ row.stock }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="conversion" label="转化率" width="100" align="right">
                <template #default="{ row }">
                  {{ row.conversion ? (row.conversion * 100).toFixed(2) : 0 }}%
                </template>
              </el-table-column>
              <el-table-column label="操作" width="140">
                <template #default="{ row }">
                  <el-button size="small" type="primary" text @click="viewDetail(row)">
                    详情
                  </el-button>
                  <el-button size="small" text @click="editProduct(row)">
                    编辑
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <el-tab-pane label="库存预警" name="stock">
          <div class="table-container">
            <el-table :data="stockAlerts" stripe style="width: 100%">
              <el-table-column type="index" label="序号" width="60" align="center" />
              <el-table-column prop="title" label="商品名称" min-width="280" />
              <el-table-column prop="sku" label="SKU" width="140" />
              <el-table-column prop="currentStock" label="当前库存" width="120" align="right" />
              <el-table-column prop="safetyStock" label="安全库存" width="120" align="right" />
              <el-table-column prop="daysLeft" label="预计可售" width="100" align="right">
                <template #default="{ row }">
                  {{ row.daysLeft }}天
                </template>
              </el-table-column>
              <el-table-column prop="level" label="预警级别" width="120">
                <template #default="{ row }">
                  <el-tag :type="getAlertType(row.level)">{{ row.level }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="120">
                <template #default="{ row }">
                  <el-button size="small" type="primary" text>
                    补货
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

const router = useRouter()
const activeTab = ref('list')
const searchKeyword = ref('')
const selectedTier = ref('')

const stats = reactive({
  totalProducts: 156,
  totalSales: 4567890,
  lowStockCount: 12,
  slowMovingCount: 5
})

const products = ref([
  { id: 1, title: '中古风玄关装饰摆件', tier: '利润款', sales: 87654, stock: 86, safetyStock: 100, conversion: 0.032 },
  { id: 2, title: '入户玄关装饰品钟馗财神爷摆件', tier: '引流款', sales: 76543, stock: 234, safetyStock: 100, conversion: 0.028 },
  { id: 3, title: '中古风玄关装饰摆件放钥匙收纳', tier: '利润款', sales: 54321, stock: 45, safetyStock: 50, conversion: 0.041 },
  { id: 4, title: '现代简约客厅装饰画', tier: '潜力款', sales: 43210, stock: 67, safetyStock: 50, conversion: 0.035 },
  { id: 5, title: '北欧风电视柜组合', tier: '利润款', sales: 32109, stock: 12, safetyStock: 20, conversion: 0.038 }
])

const stockAlerts = ref([
  { id: 1, title: '中古风玄关装饰摆件放钥匙收纳', sku: 'ABC-001', currentStock: 45, safetyStock: 50, daysLeft: 8, level: '蓝色预警' },
  { id: 2, title: '北欧风电视柜组合', sku: 'ABC-002', currentStock: 12, safetyStock: 20, daysLeft: 2, level: '红色预警' },
  { id: 3, title: '中古风玄关装饰摆件', sku: 'ABC-003', currentStock: 86, safetyStock: 100, daysLeft: 15, level: '绿色' }
])

const formatNumber = (num) => {
  if (!num && num !== 0) return '0'
  num = Number(num)
  if (num >= 10000) return (num / 10000).toFixed(2) + '万'
  return num.toLocaleString()
}

const getTierType = (tier) => {
  const types = { '引流款': 'success', '利润款': 'primary', '潜力款': 'warning' }
  return types[tier] || 'info'
}

const getStockType = (stock, safetyStock) => {
  if (stock < safetyStock * 0.5) return 'danger'
  if (stock < safetyStock) return 'warning'
  return 'success'
}

const getAlertType = (level) => {
  const types = { '红色预警': 'danger', '蓝色预警': 'warning', '绿色': 'success' }
  return types[level] || 'info'
}

const refresh = () => ElMessage.success('数据已刷新')

const viewDetail = (product) => {
  router.push(`/product/${product.id}`)
}

const editProduct = (product) => {
  ElMessage.info(`编辑商品: ${product.title}`)
}
</script>

<style scoped>
.products-page {
  padding: 20px;
  background: #f5f7fa;
  min-height: 100%;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  background: white;
  padding: 20px 24px;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.header-left h2 {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 4px 0;
  color: #303133;
}

.subtitle {
  font-size: 14px;
  color: #909399;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stats-row {
  margin-bottom: 24px;
}

.stat-card {
  display: flex;
  align-items: center;
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  margin-right: 16px;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #303133;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.content-section {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.content-tabs {
  margin-bottom: 20px;
}

.table-container {
  min-height: 400px;
}
</style>
