import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'CommandTower',
    component: () => import('@/views/CommandTower.vue')
  },
  {
    path: '/products',
    name: 'Products',
    component: () => import('@/views/Products.vue')
  },
  {
    path: '/product/:id',
    name: 'ProductDetail',
    component: () => import('@/views/ProductDetail.vue')
  },
  {
    path: '/product-ranking',
    name: 'ProductRanking',
    component: () => import('@/views/ProductRanking.vue')
  },
  {
    path: '/traffic-analysis',
    name: 'TrafficAnalysis',
    component: () => import('@/views/TrafficAnalysis.vue')
  },
  {
    path: '/lifecycle',
    name: 'Lifecycle',
    component: () => import('@/views/Lifecycle.vue')
  },
  {
    path: '/inventory',
    name: 'Inventory',
    component: () => import('@/views/Inventory.vue')
  },
  {
    path: '/ads',
    name: 'Ads',
    component: () => import('@/views/Ads.vue')
  },
  {
    path: '/profit',
    name: 'Profit',
    component: () => import('@/views/Profit.vue')
  },
  {
    path: '/kpi',
    name: 'KPI',
    component: () => import('@/views/KPI.vue')
  },
  {
    path: '/funnel',
    name: 'Funnel',
    component: () => import('@/views/Funnel.vue')
  },
  {
    path: '/reviews',
    name: 'Reviews',
    component: () => import('@/views/Reviews.vue')
  },
  {
    path: '/trends',
    name: 'Trends',
    component: () => import('@/views/Trends.vue')
  },
  {
    path: '/health',
    name: 'Health',
    component: () => import('@/views/Health.vue')
  },
  {
    path: '/operations',
    name: 'Operations',
    component: () => import('@/views/Operations.vue')
  },
  {
    path: '/market',
    name: 'Market',
    component: () => import('@/views/Market.vue')
  },
  {
    path: '/compare',
    name: 'Compare',
    component: () => import('@/views/Compare.vue')
  },
  {
    path: '/targets',
    name: 'Targets',
    component: () => import('@/views/Targets.vue')
  },
  {
    path: '/toolbox',
    name: 'Toolbox',
    component: () => import('@/views/Toolbox.vue')
  },
  {
    path: '/efficiency',
    name: 'Efficiency',
    component: () => import('@/views/Efficiency.vue')
  },
  {
    path: '/alerts',
    name: 'Alerts',
    component: () => import('@/views/Alerts.vue')
  },
  {
    path: '/refunds',
    name: 'Refunds',
    component: () => import('@/views/Refunds.vue')
  },
  {
    path: '/quadrant',
    name: 'Quadrant',
    component: () => import('@/views/Quadrant.vue')
  },
  {
    path: '/pace',
    name: 'Pace',
    component: () => import('@/views/Pace.vue')
  },
  {
    path: '/prediction',
    name: 'Prediction',
    component: () => import('@/views/Prediction.vue')
  },
  {
    path: '/promotion',
    name: 'Promotion',
    component: () => import('@/views/Promotion.vue')
  },
  {
    path: '/recommendation',
    name: 'Recommendation',
    component: () => import('@/views/Recommendation.vue')
  },
  {
    path: '/report',
    name: 'Report',
    component: () => import('@/views/Report.vue')
  },
  {
    path: '/import',
    name: 'Import',
    component: () => import('@/views/Import.vue')
  },
  {
    path: '/smart-import',
    name: 'SmartImport',
    component: () => import('@/views/SmartImport.vue')
  },
  {
    path: '/smart-alert',
    name: 'SmartAlert',
    component: () => import('@/views/SmartAlert.vue')
  },
  {
    path: '/ai-analytics',
    name: 'AIAnalytics',
    component: () => import('@/views/AIAnalytics.vue')
  },
  {
    path: '/attribution',
    name: 'Attribution',
    component: () => import('@/views/Attribution.vue')
  },
  {
    path: '/backup',
    name: 'Backup',
    component: () => import('@/views/Backup.vue')
  },
  {
    path: '/backup-management',
    name: 'BackupManagement',
    component: () => import('@/views/BackupManagement.vue')
  },
  {
    path: '/channel-detail',
    name: 'ChannelDetail',
    component: () => import('@/views/ChannelDetail.vue')
  },
  {
    path: '/collaboration',
    name: 'Collaboration',
    component: () => import('@/views/Collaboration.vue')
  },
  {
    path: '/crowd-asset',
    name: 'CrowdAsset',
    component: () => import('@/views/CrowdAsset.vue')
  },
  {
    path: '/data-quality',
    name: 'DataQuality',
    component: () => import('@/views/DataQuality.vue')
  },
  {
    path: '/data-visualization',
    name: 'DataVisualization',
    component: () => import('@/views/DataVisualization.vue')
  },
  {
    path: '/import-center',
    name: 'ImportCenter',
    component: () => import('@/views/ImportCenter.vue')
  },
  {
    path: '/advanced-import-center',
    name: 'AdvancedImportCenter',
    component: () => import('@/views/AdvancedImportCenter.vue')
  },
  {
    path: '/abtest-sop',
    name: 'ABTestSop',
    component: () => import('@/views/ABTestSop.vue')
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue')
  },
  {
    path: '/promotion-analysis',
    name: 'PromotionAnalysis',
    component: () => import('@/views/PromotionAnalysis.vue')
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
