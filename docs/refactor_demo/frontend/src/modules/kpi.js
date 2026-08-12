/**
 * KPI 模块 — 从 static/js/kpi.js 迁移
 *
 * 原始方式：全局函数挂载到 window，通过 bundle.js 拼接加载
 * 重构后：ES Module，按需 import
 */
import { api } from '../core/api.js'

// 模块状态
let currentDim = 'monthly'
let currentPeriod = null

/**
 * 初始化 KPI 模块
 */
export function initKpi() {
  loadKpiData()
  bindEvents()
}

/**
 * 加载 KPI 数据 — 替代原始 fetch('/api/kpi') 调用
 */
async function loadKpiData() {
  try {
    showLoading()

    // 获取可用周期
    if (!currentPeriod) {
      const periods = await api.get('/periods', { dim: currentDim })
      currentPeriod = periods[0] || null
    }

    if (!currentPeriod) {
      showEmpty()
      return
    }

    // 并行请求 KPI 和趋势数据
    const [kpiData, trendData] = await Promise.all([
      api.get('/kpi', { dim: currentDim, period: currentPeriod }),
      api.get('/trend', { dim: currentDim, period: currentPeriod }),
    ])

    renderKpiCards(kpiData)
    renderTrendChart(trendData)
  } catch (err) {
    console.error('KPI load failed:', err)
    showError('数据加载失败')
  }
}

/**
 * 渲染 KPI 卡片
 */
function renderKpiCards(data) {
  const container = document.getElementById('kpi-cards')
  if (!container) return

  const cards = [
    { label: '支付金额', value: data.payment_amount, format: 'wan' },
    { label: '退款金额', value: data.refund_amount, format: 'wan' },
    { label: '净销售额', value: data.net_sales, format: 'wan' },
    { label: '支付件数', value: data.payment_qty, format: 'number' },
    { label: '支付买家', value: data.buyers, format: 'number' },
  ]

  container.innerHTML = cards.map(card => {
    const change = card.value.change
    const changeClass = change >= 0 ? 'positive' : 'negative'
    const changeIcon = change >= 0 ? '↑' : '↓'

    return `
      <div class="kpi-card">
        <div class="kpi-label">${card.label}</div>
        <div class="kpi-value">${formatValue(card.value.value, card.format)}</div>
        <div class="kpi-change ${changeClass}">
          ${changeIcon} ${(Math.abs(change) * 100).toFixed(1)}%
          <span class="kpi-prev">环比</span>
        </div>
      </div>
    `
  }).join('')
}

/**
 * 渲染趋势图表
 */
function renderTrendChart(data) {
  const chartEl = document.getElementById('trend-chart')
  if (!chartEl) return

  // 动态导入 ECharts（Vite 会自动 code-split）
  import('echarts').then(echarts => {
    const chart = echarts.init(chartEl)
    chart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: data.data.map(d => d.date),
      },
      yAxis: { type: 'value' },
      series: [{
        type: 'line',
        data: data.data.map(d => d.value),
        smooth: true,
      }],
    })

    // 响应式
    window.addEventListener('resize', () => chart.resize())
  })
}

/**
 * 绑定事件
 */
function bindEvents() {
  // 维度切换
  document.querySelectorAll('[data-dim]').forEach(el => {
    el.addEventListener('click', () => {
      currentDim = el.dataset.dim
      currentPeriod = null
      loadKpiData()
    })
  })

  // 周期切换
  document.querySelectorAll('[data-period]').forEach(el => {
    el.addEventListener('click', () => {
      currentPeriod = el.dataset.period
      loadKpiData()
    })
  })
}

// --- 工具函数 ---

function formatValue(value, format) {
  if (value === null || value === undefined) return '0'
  if (format === 'wan') {
    return Math.abs(value) >= 10000
      ? (value / 10000).toFixed(1) + '万'
      : value.toFixed(0)
  }
  return value.toLocaleString()
}

function showLoading() {
  const container = document.getElementById('kpi-cards')
  if (container) container.innerHTML = '<div class="loading">加载中...</div>'
}

function showEmpty() {
  const container = document.getElementById('kpi-cards')
  if (container) container.innerHTML = '<div class="empty">暂无数据</div>'
}

function showError(msg) {
  const container = document.getElementById('kpi-cards')
  if (container) container.innerHTML = `<div class="error">${msg}</div>`
}
