import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'CommandTower',
    component: () => import('@/views/CommandTower.vue')
  },
  {
    path: '/data-goals',
    name: 'DataGoalsCenter',
    component: () => import('@/views/DataGoalsCenter.vue')
  },
  {
    path: '/experiment-asset',
    name: 'ExperimentAssetCenter',
    component: () => import('@/views/ExperimentAssetCenter.vue')
  },
  {
    path: '/execute-monitor',
    name: 'ExecuteMonitorCenter',
    component: () => import('@/views/ExecuteMonitorCenter.vue')
  },
  {
    path: '/tools-system',
    name: 'ToolsSystemCenter',
    component: () => import('@/views/ToolsSystemCenter.vue')
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue')
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
    path: '/quadrant',
    name: 'Quadrant',
    component: () => import('@/views/Quadrant.vue')
  },
  {
    path: '/kpi',
    name: 'KPI',
    component: () => import('@/views/KPI.vue')
  },
  {
    path: '/trends',
    name: 'Trends',
    component: () => import('@/views/Trends.vue')
  },
  {
    path: '/ads',
    name: 'Ads',
    component: () => import('@/views/Ads.vue')
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
    path: '/refunds',
    name: 'Refunds',
    component: () => import('@/views/Refunds.vue')
  },
  {
    path: '/targets',
    name: 'Targets',
    component: () => import('@/views/Targets.vue')
  },
  {
    path: '/pace',
    name: 'Pace',
    component: () => import('@/views/Pace.vue')
  },
  {
    path: '/alerts',
    name: 'Alerts',
    component: () => import('@/views/Alerts.vue')
  },
  {
    path: '/reviews',
    name: 'Reviews',
    component: () => import('@/views/Reviews.vue')
  },
  {
    path: '/market',
    name: 'Market',
    component: () => import('@/views/Market.vue')
  },
  {
    path: '/toolbox',
    name: 'Toolbox',
    component: () => import('@/views/Toolbox.vue')
  },
  {
    path: '/channel/:id?',
    name: 'ChannelDetail',
    component: () => import('@/views/ChannelDetail.vue')
  },
  {
    path: '/promotion',
    name: 'Promotion',
    component: () => import('@/views/Promotion.vue')
  },
  {
    path: '/lifecycle',
    name: 'Lifecycle',
    component: () => import('@/views/Lifecycle.vue')
  },
  {
    path: '/compare',
    name: 'Compare',
    component: () => import('@/views/Compare.vue')
  },
  {
    path: '/profit',
    name: 'Profit',
    component: () => import('@/views/Profit.vue')
  },
  {
    path: '/inventory',
    name: 'Inventory',
    component: () => import('@/views/Inventory.vue')
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
    path: '/attribution',
    name: 'Attribution',
    component: () => import('@/views/Attribution.vue')
  },
  {
    path: '/funnel',
    name: 'Funnel',
    component: () => import('@/views/Funnel.vue')
  },
  {
    path: '/prediction',
    name: 'Prediction',
    component: () => import('@/views/Prediction.vue')
  },
  {
    path: '/data-quality',
    name: 'DataQuality',
    component: () => import('@/views/DataQuality.vue')
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue')
  },
  {
    path: '/backup',
    name: 'Backup',
    component: () => import('@/views/Backup.vue')
  },
  {
    path: '/crowd-asset',
    name: 'CrowdAsset',
    component: () => import('@/views/CrowdAsset.vue')
  },
  {
    path: '/abtest-sop',
    name: 'ABTestSop',
    component: () => import('@/views/ABTestSop.vue')
  },
  {
    path: '/efficiency',
    name: 'Efficiency',
    component: () => import('@/views/Efficiency.vue')
  },
  {
    path: '/smart-alert',
    name: 'SmartAlert',
    component: () => import('@/views/SmartAlert.vue')
  },
  {
    path: '/import-center',
    name: 'ImportCenter',
    component: () => import('@/views/ImportCenter.vue')
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
    path: '/promotion-analysis',
    name: 'PromotionAnalysis',
    component: () => import('@/views/PromotionAnalysis.vue')
  },
  {
    path: '/backup-management',
    name: 'BackupManagement',
    component: () => import('@/views/BackupManagement.vue')
  },
  {
    path: '/advanced-import',
    name: 'AdvancedImport',
    component: () => import('@/views/AdvancedImportCenter.vue')
  },
  {
    path: '/data-visualization',
    name: 'DataVisualization',
    component: () => import('@/views/DataVisualization.vue')
  },
  {
    path: '/ai-analytics',
    name: 'AIAnalytics',
    component: () => import('@/views/AIAnalytics.vue')
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
