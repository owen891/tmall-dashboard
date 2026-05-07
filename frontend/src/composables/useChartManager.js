import { ref, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'

export function useChartManager() {
  const charts = new Map()
  let resizeHandler = null
  let resizeObserver = null

  const initChart = (elRef, options = {}) => {
    if (!elRef.value) return null
    
    const chart = echarts.init(elRef.value)
    const key = elRef.value.getAttribute('data-chart-id') || Math.random().toString(36).slice(2)
    elRef.value.setAttribute('data-chart-id', key)
    
    charts.set(key, { chart, elRef })
    
    if (options.option) {
      chart.setOption(options.option)
    }
    
    return chart
  }

  const getChart = (elRef) => {
    if (!elRef.value) return null
    const key = elRef.value.getAttribute('data-chart-id')
    return key ? charts.get(key)?.chart : null
  }

  const setOption = (elRef, option) => {
    const chart = getChart(elRef)
    if (chart) {
      chart.setOption(option, true)
    }
  }

  const showEmpty = (elRef, text = '暂无数据') => {
    const chart = getChart(elRef)
    if (chart) {
      chart.setOption({
        title: { text, left: 'center', top: 'center', textStyle: { color: '#999', fontSize: 14 } },
        xAxis: { show: false },
        yAxis: { show: false },
        series: []
      }, true)
    }
  }

  const resize = () => {
    charts.forEach(({ chart }) => {
      chart?.resize()
    })
  }

  const dispose = () => {
    charts.forEach(({ chart }) => {
      chart?.dispose()
    })
    charts.clear()
  }

  const setupResize = (useObserver = true) => {
    if (useObserver && window.ResizeObserver) {
      resizeObserver = new ResizeObserver(() => {
        resize()
      })
      charts.forEach(({ elRef }) => {
        if (elRef.value) resizeObserver.observe(elRef.value)
      })
    } else {
      resizeHandler = () => resize()
      window.addEventListener('resize', resizeHandler)
    }
  }

  const cleanup = () => {
    if (resizeHandler) {
      window.removeEventListener('resize', resizeHandler)
      resizeHandler = null
    }
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
    dispose()
  }

  onBeforeUnmount(() => {
    cleanup()
  })

  return {
    initChart,
    getChart,
    setOption,
    showEmpty,
    resize,
    dispose,
    setupResize,
    cleanup
  }
}
