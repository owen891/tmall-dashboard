import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
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
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
