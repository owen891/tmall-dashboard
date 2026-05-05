import { ref, onBeforeUnmount, shallowRef } from 'vue'
import * as echarts from 'echarts'

export function useECharts(containerRef) {
  const chart = shallowRef(null)

  const initChart = () => {
    if (containerRef.value && !chart.value) {
      chart.value = echarts.init(containerRef.value)
    }
    return chart.value
  }

  const handleResize = () => {
    chart.value?.resize()
  }

  const setupResize = () => {
    window.addEventListener('resize', handleResize)
  }

  const disposeChart = () => {
    window.removeEventListener('resize', handleResize)
    if (chart.value) {
      chart.value.dispose()
      chart.value = null
    }
  }

  onBeforeUnmount(() => {
    disposeChart()
  })

  return {
    chart,
    initChart,
    setupResize,
    disposeChart,
    handleResize,
  }
}
