<template>
  <div class="promotion-analysis">
    <div class="page-header">
      <h1>推广效果分析</h1>
      <ExportButton 
        :table-data="campaignList" 
        :file-name="`推广效果分析_${activeChannel}_${new Date().toISOString().split('T')[0]}`"
        button-text="导出数据"
        type="primary"
        size="small"
      />
    </div>

    <el-row :gutter="20" class="summary-cards">
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-label">总花费</div>
          <div class="stat-value">¥{{ formatNumber(summary.totalCost) }}</div>
          <div class="stat-trend" :class="summary.costTrend >= 0 ? 'up' : 'down'">
            {{ summary.costTrend >= 0 ? '↑' : '↓' }} {{ Math.abs(summary.costTrend).toFixed(1) }}%
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-label">总成交额</div>
          <div class="stat-value">¥{{ formatNumber(summary.totalGmv) }}</div>
          <div class="stat-trend" :class="summary.gmvTrend >= 0 ? 'up' : 'down'">
            {{ summary.gmvTrend >= 0 ? '↑' : '↓' }} {{ Math.abs(summary.gmvTrend).toFixed(1) }}%
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-label">平均ROI</div>
          <div class="stat-value">{{ summary.avgRoi?.toFixed(2) }}</div>
          <div class="stat-trend" :class="summary.roiTrend >= 0 ? 'up' : 'down'">
            {{ summary.roiTrend >= 0 ? '↑' : '↓' }} {{ Math.abs(summary.roiTrend).toFixed(1) }}%
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-label">总点击量</div>
          <div class="stat-value">{{ formatNumber(summary.totalClicks) }}</div>
          <div class="stat-trend" :class="summary.clickTrend >= 0 ? 'up' : 'down'">
            {{ summary.clickTrend >= 0 ? '↑' : '↓' }} {{ Math.abs(summary.clickTrend).toFixed(1) }}%
          </div>
        </div>
      </el-col>
    </el-row>

    <el-tabs v-model="activeChannel" type="card" @tab-change="handleChannelChange">
      <el-tab-pane label="全部渠道" name="all" />
      <el-tab-pane label="直通车" name="zhitongche" />
      <el-tab-pane label="引力魔方" name="yinlimofang" />
      <el-tab-pane label="万相台" name="wanxiangtai" />
      <el-tab-pane label="淘客" name="taoke" />
    </el-tabs>

    <el-row :gutter="20">
      <el-col :span="16">
        <div class="chart-card">
          <div class="card-header">
            <h3>推广趋势</h3>
          </div>
          <div ref="trendChartRef" style="height: 400px;"></div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="chart-card">
          <div class="card-header">
            <h3>渠道花费占比</h3>
          </div>
          <div ref="pieChartRef" style="height: 400px;"></div>
        </div>
      </el-col>
    </el-row>

    <div class="table-card">
      <div class="card-header">
        <h3>推广计划列表</h3>
        <el-input
          v-model="searchKeyword"
          placeholder="搜索计划名称"
          style="width: 200px;"
          size="small"
          clearable
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>

      <el-table :data="filteredCampaigns" style="width: 100%">
        <el-table-column prop="campaign_name" label="计划名称" min-width="200" />
        <el-table-column prop="channel" label="渠道" width="100">
          <template #default="{ row }">
            <el-tag :type="getChannelType(row.channel)" size="small">
              {{ getChannelLabel(row.channel) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="花费" width="120" sortable>
          <template #default="{ row }">
            ¥{{ formatNumber(row.cost) }}
          </template>
        </el-table-column>
        <el-table-column label="点击量" width="100" sortable>
          <template #default="{ row }">
            {{ formatNumber(row.clicks) }}
          </template>
        </el-table-column>
        <el-table-column label="CPC" width="100" sortable>
          <template #default="{ row }">
            ¥{{ (row.cost / row.clicks).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="成交额" width="120" sortable>
          <template #default="{ row }">
            ¥{{ formatNumber(row.gmv) }}
          </template>
        </el-table-column>
        <el-table-column label="ROI" width="100" sortable>
          <template #default="{ row }">
            <span :class="getRoiClass(row.roi)">
              {{ row.roi?.toFixed(2) || '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="转化率" width="100" sortable>
          <template #default="{ row }">
            {{ (row.conversionRate * 100).toFixed(2) }}%
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'running' ? 'success' : 'info'" size="small">
              {{ row.status === 'running' ? '投放中' : '已暂停' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewDetail(row)">详情</el-button>
            <el-button size="small" type="primary" @click="optimizeCampaign(row)">优化</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import ExportButton from '@/components/ExportButton.vue'
import { formatNumber } from '@/utils/format'

const activeChannel = ref('all')
const searchKeyword = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const trendChartRef = ref(null)
const pieChartRef = ref(null)
let trendChart = null
let pieChart = null
let handleResize = null

const summary = ref({
  totalCost: 125680,
  totalGmv: 485920,
  avgRoi: 3.87,
  totalClicks: 156800,
  costTrend: 12.5,
  gmvTrend: 18.3,
  roiTrend: 5.2,
  clickTrend: 8.7
})

const campaignList = ref([])

const filteredCampaigns = computed(() => {
  let campaigns = campaignList.value
  
  if (activeChannel.value !== 'all') {
    campaigns = campaigns.filter(c => c.channel === activeChannel.value)
  }
  
  if (searchKeyword.value) {
    campaigns = campaigns.filter(c => 
      c.campaign_name.toLowerCase().includes(searchKeyword.value.toLowerCase())
    )
  }
  
  return campaigns
})

const loadCampaignData = async () => {
  campaignList.value = [
    { id: 1, campaign_name: '新品推广计划A', channel: 'zhitongche', cost: 15800, clicks: 12500, gmv: 52600, roi: 3.33, conversionRate: 0.042, status: 'running' },
    { id: 2, campaign_name: '爆款引流计划B', channel: 'zhitongche', cost: 22500, clicks: 18900, gmv: 98500, roi: 4.38, conversionRate: 0.052, status: 'running' },
    { id: 3, campaign_name: '首页推荐计划C', channel: 'yinlimofang', cost: 18200, clicks: 25600, gmv: 45600, roi: 2.51, conversionRate: 0.018, status: 'running' },
    { id: 4, campaign_name: '搜索推广计划D', channel: 'yinlimofang', cost: 12800, clicks: 15200, gmv: 38900, roi: 3.04, conversionRate: 0.026, status: 'paused' },
    { id: 5, campaign_name: '万相台拉新计划', channel: 'wanxiangtai', cost: 28500, clicks: 32100, gmv: 128500, roi: 4.51, conversionRate: 0.040, status: 'running' },
    { id: 6, campaign_name: '万相台收割计划', channel: 'wanxiangtai', cost: 19800, clicks: 18600, gmv: 89200, roi: 4.51, conversionRate: 0.048, status: 'running' },
    { id: 7, campaign_name: '淘客推广计划A', channel: 'taoke', cost: 7680, clicks: 34200, gmv: 32400, roi: 4.22, conversionRate: 0.009, status: 'running' },
    { id: 8, campaign_name: '淘客推广计划B', channel: 'taoke', cost: 3200, clicks: 15600, gmv: 18500, roi: 5.78, conversionRate: 0.012, status: 'running' }
  ]
  
  total.value = campaignList.value.length
}

const getChannelType = (channel) => {
  const types = {
    'zhitongche': 'primary',
    'yinlimofang': 'success',
    'wanxiangtai': 'warning',
    'taoke': 'info'
  }
  return types[channel] || ''
}

const getChannelLabel = (channel) => {
  const labels = {
    'zhitongche': '直通车',
    'yinlimofang': '引力魔方',
    'wanxiangtai': '万相台',
    'taoke': '淘客'
  }
  return labels[channel] || channel
}

const getRoiClass = (roi) => {
  if (roi >= 4) return 'high'
  if (roi >= 2) return 'medium'
  return 'low'
}

const handleChannelChange = () => {
  currentPage.value = 1
}

const viewDetail = (row) => {
  ElMessage.info(`查看 ${row.campaign_name} 详情`)
}

const optimizeCampaign = (row) => {
  ElMessage.success(`正在优化 ${row.campaign_name}`)
}

const renderCharts = () => {
  renderTrendChart()
  renderPieChart()
}

const renderTrendChart = () => {
  if (!trendChartRef.value) return
  
  if (!trendChart) {
    trendChart = echarts.init(trendChartRef.value)
  }

  const dates = Array.from({ length: 30 }, (_, i) => {
    const d = new Date()
    d.setDate(d.getDate() - 29 + i)
    return `${d.getMonth() + 1}/${d.getDate()}`
  })

  trendChart.setOption({
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['花费', '成交额', 'ROI']
    },
    xAxis: {
      type: 'category',
      data: dates
    },
    yAxis: [
      {
        type: 'value',
        name: '金额',
        position: 'left'
      },
      {
        type: 'value',
        name: 'ROI',
        position: 'right'
      }
    ],
    series: [
      {
        name: '花费',
        type: 'bar',
        data: Array.from({ length: 30 }, () => Math.floor(Math.random() * 5000) + 3000)
      },
      {
        name: '成交额',
        type: 'bar',
        data: Array.from({ length: 30 }, () => Math.floor(Math.random() * 20000) + 10000)
      },
      {
        name: 'ROI',
        type: 'line',
        yAxisIndex: 1,
        data: Array.from({ length: 30 }, () => (Math.random() * 3 + 2).toFixed(2))
      }
    ]
  })
}

const renderPieChart = () => {
  if (!pieChartRef.value) return
  
  if (!pieChart) {
    pieChart = echarts.init(pieChartRef.value)
  }

  const channelCosts = [
    { value: 38300, name: '直通车' },
    { value: 31000, name: '引力魔方' },
    { value: 48300, name: '万相台' },
    { value: 10880, name: '淘客' }
  ]

  pieChart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: '{b}: ¥{c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left'
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: false,
          position: 'center'
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 16,
            fontWeight: 'bold'
          }
        },
        labelLine: {
          show: false
        },
        data: channelCosts
      }
    ]
  })
}

onMounted(() => {
  loadCampaignData()
  renderCharts()
  handleResize = () => {
    trendChart?.resize()
    pieChart?.resize()
  }
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  pieChart?.dispose()
})
</script>

<style scoped>
.promotion-analysis {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 600;
  margin: 0;
}

.summary-cards {
  margin-bottom: 20px;
}

.stat-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.stat-label {
  font-size: 14px;
  color: #999;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
}

.stat-trend {
  font-size: 13px;
}

.stat-trend.up {
  color: #67C23A;
}

.stat-trend.down {
  color: #F56C6C;
}

.chart-card, .table-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-header h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.high {
  color: #67C23A;
  font-weight: 500;
}

.medium {
  color: #E6A23C;
}

.low {
  color: #F56C6C;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
