import * as echarts from 'echarts'
import { onBeforeUnmount } from 'vue'

export function useChartManager() {
  const charts = new Map()
  let resizeHandler = null

  const initChart = (ref) => {
    if (!ref?.value) return null
    const existing = charts.get(ref)
    if (existing) {
      existing.dispose()
    }
    const chart = echarts.init(ref.value)
    charts.set(ref, chart)
    return chart
  }

  const getChart = (ref) => {
    return charts.get(ref) || null
  }

  const setOption = (ref, option) => {
    let chart = charts.get(ref)
    if (!chart && ref?.value) {
      chart = initChart(ref)
    }
    if (chart) {
      chart.setOption(option)
    }
  }

  const showEmpty = (ref, message = '暂无数据') => {
    setOption(ref, {
      title: {
        text: message,
        left: 'center',
        top: 'center',
        textStyle: { color: '#999', fontSize: 14, fontWeight: 'normal' }
      },
      xAxis: { show: false },
      yAxis: { show: false },
      series: []
    })
  }

  const setupResize = () => {
    resizeHandler = () => {
      charts.forEach((chart) => {
        if (chart && !chart.isDisposed()) {
          chart.resize()
        }
      })
    }
    window.addEventListener('resize', resizeHandler)
  }

  const disposeAll = () => {
    charts.forEach((chart) => {
      if (chart && !chart.isDisposed()) {
        chart.dispose()
      }
    })
    charts.clear()
    if (resizeHandler) {
      window.removeEventListener('resize', resizeHandler)
      resizeHandler = null
    }
  }

  onBeforeUnmount(() => {
    disposeAll()
  })

  return {
    initChart,
    getChart,
    setOption,
    showEmpty,
    setupResize,
    disposeAll
  }
}
