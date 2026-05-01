<template>
  <div class="channel-detail">
    <el-page-header @back="goBack" content="渠道详情" />
    
    <div class="page-header">
      <div class="header-left">
        <el-select v-model="selectedChannel" placeholder="选择渠道" filterable style="width: 200px">
          <el-option label="淘宝店铺" value="taobao" />
          <el-option label="天猫旗舰店" value="tmall" />
          <el-option label="京东自营" value="jd" />
          <el-option label="拼多多" value="pinduoduo" />
        </el-select>
      </div>
      <div class="header-right">
        <el-button type="primary" size="small">打标</el-button>
        <el-button size="small">跟进</el-button>
      </div>
    </div>

    <el-card class="summary-card" style="margin-top: 20px">
      <template #header>
        <span>店铺综合指标</span>
      </template>
      <div class="summary-grid">
        <div class="summary-item">
          <div class="summary-value">¥{{ formatNumber(summaryData.gmv) }}</div>
          <div class="summary-label">GMV</div>
          <div class="summary-trend" :class="summaryData.gmvTrend >= 0 ? 'up' : 'down'">
            {{ summaryData.gmvTrend >= 0 ? '+' : '' }}{{ summaryData.gmvTrend }}%
          </div>
        </div>
        <div class="summary-item">
          <div class="summary-value">{{ formatNumber(summaryData.visitors) }}</div>
          <div class="summary-label">访客数</div>
          <div class="summary-trend" :class="summaryData.visitorTrend >= 0 ? 'up' : 'down'">
            {{ summaryData.visitorTrend >= 0 ? '+' : '' }}{{ summaryData.visitorTrend }}%
          </div>
        </div>
        <div class="summary-item">
          <div class="summary-value">{{ formatPercent(summaryData.conversion) }}</div>
          <div class="summary-label">转化率</div>
          <div class="summary-trend" :class="summaryData.conversionTrend >= 0 ? 'up' : 'down'">
            {{ summaryData.conversionTrend >= 0 ? '+' : '' }}{{ summaryData.conversionTrend }}%
          </div>
        </div>
        <div class="summary-item">
          <div class="summary-value">¥{{ formatNumber(summaryData.aov) }}</div>
          <div class="summary-label">客单价</div>
          <div class="summary-trend" :class="summaryData.aovTrend >= 0 ? 'up' : 'down'">
            {{ summaryData.aovTrend >= 0 ? '+' : '' }}{{ summaryData.aovTrend }}%
          </div>
        </div>
        <div class="summary-item">
          <div class="summary-value">¥{{ formatNumber(summaryData.adSpend) }}</div>
          <div class="summary-label">广告花费</div>
          <div class="summary-trend" :class="summaryData.adTrend >= 0 ? 'up' : 'down'">
            {{ summaryData.adTrend >= 0 ? '+' : '' }}{{ summaryData.adTrend }}%
          </div>
        </div>
        <div class="summary-item">
          <div class="summary-value">{{ summaryData.adRoi }}</div>
          <div class="summary-label">广告ROI</div>
          <div class="summary-trend" :class="summaryData.roiTrend >= 0 ? 'up' : 'down'">
            {{ summaryData.roiTrend >= 0 ? '+' : '' }}{{ summaryData.roiTrend }}%
          </div>
        </div>
      </div>
    </el-card>

    <el-card style="margin-top: 20px">
      <template #header>
        <span>数据详情</span>
        <div class="header-actions">
          <el-button size="small" type="text">
            <el-icon><More /></el-icon>
            更多数据
          </el-button>
          <el-button size="small" type="text" @click="exportData">
            <el-icon><Download /></el-icon>
            导出
          </el-button>
        </div>
      </template>
      <el-tabs v-model="activeTab" type="card">
        <el-tab-pane label="经营数据" name="business">
          <div class="tab-content">
            <div ref="chartRef" class="chart-container"></div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="业绩对比" name="compare">
          <div class="tab-content">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-card>
                  <template #header>同比对比</template>
                  <div class="compare-list">
                    <div class="compare-item">
                      <span class="compare-label">GMV同比</span>
                      <span class="compare-value" :class="summaryData.gmvYoY >= 0 ? 'positive' : 'negative'">
                        {{ summaryData.gmvYoY >= 0 ? '+' : '' }}{{ summaryData.gmvYoY }}%
                      </span>
                    </div>
                    <div class="compare-item">
                      <span class="compare-label">访客同比</span>
                      <span class="compare-value" :class="summaryData.visitorYoY >= 0 ? 'positive' : 'negative'">
                        {{ summaryData.visitorYoY >= 0 ? '+' : '' }}{{ summaryData.visitorYoY }}%
                      </span>
                    </div>
                    <div class="compare-item">
                      <span class="compare-label">转化同比</span>
                      <span class="compare-value" :class="summaryData.conversionYoY >= 0 ? 'positive' : 'negative'">
                        {{ summaryData.conversionYoY >= 0 ? '+' : '' }}{{ summaryData.conversionYoY }}%
                      </span>
                    </div>
                  </div>
                </el-card>
              </el-col>
              <el-col :span="12">
                <el-card>
                  <template #header>环比对比</template>
                  <div class="compare-list">
                    <div class="compare-item">
                      <span class="compare-label">GMV环比</span>
                      <span class="compare-value" :class="summaryData.gmvMoM >= 0 ? 'positive' : 'negative'">
                        {{ summaryData.gmvMoM >= 0 ? '+' : '' }}{{ summaryData.gmvMoM }}%
                      </span>
                    </div>
                    <div class="compare-item">
                      <span class="compare-label">访客环比</span>
                      <span class="compare-value" :class="summaryData.visitorMoM >= 0 ? 'positive' : 'negative'">
                        {{ summaryData.visitorMoM >= 0 ? '+' : '' }}{{ summaryData.visitorMoM }}%
                      </span>
                    </div>
                    <div class="compare-item">
                      <span class="compare-label">转化环比</span>
                      <span class="compare-value" :class="summaryData.conversionMoM >= 0 ? 'positive' : 'negative'">
                        {{ summaryData.conversionMoM >= 0 ? '+' : '' }}{{ summaryData.conversionMoM }}%
                      </span>
                    </div>
                  </div>
                </el-card>
              </el-col>
            </el-row>
          </div>
        </el-tab-pane>

        <el-tab-pane label="品类分析" name="category">
          <div class="tab-content">
            <el-table :data="categoryData" border>
              <el-table-column prop="category" label="品类" />
              <el-table-column prop="gmv" label="GMV">
                <template #default="{ row }">¥{{ formatNumber(row.gmv) }}</template>
              </el-table-column>
              <el-table-column prop="ratio" label="占比">
                <template #default="{ row }">
                  <el-progress :percentage="row.ratio" :show-text="false" />
                </template>
              </el-table-column>
              <el-table-column prop="visitors" label="访客数">
                <template #default="{ row }">{{ formatNumber(row.visitors) }}</template>
              </el-table-column>
              <el-table-column prop="conversion" label="转化率">
                <template #default="{ row }">{{ formatPercent(row.conversion) }}</template>
              </el-table-column>
              <el-table-column prop="trend" label="趋势">
                <template #default="{ row }">
                  <el-tag :type="row.trend >= 0 ? 'success' : 'danger'">
                    {{ row.trend >= 0 ? '+' : '' }}{{ row.trend }}%
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <el-tab-pane label="热销商品" name="hot-products">
          <div class="tab-content">
            <el-table :data="hotProducts" border>
              <el-table-column prop="rank" label="排名" width="60">
                <template #default="{ row }">
                  <el-tag v-if="row.rank <= 3" :type="['danger', 'warning', 'success'][row.rank - 1]">
                    {{ row.rank }}
                  </el-tag>
                  <span v-else>{{ row.rank }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="title" label="商品名称" min-width="200" />
              <el-table-column prop="category" label="品类" />
              <el-table-column prop="sales" label="销售额">
                <template #default="{ row }">¥{{ formatNumber(row.sales) }}</template>
              </el-table-column>
              <el-table-column prop="visitors" label="访客数">
                <template #default="{ row }">{{ formatNumber(row.visitors) }}</template>
              </el-table-column>
              <el-table-column prop="conversion" label="转化率">
                <template #default="{ row }">{{ formatPercent(row.conversion) }}</template>
              </el-table-column>
              <el-table-column prop="roi" label="ROI" width="80">
                <template #default="{ row }">{{ row.roi }}</template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { More, Download } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

const router = useRouter()
const chartRef = ref(null)
let chart = null

const selectedChannel = ref('taobao')
const activeTab = ref('business')

const summaryData = ref({
  gmv: 1258000,
  gmvTrend: 12.5,
  visitors: 45680,
  visitorTrend: 8.3,
  conversion: 0.045,
  conversionTrend: 2.1,
  aov: 275.6,
  aovTrend: 4.2,
  adSpend: 125000,
  adTrend: 15.8,
  adRoi: 4.2,
  roiTrend: -3.5,
  gmvYoY: 25.6,
  visitorYoY: 18.2,
  conversionYoY: 6.1,
  gmvMoM: 12.5,
  visitorMoM: 8.3,
  conversionMoM: 3.8,
})

const categoryData = ref([
  { category: '女装', gmv: 450000, ratio: 36, visitors: 18000, conversion: 0.042, trend: 15.2 },
  { category: '鞋靴', gmv: 280000, ratio: 22, visitors: 12000, conversion: 0.038, trend: 8.5 },
  { category: '配饰', gmv: 200000, ratio: 16, visitors: 8500, conversion: 0.052, trend: -2.3 },
  { category: '箱包', gmv: 180000, ratio: 14, visitors: 7500, conversion: 0.048, trend: 22.1 },
  { category: '其他', gmv: 148000, ratio: 12, visitors: 9680, conversion: 0.032, trend: 5.6 },
])

const hotProducts = ref([
  { rank: 1, title: '夏季新款碎花连衣裙女', category: '女装', sales: 185000, visitors: 6800, conversion: 0.058, roi: 5.8 },
  { rank: 2, title: '韩版显瘦雪纺上衣', category: '女装', sales: 156000, visitors: 5200, conversion: 0.062, roi: 6.2 },
  { rank: 3, title: '舒适透气运动鞋', category: '鞋靴', sales: 142000, visitors: 4800, conversion: 0.055, roi: 4.8 },
  { rank: 4, title: '时尚百搭斜挎包', category: '箱包', sales: 128000, visitors: 4200, conversion: 0.058, roi: 5.2 },
  { rank: 5, title: '精致珍珠项链', category: '配饰', sales: 115000, visitors: 3800, conversion: 0.065, roi: 7.1 },
])

const formatNumber = (num) => {
  if (!num) return '0'
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + '万'
  }
  return num.toLocaleString()
}

const formatPercent = (value) => {
  if (!value) return '0%'
  return (value * 100).toFixed(2) + '%'
}

const initChart = () => {
  if (!chartRef.value) return

  if (chart) {
    chart.dispose()
  }

  chart = echarts.init(chartRef.value)

  const dates = ['1月', '2月', '3月', '4月', '5月', '6月']
  const gmv = [85, 92, 108, 115, 120, 126]
  const visitors = [32, 35, 38, 42, 44, 46]

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      data: ['GMV(万)', '访客(万)']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: dates
    },
    yAxis: [
      {
        type: 'value',
        name: 'GMV(万)'
      },
      {
        type: 'value',
        name: '访客(万)',
        position: 'right'
      }
    ],
    series: [
      {
        name: 'GMV(万)',
        type: 'line',
        data: gmv,
        smooth: true,
        itemStyle: { color: '#409eff' }
      },
      {
        name: '访客(万)',
        type: 'line',
        data: visitors,
        smooth: true,
        yAxisIndex: 1,
        itemStyle: { color: '#67c23a' }
      }
    ]
  }

  chart.setOption(option)
  window.addEventListener('resize', () => chart.resize())
}

const exportData = () => {
  ElMessage.success('数据导出功能已触发')
}

const goBack = () => {
  router.back()
}

onMounted(() => {
  nextTick(() => {
    initChart()
  })
})
</script>

<style scoped>
.channel-detail {
  width: 100%;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 0;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.summary-card {
  margin-top: 20px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 20px;
}

.summary-item {
  text-align: center;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.summary-value {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.summary-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 5px;
}

.summary-trend {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
}

.summary-trend.up {
  color: #67c23a;
  background: #f0f9eb;
}

.summary-trend.down {
  color: #f56c6c;
  background: #fef0f0;
}

.tab-content {
  padding: 20px;
}

.chart-container {
  height: 350px;
  width: 100%;
}

.compare-list {
  padding: 10px 0;
}

.compare-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 0;
  border-bottom: 1px dashed #e4e7ed;
}

.compare-item:last-child {
  border-bottom: none;
}

.compare-label {
  font-size: 14px;
  color: #606266;
}

.compare-value {
  font-size: 18px;
  font-weight: 600;
}

.compare-value.positive {
  color: #67c23a;
}

.compare-value.negative {
  color: #f56c6c;
}
</style>