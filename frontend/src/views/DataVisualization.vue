<template>
  <div class="data-visualization">
    <div class="page-header">
      <h1>高级数据可视化</h1>
      <div class="header-actions">
        <el-select v-model="selectedChartType" placeholder="选择图表类型" style="width: 200px;">
          <el-option label="折线图" value="line" />
          <el-option label="柱状图" value="bar" />
          <el-option label="饼图" value="pie" />
          <el-option label="散点图" value="scatter" />
          <el-option label="雷达图" value="radar" />
          <el-option label="热力图" value="heatmap" />
          <el-option label="漏斗图" value="funnel" />
          <el-option label="仪表盘" value="gauge" />
        </el-select>
        <el-button @click="refreshChart">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </div>

    <el-row :gutter="20">
      <el-col :span="16">
        <div class="chart-container">
          <div ref="mainChartRef" style="height: 500px;"></div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="chart-config">
          <h3>图表配置</h3>
          <el-form label-width="100px">
            <el-form-item label="图表标题">
              <el-input v-model="chartConfig.title" placeholder="输入图表标题" />
            </el-form-item>
            <el-form-item label="显示图例">
              <el-switch v-model="chartConfig.showLegend" />
            </el-form-item>
            <el-form-item label="显示提示框">
              <el-switch v-model="chartConfig.showTooltip" />
            </el-form-item>
            <el-form-item label="显示网格">
              <el-switch v-model="chartConfig.showGrid" />
            </el-form-item>
            <el-form-item label="启用缩放">
              <el-switch v-model="chartConfig.dataZoom" />
            </el-form-item>
          </el-form>
        </div>

        <div class="export-section">
          <h3>导出</h3>
          <el-button type="primary" @click="exportChart('png')">
            <el-icon><Download /></el-icon> 导出PNG
          </el-button>
          <el-button @click="exportChart('svg')">
            <el-icon><Download /></el-icon> 导出SVG
          </el-button>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="chart-gallery">
      <el-col :span="8">
        <div class="mini-chart" @click="switchToChart('line')">
          <div class="chart-preview line-preview"></div>
          <span>折线图</span>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="mini-chart" @click="switchToChart('bar')">
          <div class="chart-preview bar-preview"></div>
          <span>柱状图</span>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="mini-chart" @click="switchToChart('pie')">
          <div class="chart-preview pie-preview"></div>
          <span>饼图</span>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="mini-chart" @click="switchToChart('scatter')">
          <div class="chart-preview scatter-preview"></div>
          <span>散点图</span>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="mini-chart" @click="switchToChart('radar')">
          <div class="chart-preview radar-preview"></div>
          <span>雷达图</span>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="mini-chart" @click="switchToChart('heatmap')">
          <div class="chart-preview heatmap-preview"></div>
          <span>热力图</span>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Download } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { exportChartToPNG } from '@/utils/export'

const mainChartRef = ref(null)
let mainChart = null

const selectedChartType = ref('line')

const chartConfig = ref({
  title: '数据趋势',
  showLegend: true,
  showTooltip: true,
  showGrid: true,
  dataZoom: true
})

const chartData = ref({
  dates: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
  series1: [820, 932, 901, 934, 1290, 1330, 1320],
  series2: [420, 532, 601, 634, 890, 930, 1020]
})

const switchToChart = (type) => {
  selectedChartType.value = type
  renderChart()
}

const refreshChart = () => {
  chartData.value.series1 = chartData.value.series1.map(() => Math.floor(Math.random() * 1000) + 500)
  chartData.value.series2 = chartData.value.series2.map(() => Math.floor(Math.random() * 1000) + 500)
  renderChart()
  ElMessage.success('图表已刷新')
}

const exportChart = (type) => {
  if (!mainChart) {
    ElMessage.error('图表未初始化')
    return
  }

  if (type === 'png') {
    exportChartToPNG(mainChart, `chart_${selectedChartType.value}_${Date.now()}`)
  } else {
    ElMessage.info('SVG导出功能开发中')
  }
}

const renderChart = () => {
  if (!mainChartRef.value) return

  if (!mainChart) {
    mainChart = echarts.init(mainChartRef.value)
  }

  let option = {}

  switch (selectedChartType.value) {
    case 'line':
      option = getLineOption()
      break
    case 'bar':
      option = getBarOption()
      break
    case 'pie':
      option = getPieOption()
      break
    case 'scatter':
      option = getScatterOption()
      break
    case 'radar':
      option = getRadarOption()
      break
    case 'heatmap':
      option = getHeatmapOption()
      break
    case 'funnel':
      option = getFunnelOption()
      break
    case 'gauge':
      option = getGaugeOption()
      break
    default:
      option = getLineOption()
  }

  mainChart.setOption(option)
}

const getBaseOption = () => ({
  title: {
    text: chartConfig.value.title,
    left: 'center'
  },
  tooltip: {
    trigger: chartConfig.value.showTooltip ? 'axis' : null,
    axisPointer: {
      type: 'cross'
    }
  },
  legend: chartConfig.value.showLegend ? {
    data: ['数据1', '数据2'],
    top: 30
  } : null,
  grid: chartConfig.value.showGrid ? {
    left: '3%',
    right: '4%',
    bottom: chartConfig.value.dataZoom ? '15%' : '3%',
    containLabel: true
  } : null,
  dataZoom: chartConfig.value.dataZoom ? [
    {
      type: 'slider',
      start: 0,
      end: 100
    },
    {
      type: 'inside',
      start: 0,
      end: 100
    }
  ] : null
})

const getLineOption = () => ({
  ...getBaseOption(),
  xAxis: {
    type: 'category',
    data: chartData.value.dates,
    boundaryGap: false
  },
  yAxis: {
    type: 'value'
  },
  series: [
    {
      name: '数据1',
      type: 'line',
      smooth: true,
      data: chartData.value.series1,
      areaStyle: {
        opacity: 0.3
      }
    },
    {
      name: '数据2',
      type: 'line',
      smooth: true,
      data: chartData.value.series2,
      areaStyle: {
        opacity: 0.3
      }
    }
  ]
})

const getBarOption = () => ({
  ...getBaseOption(),
  xAxis: {
    type: 'category',
    data: chartData.value.dates
  },
  yAxis: {
    type: 'value'
  },
  series: [
    {
      name: '数据1',
      type: 'bar',
      data: chartData.value.series1,
      itemStyle: {
        color: '#409EFF'
      }
    },
    {
      name: '数据2',
      type: 'bar',
      data: chartData.value.series2,
      itemStyle: {
        color: '#67C23A'
      }
    }
  ]
})

const getPieOption = () => ({
  title: {
    text: chartConfig.value.title,
    left: 'center'
  },
  tooltip: {
    trigger: 'item',
    formatter: '{b}: {c} ({d}%)'
  },
  legend: chartConfig.value.showLegend ? {
    orient: 'vertical',
    left: 'left'
  } : null,
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
      data: chartData.value.dates.map((name, index) => ({
        value: chartData.value.series1[index],
        name: name
      }))
    }
  ]
})

const getScatterOption = () => ({
  ...getBaseOption(),
  xAxis: {
    type: 'value'
  },
  yAxis: {
    type: 'value'
  },
  series: [
    {
      type: 'scatter',
      symbolSize: 20,
      data: chartData.value.series1.map((v, i) => [v, chartData.value.series2[i]])
    }
  ]
})

const getRadarOption = () => ({
  title: {
    text: chartConfig.value.title,
    left: 'center'
  },
  tooltip: {},
  legend: chartConfig.value.showLegend ? {
    data: ['预算', '实际'],
    left: 'right'
  } : null,
  radar: {
    indicator: [
      { name: '销售', max: 3000 },
      { name: '利润', max: 2500 },
      { name: '流量', max: 2000 },
      { name: '转化', max: 1500 },
      { name: '客单价', max: 1200 }
    ],
    center: ['50%', '55%'],
    radius: '65%'
  },
  series: [
    {
      type: 'radar',
      data: [
        {
          value: [2400, 2100, 1800, 1200, 900],
          name: '预算'
        },
        {
          value: [2200, 2300, 1600, 1300, 1000],
          name: '实际'
        }
      ]
    }
  ]
})

const getHeatmapOption = () => ({
  title: {
    text: chartConfig.value.title,
    left: 'center'
  },
  tooltip: {
    position: 'top'
  },
  grid: {
    left: '3%',
    right: '10%',
    bottom: '3%',
    containLabel: true
  },
  xAxis: {
    type: 'category',
    data: chartData.value.dates,
    splitArea: {
      show: true
    }
  },
  yAxis: {
    type: 'category',
    data: ['商品A', '商品B', '商品C', '商品D'],
    splitArea: {
      show: true
    }
  },
  visualMap: {
    min: 0,
    max: 2000,
    calculable: true,
    orient: 'vertical',
    right: 'right',
    top: 'center'
  },
  series: [
    {
      name: '销售额',
      type: 'heatmap',
      data: [
        [0, 0, 1200], [0, 1, 800], [0, 2, 1500], [0, 3, 600],
        [1, 0, 950], [1, 1, 1100], [1, 2, 750], [1, 3, 1400],
        [2, 0, 1800], [2, 1, 650], [2, 2, 1200], [2, 3, 900],
        [3, 0, 700], [3, 1, 1350], [3, 2, 850], [3, 3, 1100],
        [4, 0, 1450], [4, 1, 720], [4, 2, 1680], [4, 3, 580],
        [5, 0, 830], [5, 1, 980], [5, 2, 640], [5, 3, 1320],
        [6, 0, 1680], [6, 1, 520], [6, 2, 1420], [6, 3, 780]
      ],
      label: {
        show: true
      },
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      }
    }
  ]
})

const getFunnelOption = () => ({
  title: {
    text: chartConfig.value.title,
    left: 'center'
  },
  tooltip: {
    trigger: 'item',
    formatter: '{b}: {c}%'
  },
  legend: chartConfig.value.showLegend ? {
    data: ['访问', '点击', '加购', '下单', '支付'],
    left: 'left'
  } : null,
  series: [
    {
      name: '漏斗图',
      type: 'funnel',
      left: '10%',
      top: 60,
      bottom: 60,
      width: '80%',
      min: 0,
      max: 100,
      minSize: '0%',
      maxSize: '100%',
      sort: 'descending',
      gap: 2,
      label: {
        show: true,
        position: 'inside'
      },
      labelLine: {
        show: false
      },
      itemStyle: {
        borderColor: '#fff',
        borderWidth: 1
      },
      emphasis: {
        label: {
          fontSize: 16
        }
      },
      data: [
        { value: 100, name: '访问' },
        { value: 60, name: '点击' },
        { value: 40, name: '加购' },
        { value: 20, name: '下单' },
        { value: 10, name: '支付' }
      ]
    }
  ]
})

const getGaugeOption = () => ({
  title: {
    text: chartConfig.value.title,
    left: 'center'
  },
  series: [
    {
      type: 'gauge',
      startAngle: 180,
      endAngle: 0,
      center: ['50%', '70%'],
      radius: '90%',
      min: 0,
      max: 100,
      splitNumber: 10,
      axisLine: {
        lineStyle: {
          width: 6,
          color: [
            [0.3, '#67C23A'],
            [0.7, '#E6A23C'],
            [1, '#F56C6C']
          ]
        }
      },
      pointer: {
        icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z',
        length: '12%',
        width: 20,
        offsetCenter: [0, '-60%'],
        itemStyle: {
          color: 'auto'
        }
      },
      axisTick: {
        length: 12,
        lineStyle: {
          color: 'auto',
          width: 2
        }
      },
      splitLine: {
        length: 20,
        lineStyle: {
          color: 'auto',
          width: 5
        }
      },
      axisLabel: {
        color: '#464646',
        fontSize: 12,
        distance: -60
      },
      title: {
        offsetCenter: [0, '-10%'],
        fontSize: 16
      },
      detail: {
        fontSize: 30,
        offsetCenter: [0, '-35%'],
        valueAnimation: true,
        formatter: (value) => {
          return Math.round(value) + '%'
        },
        color: 'auto'
      },
      data: [
        {
          value: 72,
          name: '完成率'
        }
      ]
    }
  ]
})

watch(selectedChartType, () => {
  renderChart()
})

watch(chartConfig, () => {
  renderChart()
}, { deep: true })

onMounted(() => {
  renderChart()
  
  window.addEventListener('resize', () => {
    mainChart?.resize()
  })
})

onBeforeUnmount(() => {
  mainChart?.dispose()
})
</script>

<style scoped>
.data-visualization {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 600;
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.chart-container, .chart-config, .export-section {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.chart-config {
  margin-bottom: 20px;
}

.chart-config h3, .export-section h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px 0;
}

.export-section {
  margin-top: 20px;
}

.export-section .el-button {
  width: 100%;
  margin-bottom: 12px;
}

.chart-gallery {
  margin-top: 20px;
}

.mini-chart {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  cursor: pointer;
  transition: all 0.3s;
  margin-bottom: 20px;
}

.mini-chart:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.mini-chart span {
  display: block;
  text-align: center;
  margin-top: 12px;
  font-weight: 500;
}

.chart-preview {
  height: 120px;
  border-radius: 4px;
  background: #f5f7fa;
}

.line-preview {
  background: linear-gradient(to right, #409EFF 0%, #409EFF 50%, #67C23A 50%, #67C23A 100%);
  opacity: 0.8;
}

.bar-preview {
  background: repeating-linear-gradient(
    90deg,
    #409EFF 0px,
    #409EFF 15px,
    #67C23A 15px,
    #67C23A 30px
  );
  opacity: 0.8;
}

.pie-preview {
  background: conic-gradient(
    #409EFF 0deg 120deg,
    #67C23A 120deg 220deg,
    #E6A23C 220deg 320deg,
    #F56C6C 320deg 360deg
  );
  border-radius: 50%;
}

.scatter-preview {
  background: radial-gradient(
    circle at 30% 40%, #409EFF 4px, transparent 4px),
    radial-gradient(
    circle at 60% 30%, #67C23A 6px, transparent 6px),
    radial-gradient(
    circle at 45% 70%, #E6A23C 5px, transparent 5px),
    radial-gradient(
    circle at 80% 60%, #F56C6C 3px, transparent 3px),
    #f5f7fa;
}

.radar-preview {
  background: 
    conic-gradient(
      from 0deg at 50% 50%,
      transparent 0deg,
      #409EFF33 30deg,
      transparent 60deg,
      #67C23A33 90deg,
      transparent 120deg,
      #E6A23C33 150deg,
      transparent 180deg,
      #F56C6C33 210deg,
      transparent 240deg,
      #90939933 270deg,
      transparent 300deg,
      #409EFF33 330deg,
      transparent 360deg
    ),
    #f5f7fa;
}

.heatmap-preview {
  background: 
    linear-gradient(90deg, #67C23A 0%, #E6A23C 50%, #F56C6C 100%);
  opacity: 0.8;
}
</style>
