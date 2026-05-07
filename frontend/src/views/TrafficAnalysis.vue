<template>
  <div class="page-container traffic-page">
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
            <div ref="trendChartRef" style="height: 300px;"></div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="chart-card">
            <div class="card-header">
              <h3>流量来源分布</h3>
            </div>
            <div ref="sourceChartRef" style="height: 300px;"></div>
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
import api from '@/api'
import { formatNumber } from '@/utils/format'

const loading = ref(false)
const trendChartRef = ref(null)
const sourceChartRef = ref(null)
let trendChart = null
let sourceChart = null
let handleResize = null

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
    const result = await api.trafficApi.getKeywords({})
    const data = result?.data || {}
    
    overview.value = {
      visitors: data.overview?.visitors || 0,
      pv: data.overview?.pv || 0,
      conversion: data.overview?.conversion || 0,
      uvValue: data.overview?.uv_value || 0
    }
    
    channelData.value = (data.channels || []).map(c => ({
      channel: c.channel || '未知',
      visitors: c.visitors || 0,
      ratio: c.ratio || 0,
      conversion: c.conversion || 0,
      aov: c.aov || 0,
      gmv: c.gmv || 0
    }))
    
    topKeywords.value = (data.keywords || []).map(k => ({
      keyword: k.keyword || '',
      visitors: k.visitors || 0,
      conversion: k.conversion || 0
    }))
    
    topPages.value = (data.pages || []).map(p => ({
      page: p.page || '',
      visits: p.visits || 0,
      bounceRate: p.bounce_rate || 0
    }))
    
    renderCharts()
  } catch (error) {
    console.error('加载流量数据失败:', error)
    ElMessage.error('加载流量数据失败')
    overview.value = { visitors: 0, pv: 0, conversion: 0, uvValue: 0 }
    channelData.value = []
    topKeywords.value = []
    topPages.value = []
  } finally {
    loading.value = false
  }
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

  const trends = channelData.value.length > 0 ? channelData.value : []
  
  if (trends.length === 0) {
    trendChart.setOption({
      title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: '#999' } }
    }, true)
    return
  }

  trendChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['访客数', '转化率'] },
    xAxis: { type: 'category', data: trends.map(c => c.channel || ''), boundaryGap: false },
    yAxis: [
      { type: 'value', name: '访客数', position: 'left' },
      { type: 'value', name: '转化率', position: 'right', axisLabel: { formatter: '{value}%' } }
    ],
    series: [
      { name: '访客数', type: 'line', smooth: true, data: trends.map(c => c.visitors || 0), areaStyle: { opacity: 0.3 } },
      { name: '转化率', type: 'line', smooth: true, yAxisIndex: 1, data: trends.map(c => (c.conversion || 0) * 100) }
    ]
  })
}

const renderSourceChart = () => {
  if (!sourceChartRef.value) return
  
  if (!sourceChart) {
    sourceChart = echarts.init(sourceChartRef.value)
  }

  const data = channelData.value.length > 0 ? channelData.value : []
  
  if (data.length === 0) {
    sourceChart.setOption({
      title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: '#999' } }
    }, true)
    return
  }

  sourceChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'vertical', left: 'left' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
      label: { show: false, position: 'center' },
      emphasis: { label: { show: true, fontSize: 16, fontWeight: 'bold' } },
      labelLine: { show: false },
      data: data.map(c => ({ value: c.visitors || 0, name: c.channel || '未知' }))
    }]
  })
}

onMounted(() => {
  loadData()
  handleResize = () => {
    trendChart?.resize()
    sourceChart?.resize()
  }
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  sourceChart?.dispose()
})
</script>

<style scoped>
.traffic-page {
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
