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
    component: () => import('@/views/ProductsSimplified.vue')
  },
  {
    path: '/product/:id',
    name: 'ProductDetail',
    component: () => import('@/views/ProductDetail.vue')
  },
  {
    path: '/traffic',
    name: 'Traffic',
    component: () => import('@/views/TrafficSimplified.vue')
  },
  {
    path: '/lifecycle',
    name: 'Lifecycle',
    component: () => import('@/views/Lifecycle.vue')
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
