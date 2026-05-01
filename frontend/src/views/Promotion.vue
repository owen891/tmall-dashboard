<template>
  <div class="promotion-analysis">
    <el-card class="filter-card">
      <div class="filter-row">
        <div class="filter-left">
          <el-button-group>
            <el-button :type="dataSource === 'cloud' ? 'primary' : 'default'" @click="dataSource = 'cloud'">云端</el-button>
            <el-button :type="dataSource === 'local' ? 'primary' : 'default'" @click="dataSource = 'local'">本地</el-button>
          </el-button-group>
        </div>
        
        <div class="filter-center">
          <span class="date-label">统计时间:</span>
          <el-date-picker
            v-model="selectedDate"
            type="date"
            placeholder="选择日期"
            size="small"
          />
          <el-button-group size="small">
            <el-button @click="setDateRange('7d')">7天</el-button>
            <el-button @click="setDateRange('30d')">30天</el-button>
            <el-button @click="setDateRange('day')">日</el-button>
            <el-button @click="setDateRange('week')">周</el-button>
            <el-button @click="setDateRange('month')">月</el-button>
            <el-button @click="showCustomDate = true">自定义</el-button>
          </el-button-group>
        </div>
        
        <div class="filter-right">
          <span class="margin-label">单品毛利率:</span>
          <el-input v-model="grossMargin" type="number" size="small" style="width: 80px;" />
          <span class="percent-label">%</span>
          <el-button type="primary" size="small" @click="applyGrossMargin">确定</el-button>
          <el-button size="small" @click="exportData">导出</el-button>
          <el-button size="small" @click="showMoreData = true">更多数据</el-button>
        </div>
      </div>
      
      <div class="channel-row">
        <el-select v-model="selectedChannel" placeholder="选择渠道" size="small" class="channel-select">
          <el-option label="淘系" value="taobao" />
          <el-option label="天猫" value="tmall" />
          <el-option label="京东" value="jd" />
          <el-option label="拼多多" value="pinduoduo" />
          <el-option label="抖音" value="douyin" />
        </el-select>
        <el-select v-model="selectedShop" placeholder="选择店铺" size="small" class="shop-select">
          <el-option label="全部店铺" value="all" />
          <el-option label="旗舰店" value="flagship" />
          <el-option label="专营店" value="specialty" />
        </el-select>
        <el-button icon="Search" size="small" />
      </div>
    </el-card>

    <el-card class="main-card">
      <div class="card-header">
        <el-tabs v-model="activeTab" type="card" @tab-click="handleTabChange">
          <el-tab-pane label="推广总览" name="overview">
          </el-tab-pane>
          <el-tab-pane label="搜索拉升效率分析" name="search-efficiency">
          </el-tab-pane>
        </el-tabs>
      </div>

      <div v-if="activeTab === 'overview'" class="tab-content">
        <div class="left-panel">
          <div class="panel-header">
            <span class="panel-title">商品</span>
            <div class="filter-tags">
              <el-checkbox v-model="filterTags.self" label="自己" />
              <el-checkbox v-model="filterTags.new" label="新品" />
              <el-checkbox v-model="filterTags.follow" label="跟进" />
              <el-checkbox v-model="filterTags.pending" label="待办" />
            </div>
          </div>
          
          <div class="product-list">
            <div v-if="filteredProducts.length === 0" class="empty-state">
              <div class="empty-icon">
                <el-icon size="48"><Files /></el-icon>
              </div>
              <p>暂无相关数据</p>
            </div>
            <el-tree
              v-else
              :data="productTree"
              :props="treeProps"
              default-expand-all
              :highlight-current="true"
              @node-click="handleProductSelect"
            />
          </div>
        </div>

        <div class="right-panel">
          <div class="table-container">
            <el-table 
              :data="promotionPlans" 
              stripe 
              size="small"
              :cell-style="{ padding: '8px 12px' }"
              @selection-change="handleSelectionChange"
            >
              <el-table-column type="selection" width="40" />
              <el-table-column prop="name" label="计划名称" min-width="150" />
              <el-table-column prop="channel" label="推广渠道" width="100">
                <template #default="{ row }">
                  <el-tag :type="getChannelType(row.channel)">{{ row.channel }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="80">
                <template #default="{ row }">
                  <el-tag :type="getStatusType(row.status)">{{ row.status }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="planId" label="计划ID" width="100" />
              <el-table-column prop="type" label="计划类型" width="100" />
              <el-table-column prop="cost" label="推广花费" width="100" align="right">
                <template #default="{ row }">¥{{ row.cost.toLocaleString() }}</template>
              </el-table-column>
              <el-table-column prop="revenue" label="成交金额" width="100" align="right">
                <template #default="{ row }">¥{{ row.revenue.toLocaleString() }}</template>
              </el-table-column>
              <el-table-column prop="roi" label="ROI" width="80" align="right">
                <template #default="{ row }">
                  <span :class="row.roi >= 1 ? 'text-success' : 'text-danger'">{{ row.roi.toFixed(2) }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="avgCpc" label="平均点击单价" width="100" align="right">
                <template #default="{ row }">¥{{ row.avgCpc.toFixed(2) }}</template>
              </el-table-column>
            </el-table>
          </div>

          <div v-if="selectedPlan" class="plan-detail">
            <div class="detail-header">
              <span class="detail-title">计划详情</span>
            </div>
            <div class="detail-content">
              <el-descriptions :column="3" border size="small">
                <el-descriptions-item label="计划名称">{{ selectedPlan.name }}</el-descriptions-item>
                <el-descriptions-item label="计划ID">{{ selectedPlan.planId }}</el-descriptions-item>
                <el-descriptions-item label="推广渠道">{{ selectedPlan.channel }}</el-descriptions-item>
                <el-descriptions-item label="计划类型">{{ selectedPlan.type }}</el-descriptions-item>
                <el-descriptions-item label="状态">{{ selectedPlan.status }}</el-descriptions-item>
                <el-descriptions-item label="创建时间">{{ selectedPlan.createTime }}</el-descriptions-item>
                <el-descriptions-item label="推广花费">¥{{ selectedPlan.cost.toLocaleString() }}</el-descriptions-item>
                <el-descriptions-item label="成交金额">¥{{ selectedPlan.revenue.toLocaleString() }}</el-descriptions-item>
                <el-descriptions-item label="ROI">{{ selectedPlan.roi.toFixed(2) }}</el-descriptions-item>
                <el-descriptions-item label="点击量">{{ selectedPlan.clicks }}</el-descriptions-item>
                <el-descriptions-item label="展现量">{{ selectedPlan.impressions }}</el-descriptions-item>
                <el-descriptions-item label="转化率">{{ (selectedPlan.conversionRate * 100).toFixed(2) }}%</el-descriptions-item>
              </el-descriptions>
            </div>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'search-efficiency'" class="tab-content">
        <div class="efficiency-content">
          <div class="summary-cards">
            <el-card class="summary-card">
              <div class="card-icon search-icon">
                <el-icon size="24"><Search /></el-icon>
              </div>
              <div class="card-info">
                <p class="card-value">{{ searchStats.totalSearches.toLocaleString() }}</p>
                <p class="card-label">搜索总次数</p>
              </div>
            </el-card>
            <el-card class="summary-card">
              <div class="card-icon click-icon">
                <el-icon size="24"><Mouse /></el-icon>
              </div>
              <div class="card-info">
                <p class="card-value">{{ searchStats.clickRate.toFixed(2) }}%</p>
                <p class="card-label">点击率</p>
              </div>
            </el-card>
            <el-card class="summary-card">
              <div class="card-icon conversion-icon">
                <el-icon size="24"><ArrowUp /></el-icon>
              </div>
              <div class="card-info">
                <p class="card-value">{{ searchStats.conversionRate.toFixed(2) }}%</p>
                <p class="card-label">转化率</p>
              </div>
            </el-card>
            <el-card class="summary-card">
              <div class="card-icon growth-icon">
                <el-icon size="24"><TrendCharts /></el-icon>
              </div>
              <div class="card-info">
                <p class="card-value">{{ searchStats.growthRate > 0 ? '+' : '' }}{{ searchStats.growthRate.toFixed(2) }}%</p>
                <p class="card-label">同比增长</p>
              </div>
            </el-card>
          </div>

          <div class="chart-section">
            <el-card>
              <template #header>搜索趋势</template>
              <div ref="searchChartRef" class="chart-container"></div>
            </el-card>
          </div>

          <div class="keyword-table">
            <el-card>
              <template #header>关键词排名</template>
              <el-table 
                :data="keywordRanking" 
                stripe 
                size="small"
              >
                <el-table-column prop="rank" label="排名" width="60" />
                <el-table-column prop="keyword" label="关键词" min-width="150" />
                <el-table-column prop="searches" label="搜索次数" width="100" align="right" />
                <el-table-column prop="clickRate" label="点击率" width="100" align="right">
                  <template #default="{ row }">{{ row.clickRate.toFixed(2) }}%</template>
                </el-table-column>
                <el-table-column prop="conversionRate" label="转化率" width="100" align="right">
                  <template #default="{ row }">{{ row.conversionRate.toFixed(2) }}%</template>
                </el-table-column>
                <el-table-column prop="trend" label="趋势" width="80">
                  <template #default="{ row }">
                    <el-icon v-if="row.trend > 0" class="text-success"><ArrowUp /></el-icon>
                    <el-icon v-else-if="row.trend < 0" class="text-danger"><ArrowDown /></el-icon>
                    <el-icon v-else class="text-gray"><Minus /></el-icon>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </div>
        </div>
      </div>
    </el-card>

    <el-dialog v-model="showCustomDate" title="自定义时间范围" width="400px">
      <el-date-picker
        v-model="customDateRange"
        type="daterange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
      />
      <div slot="footer" class="dialog-footer">
        <el-button @click="showCustomDate = false">取消</el-button>
        <el-button type="primary" @click="applyCustomDate">确定</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Mouse, ArrowUp, ArrowDown, Minus, TrendCharts, Files } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

const dataSource = ref('cloud')
const selectedDate = ref(new Date())
const selectedChannel = ref('taobao')
const selectedShop = ref('all')
const grossMargin = ref(30)
const activeTab = ref('overview')
const showCustomDate = ref(false)
const showMoreData = ref(false)
const customDateRange = ref([])
const selectedPlan = ref(null)

const filterTags = ref({
  self: false,
  new: false,
  follow: false,
  pending: false
})

const promotionPlans = ref([
  { id: 1, name: '夏季新品推广计划', channel: '直通车', status: '运行中', planId: 'P202405001', type: '标准计划', cost: 12580, revenue: 38650, roi: 3.08, avgCpc: 2.85, clicks: 4414, impressions: 89520, conversionRate: 0.085, createTime: '2024-05-01' },
  { id: 2, name: '爆款打造计划', channel: '超级推荐', status: '运行中', planId: 'P202405002', type: '智能计划', cost: 8920, revenue: 25680, roi: 2.88, avgCpc: 1.95, clicks: 4574, impressions: 125680, conversionRate: 0.072, createTime: '2024-05-05' },
  { id: 3, name: '品牌推广计划', channel: '钻展', status: '暂停', planId: 'P202405003', type: '品牌计划', cost: 15600, revenue: 42500, roi: 2.72, avgCpc: 4.20, clicks: 3714, impressions: 45800, conversionRate: 0.091, createTime: '2024-04-28' },
  { id: 4, name: '清仓促销计划', channel: '直通车', status: '运行中', planId: 'P202405004', type: '标准计划', cost: 4580, revenue: 11200, roi: 2.44, avgCpc: 1.65, clicks: 2776, impressions: 58450, conversionRate: 0.068, createTime: '2024-05-10' },
  { id: 5, name: '新品测款计划', channel: '超级推荐', status: '运行中', planId: 'P202405005', type: '智能计划', cost: 6780, revenue: 18950, roi: 2.80, avgCpc: 2.15, clicks: 3153, impressions: 78920, conversionRate: 0.075, createTime: '2024-05-12' }
])

const filteredProducts = ref([
  { id: 1, name: '夏季新款连衣裙', sku: 'SKU001' },
  { id: 2, name: '纯棉T恤短袖', sku: 'SKU002' },
  { id: 3, name: '休闲短裤男', sku: 'SKU003' }
])

const productTree = computed(() => {
  return filteredProducts.value.map(p => ({
    id: p.id,
    label: p.name,
    children: [{ id: p.sku, label: p.sku }]
  }))
})

const treeProps = {
  children: 'children',
  label: 'label'
}

const searchStats = ref({
  totalSearches: 125680,
  clickRate: 4.25,
  conversionRate: 3.82,
  growthRate: 12.5
})

const keywordRanking = ref([
  { rank: 1, keyword: '夏季连衣裙', searches: 25680, clickRate: 5.82, conversionRate: 4.25, trend: 5.2 },
  { rank: 2, keyword: '纯棉T恤', searches: 18950, clickRate: 4.56, conversionRate: 3.88, trend: 3.1 },
  { rank: 3, keyword: '休闲短裤男', searches: 15680, clickRate: 3.95, conversionRate: 3.25, trend: -1.2 },
  { rank: 4, keyword: '韩版女装', searches: 12350, clickRate: 4.12, conversionRate: 3.65, trend: 2.8 },
  { rank: 5, keyword: '修身显瘦', searches: 9850, clickRate: 3.58, conversionRate: 3.12, trend: 1.5 }
])

const searchChartRef = ref(null)
let searchChart = null

const getChannelType = (channel) => {
  const types = {
    '直通车': 'primary',
    '超级推荐': 'success',
    '钻展': 'warning'
  }
  return types[channel] || 'info'
}

const getStatusType = (status) => {
  const types = {
    '运行中': 'success',
    '暂停': 'warning',
    '已结束': 'info'
  }
  return types[status] || 'info'
}

const handleTabChange = (tab) => {
  if (tab.name === 'search-efficiency') {
    nextTick(() => initSearchChart())
  }
}

const handleProductSelect = (data) => {
  console.log('Selected product:', data)
}

const handleSelectionChange = (val) => {
  if (val.length > 0) {
    selectedPlan.value = val[0]
  }
}

const setDateRange = (range) => {
  const now = new Date()
  if (range === '7d') {
    selectedDate.value = new Date(now.setDate(now.getDate() - 7))
  } else if (range === '30d') {
    selectedDate.value = new Date(now.setDate(now.getDate() - 30))
  } else if (range === 'day') {
    selectedDate.value = new Date()
  } else if (range === 'week') {
    const dayOfWeek = now.getDay() || 7
    selectedDate.value = new Date(now.setDate(now.getDate() - dayOfWeek + 1))
  } else if (range === 'month') {
    selectedDate.value = new Date(now.getFullYear(), now.getMonth(), 1)
  }
}

const applyGrossMargin = () => {
  ElMessage.success(`单品毛利率已设置为 ${grossMargin.value}%`)
}

const exportData = () => {
  ElMessage.info('正在导出数据...')
}

const applyCustomDate = () => {
  if (customDateRange.value.length === 2) {
    ElMessage.success(`时间范围已设置为 ${formatDate(customDateRange.value[0])} 至 ${formatDate(customDateRange.value[1])}`)
  }
  showCustomDate.value = false
}

const formatDate = (date) => {
  const d = new Date(date)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const initSearchChart = () => {
  if (!searchChartRef.value) return
  
  searchChart = echarts.init(searchChartRef.value)
  const option = {
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['搜索次数', '点击次数', '转化次数']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: ['5/1', '5/2', '5/3', '5/4', '5/5', '5/6', '5/7']
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: '搜索次数',
        type: 'line',
        smooth: true,
        data: [18500, 21200, 19800, 23500, 22800, 25600, 24200]
      },
      {
        name: '点击次数',
        type: 'line',
        smooth: true,
        data: [820, 950, 880, 1050, 990, 1150, 1080]
      },
      {
        name: '转化次数',
        type: 'line',
        smooth: true,
        data: [32, 38, 35, 42, 39, 45, 42]
      }
    ]
  }
  searchChart.setOption(option)
  
  window.addEventListener('resize', () => {
    searchChart?.resize()
  })
}

onMounted(() => {
  nextTick(() => {
    if (activeTab.value === 'search-efficiency') {
      initSearchChart()
    }
  })
})
</script>

<style scoped>
.promotion-analysis {
  padding-bottom: 20px;
}

.filter-card {
  margin-bottom: 16px;
}

.filter-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filter-left, .filter-center, .filter-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.date-label, .margin-label {
  font-size: 14px;
  color: #606266;
}

.percent-label {
  font-size: 14px;
  color: #606266;
  margin-right: 8px;
}

.channel-row {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  gap: 12px;
}

.channel-select, .shop-select {
  width: 140px;
}

.main-card {
  min-height: calc(100vh - 280px);
}

.card-header {
  border-bottom: 1px solid #ebeef5;
}

.tab-content {
  display: flex;
  gap: 16px;
  padding: 16px;
}

.left-panel {
  width: 260px;
  flex-shrink: 0;
  background: #fafafa;
  border-radius: 8px;
  padding: 12px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
}

.panel-title {
  font-weight: 600;
  font-size: 14px;
}

.filter-tags {
  display: flex;
  gap: 8px;
}

.product-list {
  margin-top: 12px;
  height: calc(100vh - 420px);
  overflow-y: auto;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: #909399;
}

.empty-icon {
  margin-bottom: 12px;
  color: #c0c4cc;
}

.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.table-container {
  background: #fff;
  border-radius: 8px;
}

.plan-detail {
  background: #fff;
  border-radius: 8px;
}

.detail-header {
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
}

.detail-title {
  font-weight: 600;
  font-size: 14px;
}

.detail-content {
  padding: 16px;
}

.efficiency-content {
  padding: 16px;
}

.summary-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.summary-card {
  display: flex;
  align-items: center;
  gap: 16px;
}

.card-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.search-icon {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
}

.click-icon {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  color: #fff;
}

.conversion-icon {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: #fff;
}

.growth-icon {
  background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
  color: #fff;
}

.card-info {
  flex: 1;
}

.card-value {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 4px 0;
}

.card-label {
  font-size: 12px;
  color: #909399;
  margin: 0;
}

.chart-section {
  margin-bottom: 16px;
}

.chart-container {
  height: 300px;
}

.text-success {
  color: #67c23a;
}

.text-danger {
  color: #f56c6c;
}

.text-gray {
  color: #909399;
}

.el-descriptions__label {
  font-weight: 500;
}
</style>
