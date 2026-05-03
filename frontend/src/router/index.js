import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'CommandTower',
    component: () => import('@/views/CommandTower.vue')
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
    path: '/product-ranking',
    name: 'ProductRanking',
    component: () => import('@/views/ProductRanking.vue')
  },
  {
    path: '/traffic',
    name: 'Traffic',
    component: () => import('@/views/Traffic.vue')
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
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
