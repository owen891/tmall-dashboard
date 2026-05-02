<template>
  <div class="prediction-page">
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-icon><TrendCharts /></el-icon>
            <span>预测分析</span>
          </div>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="GMV 预测" name="gmv">
          <el-row :gutter="20">
            <el-col :span="16">
              <el-card>
                <template #header>
                  <span>GMV 趋势预测</span>
                </template>
                <div ref="gmvChartRef" style="width: 100%; height: 350px;"></div>
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card>
                <template #header>
                  <span>预测概览</span>
                </template>
                <el-descriptions :column="1" border>
                  <el-descriptions-item label="预测置信度">
                    <el-progress :percentage="gmvPrediction?.confidence || 0" :stroke-width="10" />
                  </el-descriptions-item>
                  <el-descriptions-item label="趋势">
                    <el-tag :type="gmvPrediction?.trend === 'up' ? 'success' : 'danger'">
                      {{ gmvPrediction?.trend === 'up' ? '上升 ↑' : '下降 ↓' }}
                    </el-tag>
                  </el-descriptions-item>
                  <el-descriptions-item label="历史周均 GMV">
                    ¥{{ formatNumber(gmvPrediction?.avg_weekly_gmv) }}
                  </el-descriptions-item>
                  <el-descriptions-item label="预测周期">
                    未来 {{ gmvPrediction?.predictions?.length || 0 }} 周
                  </el-descriptions-item>
                </el-descriptions>
              </el-card>
            </el-col>
          </el-row>
          
          <el-card style="margin-top: 20px">
            <template #header>
              <span>预测明细</span>
            </template>
            <el-table :data="gmvPrediction?.predictions || []" stripe>
              <el-table-column prop="date" label="预测日期" width="120" />
              <el-table-column prop="predicted_gmv" label="预测 GMV" width="150" align="right">
                <template #default="{ row }">¥{{ formatNumber(row.predicted_gmv) }}</template>
              </el-table-column>
              <el-table-column label="置信区间" width="200">
                <template #default="{ row }">
                  ¥{{ formatNumber(row.lower_bound) }} - ¥{{ formatNumber(row.upper_bound) }}
                </template>
              </el-table-column>
              <el-table-column prop="trend" label="趋势" width="100" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.trend === 'up' ? 'success' : 'danger'" size="small">
                    {{ row.trend === 'up' ? '上升' : '下降' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="销量预测" name="sales">
          <el-card>
            <template #header>
              <span>访客量预测</span>
            </template>
            <div ref="salesChartRef" style="width: 100%; height: 300px;"></div>
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="ROI 预测" name="roi">
          <el-card>
            <template #header>
              <span>广告 ROI 预测</span>
            </template>
            <el-table :data="roiPrediction?.predictions || []" stripe>
              <el-table-column prop="date" label="预测日期" width="120" />
              <el-table-column prop="predicted_roi" label="预测 ROI" width="120" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.assessment === 'good' ? 'success' : row.assessment === 'normal' ? 'warning' : 'danger'">
                    {{ row.predicted_roi }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="assessment" label="评估" width="100" align="center">
                <template #default="{ row }">
                  {{ row.assessment === 'good' ? '优秀' : row.assessment === 'normal' ? '一般' : '较差' }}
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import * as echarts from 'echarts'

const activeTab = ref('gmv')
const gmvPrediction = ref(null)
const roiPrediction = ref(null)
const gmvChartRef = ref(null)
const salesChartRef = ref(null)

const loadData = async () => {
  try {
    const [gmvRes, roiRes] = await Promise.all([
      api.getPrediction({ periods: 8 }),
      api.getPrediction({ periods: 4 })
    ])
    gmvPrediction.value = gmvRes.data
    roiPrediction.value = roiRes.data
    
    setTimeout(() => {
      if (gmvChartRef.value && gmvRes.data?.predictions) {
        renderGmvChart(gmvRes.data.predictions)
      }
    }, 100)
  } catch (error) {
    console.error('Load prediction error:', error)
    ElMessage.error('加载预测数据失败')
  }
}

const renderGmvChart = (predictions) => {
  if (!gmvChartRef.value) return
  
  const chart = echarts.init(gmvChartRef.value)
  const dates = predictions.map(p => p.date)
  const values = predictions.map(p => p.predicted_gmv)
  const lower = predictions.map(p => p.lower_bound)
  const upper = predictions.map(p => p.upper_bound)
  
  chart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const p = params[0]
        return `${p.name}<br/>预测: ¥${p.value.toLocaleString()}`
      }
    },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', axisLabel: { formatter: v => '¥' + (v/1000).toFixed(0) + 'k' } },
    series: [
      {
        name: '预测GMV',
        type: 'line',
        smooth: true,
        data: values,
        itemStyle: { color: '#409eff' },
        areaStyle: { color: 'rgba(64, 158, 255, 0.1)' }
      },
      {
        name: '上限',
        type: 'line',
        smooth: true,
        data: upper,
        lineStyle: { type: 'dashed', color: '#67c23a' },
        itemStyle: { color: '#67c23a' }
      },
      {
        name: '下限',
        type: 'line',
        smooth: true,
        data: lower,
        lineStyle: { type: 'dashed', color: '#e6a23c' },
        itemStyle: { color: '#e6a23c' }
      }
    ]
  })
}

const formatNumber = (value) => {
  if (!value && value !== 0) return '-'
  return Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.prediction-page {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 500;
}
</style>
