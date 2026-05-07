import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'

/**
 * ECharts 图表封装 Hook
 * @param {Object} options - 图表配置选项
 * @returns {Object} - 图表实例和控制方法
 */
export function useChart(options = {}) {
  const chartRef = ref(null)
  let chart = null
  let resizeObserver = null

  // 初始化图表
  const initChart = (chartOptions) => {
    if (!chartRef.value) return null
    
    if (chart) {
      chart.dispose()
    }
    
    chart = echarts.init(chartRef.value)
    
    if (chartOptions) {
      chart.setOption(chartOptions)
    }
    
    return chart
  }

  // 更新图表配置
  const setOption = (chartOptions, notMerge = false) => {
    if (!chart) {
      initChart(chartOptions)
    } else {
      chart.setOption(chartOptions, notMerge)
    }
  }

  // 调整图表大小
  const resize = () => {
    chart?.resize()
  }

  // 清空图表
  const clear = () => {
    chart?.clear()
  }

  // 销毁图表
  const dispose = () => {
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
    chart?.dispose()
    chart = null
  }

  // 获取图表实例
  const getChartInstance = () => chart

  // 注册事件
  const on = (eventName, handler) => {
    chart?.on(eventName, handler)
  }

  // 取消事件
  const off = (eventName, handler) => {
    chart?.off(eventName, handler)
  }

  // 显示加载
  const showLoading = (loadingOptions = {}) => {
    chart?.showLoading({
      text: '加载中...',
      color: '#409eff',
      maskColor: 'rgba(255, 255, 255, 0.8)',
      ...loadingOptions
    })
  }

  // 隐藏加载
  const hideLoading = () => {
    chart?.hideLoading()
  }

  onMounted(() => {
    nextTick(() => {
      // 使用 ResizeObserver 监听容器大小变化
      if (chartRef.value) {
        resizeObserver = new ResizeObserver(() => {
          resize()
        })
        resizeObserver.observe(chartRef.value)
      }
    })
  })

  onBeforeUnmount(() => {
    dispose()
  })

  return {
    chartRef,
    initChart,
    setOption,
    resize,
    clear,
    dispose,
    getChartInstance,
    on,
    off,
    showLoading,
    hideLoading
  }
}

/**
 * 创建折线图配置
 */
export function createLineChartOption(data, config = {}) {
  const { 
    title, 
    xField = 'x', 
    yField = 'y', 
    smooth = true,
    showArea = true,
    color = '#409eff'
  } = config

  return {
    title: title ? { text: title, left: 'center', textStyle: { fontSize: 14 } } : undefined,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    grid: { left: 60, right: 40, top: title ? 40 : 20, bottom: 30 },
    xAxis: {
      type: 'category',
      data: data.map(d => d[xField]),
      axisLabel: { rotate: 45, fontSize: 11 }
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (v) => v >= 10000 ? (v / 10000).toFixed(1) + 'w' : v
      }
    },
    series: [{
      type: 'line',
      data: data.map(d => d[yField]),
      smooth,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { width: 2, color },
      itemStyle: { color },
      areaStyle: showArea ? {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: color.replace(')', ', 0.3)').replace('rgb', 'rgba') },
          { offset: 1, color: color.replace(')', ', 0.05)').replace('rgb', 'rgba') }
        ])
      } : undefined
    }]
  }
}

/**
 * 创建柱状图配置
 */
export function createBarChartOption(data, config = {}) {
  const { 
    title, 
    xField = 'x', 
    yField = 'y',
    color = '#409eff',
    horizontal = false
  } = config

  return {
    title: title ? { text: title, left: 'center', textStyle: { fontSize: 14 } } : undefined,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    grid: { left: 60, right: 40, top: title ? 40 : 20, bottom: 30 },
    xAxis: {
      type: horizontal ? 'value' : 'category',
      data: horizontal ? undefined : data.map(d => d[xField]),
      axisLabel: { rotate: 45, fontSize: 11 }
    },
    yAxis: {
      type: horizontal ? 'category' : 'value',
      data: horizontal ? data.map(d => d[xField]) : undefined,
      axisLabel: {
        formatter: (v) => v >= 10000 ? (v / 10000).toFixed(1) + 'w' : v
      }
    },
    series: [{
      type: 'bar',
      data: data.map(d => d[yField]),
      itemStyle: { 
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color },
          { offset: 1, color: color.replace(')', ', 0.6)').replace('rgb', 'rgba') }
        ])
      },
      barMaxWidth: 40
    }]
  }
}

/**
 * 创建饼图配置
 */
export function createPieChartOption(data, config = {}) {
  const { 
    title, 
    nameField = 'name', 
    valueField = 'value',
    radius = ['40%', '70%']
  } = config

  return {
    title: title ? { text: title, left: 'center', textStyle: { fontSize: 14 } } : undefined,
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left',
      top: 'middle'
    },
    series: [{
      type: 'pie',
      radius,
      center: ['50%', '50%'],
      data: data.map(d => ({ name: d[nameField], value: d[valueField] })),
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      },
      label: {
        show: false,
        position: 'center'
      },
      labelLine: {
        show: false
      }
    }]
  }
}

export default useChart
