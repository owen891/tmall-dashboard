import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return

          if (id.includes('element-plus')) {
            if (id.includes('element-plus/es/components')) {
              const match = id.match(/components\/([^/]+)/)
              if (match) return `ep-${match[1]}`
            }
            return 'element-plus'
          }
          if (id.includes('echarts')) {
            if (id.includes('echarts/charts')) return 'echarts-charts'
            if (id.includes('echarts/components')) return 'echarts-components'
            if (id.includes('echarts/renderers')) return 'echarts-renderers'
            if (id.includes('zrender')) return 'echarts-zrender'
            return 'echarts-core'
          }
          if (id.includes('vue') || id.includes('pinia')) return 'vue-core'
          if (id.includes('axios')) return 'axios'
          if (id.includes('xlsx') || id.includes('exceljs')) return 'vendor-xlsx'
          return 'vendor'
        }
      }
    }
  }
})
