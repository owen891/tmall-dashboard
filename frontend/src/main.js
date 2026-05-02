import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import './styles/dark-theme.css'

import App from './App.vue'
import router from './router'
import { wsClient } from './utils/websocket'

const app = createApp(App)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

const savedTheme = localStorage.getItem('dashboardTheme')
if (savedTheme === 'dark') {
  document.documentElement.classList.add('dark')
  document.body.classList.add('dark-theme')
}

app.mount('#app')

wsClient.connect()
