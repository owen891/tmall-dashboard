<template>
  <div class="traffic-analysis">
    <div class="page-header">
      <h1>流量分析</h1>
      <ExportButton 
        :table-data="channelData" 
        :chart-instance="trendChart"
        :file-name="`流量分析_${new Date().toISOString().split('T')[0]}`"
        button-text="导出数据"
        type="primary"
        size="small"
      />
    </div>

    <div v-loading="loading">
      <el-row :gutter="20" class="summary-cards">
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-icon visitors">
              <el-icon><User /></el-icon>
            </div>
            <div class="stat-content">
              <div class="stat-label">总访客数</div>
              <div class="stat-value">{{ formatNumber(overview.visitors) }}</div>
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-icon pv">
              <el-icon><View /></el-icon>
            </div>
            <div class="stat-content">
              <div class="stat-label">总浏览量</div>
              <div class="stat-value">{{ formatNumber(overview.pv) }}</div>
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-icon conversion">
              <el-icon><TrendCharts /></el-icon>
            </div>
            <div class="stat-content">
              <div class="stat-label">平均转化率</div>
              <div class="stat-value">{{ (overview.conversion * 100).toFixed(2) }}%</div>
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-icon uv-value">
              <el-icon><Coin /></el-icon>
            </div>
            <div class="stat-content">
              <div class="stat-label">UV价值</div>
              <div class="stat-value">¥{{ overview.uvValue?.toFixed(2) || '0.00' }}</div>
            </div>
          </div>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="16">
          <div class="chart-card">
            <div class="card-header">
              <h3>流量趋势</h3>
            </div>
            <div ref="trendChartRef" style="height: 400px;"></div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="chart-card">
            <div class="card-header">
              <h3>流量来源分布</h3>
            </div>
            <div ref="sourceChartRef" style="height: 400px;"></div>
          </div>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="24">
          <div class="chart-card">
            <div class="card-header">
              <h3>渠道效果对比</h3>
            </div>
            <el-table :data="channelData" style="width: 100%">
              <el-table-column prop="channel" label="渠道" width="150" />
              <el-table-column label="访客数" width="120">
                <template #default="{ row }">{{ formatNumber(row.visitors) }}</template>
              </el-table-column>
              <el-table-column label="占比" width="100">
                <template #default="{ row }">{{ (row.ratio * 100).toFixed(1) }}%</template>
              </el-table-column>
              <el-table-column label="转化率" width="100">
                <template #default="{ row }">{{ (row.conversion * 100).toFixed(2) }}%</template>
              </el-table-column>
              <el-table-column label="客单价" width="120">
                <template #default="{ row }">¥{{ row.aov?.toFixed(2) || '0.00' }}</template>
              </el-table-column>
              <el-table-column label="GMV" width="150">
                <template #default="{ row }">¥{{ formatNumber(row.gmv) }}</template>
              </el-table-column>
              <el-table-column label="趋势" min-width="200">
                <template #default="{ row }">
                  <el-progress 
                    :percentage="row.ratio * 100" 
                    :color="getChannelColor(row.channel)"
                    :stroke-width="8"
                  />
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="12">
          <div class="chart-card">
            <div class="card-header">
              <h3>TOP搜索关键词</h3>
            </div>
            <el-table :data="topKeywords" style="width: 100%" max-height="400">
              <el-table-column prop="keyword" label="关键词" />
              <el-table-column label="流量" width="100">
                <template #default="{ row }">{{ formatNumber(row.visitors) }}</template>
              </el-table-column>
              <el-table-column label="转化率" width="100">
                <template #default="{ row }">{{ (row.conversion * 100).toFixed(2) }}%</template>
              </el-table-column>
            </el-table>
          </div>
        </el-col>
        <el-col :span="12">
          <div class="chart-card">
            <div class="card-header">
              <h3>TOP页面</h3>
            </div>
            <el-table :data="topPages" style="width: 100%" max-height="400">
              <el-table-column prop="page" label="页面" show-overflow-tooltip />
              <el-table-column label="访问量" width="100">
                <template #default="{ row }">{{ formatNumber(row.visits) }}</template>
              </el-table-column>
              <el-table-column label="跳出率" width="100">
                <template #default="{ row }">{{ (row.bounceRate * 100).toFixed(1) }}%</template>
              </el-table-column>
            </el-table>
          </div>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { User, View, TrendCharts, Coin } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import ExportButton from '@/components/ExportButton.vue'

const loading = ref(false)
const trendChartRef = ref(null)
const sourceChartRef = ref(null)
let trendChart = null
let sourceChart = null

const overview = ref({
  visitors: 0,
  pv: 0,
  conversion: 0,
  uvValue: 0
})

const channelData = ref([])
const topKeywords = ref([])
const topPages = ref([])

const loadData = async () => {
  loading.value = true
  try {
    // 尝试从API获取数据
    const response = await fetch('/api/traffic/overview')
    if (response.ok) {
      const result = await response.json()
      if (result.code === 200) {
        overview.value = result.data.overview
        channelData.value = result.data.channels || []
        topKeywords.value = result.data.keywords || []
        topPages.value = result.data.pages || []
      }
    } else {
      // 使用模拟数据
      loadMockData()
    }
  } catch (error) {
    loadMockData()
  } finally {
    loading.value = false
    renderCharts()
  }
}

const loadMockData = () => {
  overview.value = {
    visitors: 370616,
    pv: 892450,
    conversion: 0.0159,
    uvValue: 0.96
  }

  channelData.value = [
    { channel: '搜索流量', visitors: 150000, ratio: 0.40, conversion: 0.018, aov: 98.5, gmv: 265950 },
    { channel: '推荐流量', visitors: 120000, ratio: 0.32, conversion: 0.012, aov: 85.2, gmv: 122688 },
    { channel: '付费流量', visitors: 60000, ratio: 0.16, conversion: 0.025, aov: 112.3, gmv: 168450 },
    { channel: '自主访问', visitors: 25000, ratio: 0.07, conversion: 0.020, aov: 95.8, gmv: 47900 },
    { channel: '其他', visitors: 15616, ratio: 0.05, conversion: 0.008, aov: 68.4, gmv: 8540 }
  ]

  topKeywords.value = [
    { keyword: '玄关装饰摆件', visitors: 12500, conversion: 0.025 },
    { keyword: '财神爷摆件', visitors: 9800, conversion: 0.022 },
    { keyword: '乔迁之喜礼物', visitors: 8500, conversion: 0.028 },
    { keyword: '中古风摆件', visitors: 7200, conversion: 0.019 },
    { keyword: '入户玄关装饰', visitors: 6800, conversion: 0.021 },
    { keyword: '客厅摆件', visitors: 5500, conversion: 0.015 },
    { keyword: '搬家礼物', visitors: 4800, conversion: 0.032 },
    { keyword: '新中式摆件', visitors: 4200, conversion: 0.018 }
  ]

  topPages.value = [
    { page: '首页', visits: 125000, bounceRate: 0.35 },
    { page: '商品详情页-玄关摆件', visits: 45000, bounceRate: 0.25 },
    { page: '活动页-新品上市', visits: 32000, bounceRate: 0.42 },
    { page: '分类页-家居饰品', visits: 28000, bounceRate: 0.38 },
    { page: '商品详情页-财神摆件', visits: 25000, bounceRate: 0.22 }
  ]
}

const formatNumber = (num) => {
  if (!num) return '0'
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + '万'
  }
  return num.toLocaleString()
}

const getChannelColor = (channel) => {
  const colors = {
    '搜索流量': '#409EFF',
    '推荐流量': '#67C23A',
    '付费流量': '#E6A23C',
    '自主访问': '#F56C6C',
    '其他': '#909399'
  }
  return colors[channel] || '#409EFF'
}

const renderCharts = () => {
  renderTrendChart()
  renderSourceChart()
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
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      }
    },
    legend: {
      data: ['访客数', '转化率']
    },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false
    },
    yAxis: [
      {
        type: 'value',
        name: '访客数',
        position: 'left'
      },
      {
        type: 'value',
        name: '转化率',
        position: 'right',
        axisLabel: {
          formatter: '{value}%'
        }
      }
    ],
    series: [
      {
        name: '访客数',
        type: 'line',
        smooth: true,
        data: Array.from({ length: 30 }, () => Math.floor(Math.random() * 5000) + 10000),
        areaStyle: {
          opacity: 0.3
        }
      },
      {
        name: '转化率',
        type: 'line',
        smooth: true,
        yAxisIndex: 1,
        data: Array.from({ length: 30 }, () => (Math.random() * 2 + 1).toFixed(2))
      }
    ]
  })
}

const renderSourceChart = () => {
  if (!sourceChartRef.value) return
  
  if (!sourceChart) {
    sourceChart = echarts.init(sourceChartRef.value)
  }

  sourceChart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
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
        data: channelData.value.map(c => ({
          value: c.visitors,
          name: c.channel
        }))
      }
    ]
  })
}

onMounted(() => {
  loadData()
})

onBeforeUnmount(() => {
  trendChart?.dispose()
  sourceChart?.dispose()
})
</script>

<style scoped>
.traffic-analysis {
  padding: 24px;
}

.page-header {
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
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.stat-icon.visitors {
  background: rgba(64, 158, 255, 0.1);
  color: #409EFF;
}

.stat-icon.pv {
  background: rgba(103, 194, 58, 0.1);
  color: #67C23A;
}

.stat-icon.conversion {
  background: rgba(230, 162, 60, 0.1);
  color: #E6A23C;
}

.stat-icon.uv-value {
  background: rgba(245, 108, 108, 0.1);
  color: #F56C6C;
}

.stat-label {
  font-size: 14px;
  color: #999;
  margin-bottom: 4px;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #333;
}

.chart-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-bottom: 20px;
}

.card-header {
  margin-bottom: 16px;
}

.card-header h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}
</style>
