import { createRouter, createWebHistory } from 'vue-router'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'

NProgress.configure({ showSpinner: false })

const routes = [
  {
    path: '/',
    name: 'CommandTower',
    component: () => import('@/views/CommandTower.vue'),
    meta: { title: '指挥塔' }
  },
  {
    path: '/products',
    name: 'Products',
    component: () => import('@/views/Products.vue'),
    meta: { title: '商品列表' }
  },
  {
    path: '/product/:id',
    name: 'ProductDetail',
    component: () => import('@/views/ProductDetail.vue'),
    meta: { title: '商品详情' }
  },
  {
    path: '/product-ranking',
    name: 'ProductRanking',
    component: () => import('@/views/ProductRanking.vue'),
    meta: { title: '商品排行' }
  },
  {
    path: '/ranking',
    redirect: '/product-ranking'
  },
  {
    path: '/dashboard',
    redirect: '/'
  },
  {
    path: '/traffic-analysis',
    name: 'TrafficAnalysis',
    component: () => import('@/views/TrafficAnalysis.vue'),
    meta: { title: '流量分析' }
  },
  {
    path: '/lifecycle',
    name: 'Lifecycle',
    component: () => import('@/views/Lifecycle.vue'),
    meta: { title: '生命周期' }
  },
  {
    path: '/inventory',
    name: 'Inventory',
    component: () => import('@/views/Inventory.vue'),
    meta: { title: '库存预警' }
  },
  {
    path: '/ads',
    name: 'Ads',
    component: () => import('@/views/Ads.vue'),
    meta: { title: '广告投放' }
  },
  {
    path: '/profit',
    name: 'Profit',
    component: () => import('@/views/Profit.vue'),
    meta: { title: '利润分析' }
  },
  {
    path: '/kpi',
    name: 'KPI',
    component: () => import('@/views/KPI.vue'),
    meta: { title: 'KPI管理' }
  },
  {
    path: '/funnel',
    name: 'Funnel',
    component: () => import('@/views/Funnel.vue'),
    meta: { title: '转化漏斗' }
  },
  {
    path: '/reviews',
    name: 'Reviews',
    component: () => import('@/views/Reviews.vue'),
    meta: { title: '评价分析' }
  },
  {
    path: '/trends',
    name: 'Trends',
    component: () => import('@/views/Trends.vue'),
    meta: { title: '趋势分析' }
  },
  {
    path: '/health',
    name: 'Health',
    component: () => import('@/views/Health.vue'),
    meta: { title: '健康度' }
  },
  {
    path: '/operations',
    name: 'Operations',
    component: () => import('@/views/Operations.vue'),
    meta: { title: '运营动作' }
  },
  {
    path: '/market',
    name: 'Market',
    component: () => import('@/views/Market.vue'),
    meta: { title: '市场分析' }
  },
  {
    path: '/compare',
    name: 'Compare',
    component: () => import('@/views/Compare.vue'),
    meta: { title: '对比分析' }
  },
  {
    path: '/targets',
    name: 'Targets',
    component: () => import('@/views/Targets.vue'),
    meta: { title: '目标管理' }
  },
  {
    path: '/toolbox',
    name: 'Toolbox',
    component: () => import('@/views/Toolbox.vue'),
    meta: { title: '工具箱' }
  },
  {
    path: '/efficiency',
    name: 'Efficiency',
    component: () => import('@/views/Efficiency.vue'),
    meta: { title: '效率分析' }
  },
  {
    path: '/alerts',
    name: 'Alerts',
    component: () => import('@/views/Alerts.vue'),
    meta: { title: '告警管理' }
  },
  {
    path: '/refunds',
    name: 'Refunds',
    component: () => import('@/views/Refunds.vue'),
    meta: { title: '退款分析' }
  },
  {
    path: '/quadrant',
    name: 'Quadrant',
    component: () => import('@/views/Quadrant.vue'),
    meta: { title: '四象限分析' }
  },
  {
    path: '/pace',
    name: 'Pace',
    component: () => import('@/views/Pace.vue'),
    meta: { title: '进度分析' }
  },
  {
    path: '/prediction',
    name: 'Prediction',
    component: () => import('@/views/Prediction.vue'),
    meta: { title: '预测分析' }
  },
  {
    path: '/promotion',
    name: 'Promotion',
    component: () => import('@/views/Promotion.vue'),
    meta: { title: '促销活动' }
  },
  {
    path: '/recommendation',
    name: 'Recommendation',
    component: () => import('@/views/Recommendation.vue'),
    meta: { title: '推荐系统' }
  },
  {
    path: '/report',
    name: 'Report',
    component: () => import('@/views/Report.vue'),
    meta: { title: '报表中心' }
  },
  {
    path: '/import',
    name: 'Import',
    component: () => import('@/views/Import.vue'),
    meta: { title: '数据导入' }
  },
  {
    path: '/smart-import',
    name: 'SmartImport',
    component: () => import('@/views/SmartImport.vue'),
    meta: { title: '智能导入' }
  },
  {
    path: '/smart-alert',
    name: 'SmartAlert',
    component: () => import('@/views/SmartAlert.vue'),
    meta: { title: '智能告警' }
  },
  {
    path: '/ai-analytics',
    name: 'AIAnalytics',
    component: () => import('@/views/AIAnalytics.vue'),
    meta: { title: 'AI分析' }
  },
  {
    path: '/attribution',
    name: 'Attribution',
    component: () => import('@/views/Attribution.vue'),
    meta: { title: '归因分析' }
  },
  {
    path: '/backup',
    name: 'Backup',
    component: () => import('@/views/Backup.vue'),
    meta: { title: '数据备份' }
  },
  {
    path: '/backup-management',
    name: 'BackupManagement',
    component: () => import('@/views/BackupManagement.vue'),
    meta: { title: '备份管理' }
  },
  {
    path: '/channel-detail',
    name: 'ChannelDetail',
    component: () => import('@/views/ChannelDetail.vue'),
    meta: { title: '渠道详情' }
  },
  {
    path: '/collaboration',
    name: 'Collaboration',
    component: () => import('@/views/Collaboration.vue'),
    meta: { title: '协同工作' }
  },
  {
    path: '/crowd-asset',
    name: 'CrowdAsset',
    component: () => import('@/views/CrowdAsset.vue'),
    meta: { title: '人群资产' }
  },
  {
    path: '/data-quality',
    name: 'DataQuality',
    component: () => import('@/views/DataQuality.vue'),
    meta: { title: '数据质量' }
  },
  {
    path: '/data-visualization',
    name: 'DataVisualization',
    component: () => import('@/views/DataVisualization.vue'),
    meta: { title: '数据可视化' }
  },
  {
    path: '/import-center',
    name: 'ImportCenter',
    component: () => import('@/views/ImportCenter.vue'),
    meta: { title: '导入中心' }
  },
  {
    path: '/advanced-import-center',
    name: 'AdvancedImportCenter',
    component: () => import('@/views/AdvancedImportCenter.vue'),
    meta: { title: '高级导入' }
  },
  {
    path: '/abtest-sop',
    name: 'ABTestSop',
    component: () => import('@/views/ABTestSop.vue'),
    meta: { title: 'A/B测试' }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue'),
    meta: { title: '系统设置' }
  },
  {
    path: '/promotion-analysis',
    name: 'PromotionAnalysis',
    component: () => import('@/views/PromotionAnalysis.vue'),
    meta: { title: '促销分析' }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/CommandTower.vue'),
    meta: { title: '页面不存在' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    return { top: 0, behavior: 'smooth' }
  }
})

router.beforeEach((to, from, next) => {
  NProgress.start()
  document.title = to.meta?.title ? `${to.meta.title} - 海贝海运营系统` : '海贝海运营系统'
  next()
})

router.afterEach(() => {
  NProgress.done()
})

router.onError((error) => {
  NProgress.done()
  console.error('Router error:', error)
})

export default router
