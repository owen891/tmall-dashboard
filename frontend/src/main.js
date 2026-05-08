import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import CommonComponents from '@/components/index.js'
import './styles/dark-theme.css'
import './styles/global-utils.css'
import './styles/page.scss'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import { setupGlobalErrorHandler } from './utils/globalErrorHandler'

const app = createApp(App)

setupGlobalErrorHandler(app)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

const pinia = createPinia()
app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.use(CommonComponents)

const savedTheme = localStorage.getItem('dashboardTheme')
if (savedTheme === 'dark') {
  document.documentElement.classList.add('dark')
  document.body.classList.add('dark-theme')
}

app.mount('#app')

const authStore = useAuthStore()
authStore.init().catch((err) => {
  console.warn('Auth init failed:', err)
})
