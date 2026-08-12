/**
 * Vite 配置
 *
 * 替代手动拼接 bundle.js 的方式。
 * 开发时热更新，构建时自动压缩、tree-shaking、代码分割。
 */
import { defineConfig } from 'vite'
import { resolve } from 'path'

export default defineConfig({
  root: 'frontend',
  base: '/static/dist/',

  build: {
    outDir: '../static/dist',
    emptyOutDir: true,

    // 代码分割：按模块拆分 chunk
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'frontend/src/main.js'),
      },
      output: {
        entryFileNames: '[name].js',
        chunkFileNames: 'chunks/[name]-[hash].js',
        assetFileNames: 'assets/[name].[ext]',

        // 手动分包
        manualChunks(id) {
          if (id.includes('node_modules/echarts')) {
            return 'echarts'
          }
          if (id.includes('node_modules/dayjs')) {
            return 'dayjs'
          }
          // 按功能模块分包
          if (id.includes('/modules/kpi')) return 'kpi'
          if (id.includes('/modules/products')) return 'products'
          if (id.includes('/modules/market')) return 'market'
          if (id.includes('/modules/health')) return 'health'
        },
      },
    },
  },

  // 开发服务器代理
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
    },
  },
})
