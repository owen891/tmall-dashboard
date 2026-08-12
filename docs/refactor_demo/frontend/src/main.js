/**
 * 前端入口 — 替代 bundle.js 的手动拼接
 *
 * 原始方式：14 个 JS 文件手动拼接成 bundle.js（7059 行）
 * 重构后：ES Module import，Vite 自动处理依赖和打包
 */
import './styles/base.css'
import './styles/layout.css'
import './styles/components.css'
import './styles/themes.css'

import { initRouter } from './core/router.js'
import { initTheme } from './core/theme.js'
import { api } from './core/api.js'

// 按需导入模块（Vite 会自动 code-split）
import { initKpi } from './modules/kpi.js'
import { initTrend } from './modules/trend.js'
import { initProducts } from './modules/products.js'
import { initHealth } from './modules/health.js'
import { initMarket } from './modules/market.js'
import { initReview } from './modules/review.js'
import { initAd } from './modules/ad.js'
import { initActions } from './modules/actions.js'
import { initCompare } from './modules/compare.js'
import { initToolbox } from './modules/toolbox.js'

// 模块注册表
const modules = {
  kpi: initKpi,
  trend: initTrend,
  products: initProducts,
  health: initHealth,
  market: initMarket,
  review: initReview,
  ad: initAd,
  actions: initActions,
  compare: initCompare,
  toolbox: initToolbox,
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
  initTheme()
  initRouter(modules)

  // 默认加载 KPI 模块
  modules.kpi()
})
