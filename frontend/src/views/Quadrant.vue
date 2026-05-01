<template>
  <div class="quadrant">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>商品四象限分析</span>
          <span class="subtitle">GMV vs ROI</span>
        </div>
      </template>
      <el-row :gutter="20">
        <el-col :span="16">
          <div ref="chartRef" class="chart-container"></div>
        </el-col>
        <el-col :span="8">
          <div class="legend">
            <h4>图例说明</h4>
            <div class="legend-item">
              <span class="legend-color star"></span>
              <span>明星商品（高 GMV + 高 ROI）</span>
            </div>
            <div class="legend-item">
              <span class="legend-color cash-cow"></span>
              <span>现金牛（高 GMV + 低 ROI）</span>
            </div>
            <div class="legend-item">
              <span class="legend-color question"></span>
              <span>问题商品（低 GMV + 高 ROI）</span>
            </div>
            <div class="legend-item">
              <span class="legend-color dog"></span>
              <span>瘦狗商品（低 GMV + 低 ROI）</span>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-row :gutter="20" class="product-lists">
      <el-col :span="6" v-for="(products, key) in quadrantGroups" :key="key">
        <el-card class="quadrant-card">
          <template #header>
            <div class="quadrant-header">
              <span>{{ quadrantNames[key] }}</span>
              <el-tag type="info" size="small">{{ products.length }}</el-tag>
            </div>
          </template>
          <div class="product-list">
            <div 
              v-for="p in products.slice(0, 10)" 
              :key="p.product_id" 
              class="product-item"
              @click="$router.push(`/product/${p.product_id}`)"
            >
              <div class="product-name">{{ p.title || p.product_id }}</div>
              <div class="product-metrics">
                <span>GMV: ¥{{ formatNumber(p.gmv) }}</span>
                <span>ROI: {{ p.roi?.toFixed(2) }}</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import api from '@/api'

const chartRef = ref(null)
let chart = null

const quadrantData = ref([])
const quadrantGroups = ref({})
const quadrantNames = {
  star: '明星商品',
  cash_cow: '现金牛',
  question: '问题商品',
  dog: '瘦狗商品'
}

const formatNumber = (num) => {
  if (!num) return '0'
  if (num >= 10000) {
    return (num / 10000).toFixed(2) + '万'
  }
  return num.toLocaleString()
}

const gmvMid = ref(10000)
const roiMid = ref(3)

const loadData = async () => {
  try {
    const res = await api.getQuadrantData()
    quadrantData.value = res.data?.products || []
    quadrantGroups.value = res.data?.quadrants || {}
    gmvMid.value = res.data?.gmv_mid || 10000
    roiMid.value = res.data?.roi_mid || 3
    nextTick(() => {
      initChart()
    })
  } catch (error) {
    console.error('Load quadrant data error:', error)
  }
}

const initChart = () => {
  if (!chartRef.value) return
  
  if (chart) {
    chart.dispose()
  }
  
  chart = echarts.init(chartRef.value)
  
  const colors = {
    star: '#67c23a',
    cash_cow: '#409eff',
    question: '#e6a23c',
    dog: '#909399'
  }
  
  const seriesData = Object.values(quadrantGroups.value).flatMap(group =>
    group.map(p => ({
      name: p.title || p.product_id,
      value: [p.gmv, p.roi],
      quadrant: p.quadrant,
      itemStyle: { color: colors[p.quadrant] }
    }))
  )
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        return `${params.name}<br/>GMV: ¥${formatNumber(params.value[0])}<br/>ROI: ${params.value[1]?.toFixed(2)}`
      }
    },
    grid: {
      left: '10%',
      right: '10%',
      bottom: '10%',
      top: '10%'
    },
    xAxis: {
      type: 'value',
      name: 'GMV',
      splitLine: { show: false }
    },
    yAxis: {
      type: 'value',
      name: 'ROI',
      splitLine: { show: false }
    },
    series: [
      {
        type: 'scatter',
        data: seriesData,
        symbolSize: 15,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.3)'
          }
        },
        markLine: {
          silent: true,
          lineStyle: { color: '#999', type: 'dashed' },
          data: [
            { xAxis: gmvMid.value },
            { yAxis: roiMid.value }
          ],
          label: { show: false }
        },
        markArea: {
          silent: true,
          label: {
            position: 'inside',
            formatter: '{b}',
            color: '#999',
            fontSize: 14
          },
          data: [
            [
              { name: '明星商品', xAxis: gmvMid.value, yAxis: roiMid.value, itemStyle: { color: 'rgba(103, 194, 58, 0.1)' } },
              {}
            ],
            [
              { name: '问题商品', yAxis: roiMid.value, itemStyle: { color: 'rgba(230, 162, 60, 0.1)' } },
              { xAxis: gmvMid.value }
            ],
            [
              { name: '现金牛', xAxis: gmvMid.value, itemStyle: { color: 'rgba(64, 158, 255, 0.1)' } },
              { yAxis: roiMid.value }
            ],
            [
              { name: '瘦狗商品', itemStyle: { color: 'rgba(144, 147, 153, 0.1)' } },
              { xAxis: gmvMid.value, yAxis: roiMid.value }
            ]
          ]
        }
      }
    ]
  }
  
  chart.setOption(option)
  
  window.addEventListener('resize', () => chart.resize())
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.quadrant {
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.subtitle {
  color: #909399;
  font-size: 14px;
}

.chart-container {
  height: 500px;
  width: 100%;
}

.legend {
  padding: 20px;
}

.legend h4 {
  margin-bottom: 15px;
}

.legend-item {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
  gap: 10px;
}

.legend-color {
  width: 16px;
  height: 16px;
  border-radius: 50%;
}

.legend-color.star {
  background: #67c23a;
}

.legend-color.cash-cow {
  background: #409eff;
}

.legend-color.question {
  background: #e6a23c;
}

.legend-color.dog {
  background: #909399;
}

.product-lists {
  margin-top: 20px;
}

.quadrant-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.product-list {
  max-height: 400px;
  overflow-y: auto;
}

.product-item {
  padding: 10px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background 0.2s;
}

.product-item:hover {
  background: #f5f7fa;
}

.product-name {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.product-metrics {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #909399;
}
</style>
