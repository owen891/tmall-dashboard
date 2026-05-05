import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

const shortcuts = new Map()

let globalListener = null

export function useKeyboardShortcuts() {
  const router = useRouter()

  const defaults = {
    'g p': () => router.push('/products'),
    'g d': () => router.push('/'),
    'g r': () => router.push('/product-ranking'),
    'g t': () => router.push('/traffic-analysis'),
    'g l': () => router.push('/lifecycle'),
    'g i': () => router.push('/inventory'),
    'g a': () => router.push('/ads'),
    'g o': () => router.push('/profit'),
    'g k': () => router.push('/kpi'),
    '/': () => {
      const searchInput = document.querySelector('input[type="search"], .search-input')
      if (searchInput) {
        searchInput.focus()
        searchInput.select()
      }
    },
    '?': () => {
      showHelp()
    }
  }

  function showHelp() {
    const helpText = `
      <div style="text-align: left;">
        <h4 style="margin-bottom: 12px;">键盘快捷键</h4>
        <table style="width: 100%;">
          <tr><td><kbd style="padding: 2px 6px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 3px;">g p</kbd></td><td>商品列表</td></tr>
          <tr><td><kbd style="padding: 2px 6px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 3px;">g d</kbd></td><td>指挥塔</td></tr>
          <tr><td><kbd style="padding: 2px 6px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 3px;">g r</kbd></td><td>商品排行</td></tr>
          <tr><td><kbd style="padding: 2px 6px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 3px;">g t</kbd></td><td>流量分析</td></tr>
          <tr><td><kbd style="padding: 2px 6px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 3px;">g l</kbd></td><td>生命周期</td></tr>
          <tr><td><kbd style="padding: 2px 6px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 3px;">g i</kbd></td><td>库存预警</td></tr>
          <tr><td><kbd style="padding: 2px 6px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 3px;">g a</kbd></td><td>广告投放</td></tr>
          <tr><td><kbd style="padding: 2px 6px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 3px;">g o</kbd></td><td>利润分析</td></tr>
          <tr><td><kbd style="padding: 2px 6px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 3px;">g k</kbd></td><td>KPI管理</td></tr>
          <tr><td><kbd style="padding: 2px 6px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 3px;">/</kbd></td><td>聚焦搜索</td></tr>
          <tr><td><kbd style="padding: 2px 6px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 3px;">?</kbd></td><td>显示帮助</td></tr>
          <tr><td><kbd style="padding: 2px 6px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 3px;">Esc</kbd></td><td>取消/返回</td></tr>
        </table>
      </div>
    `

    import('element-plus').then(({ ElMessageBox }) => {
      ElMessageBox.alert(helpText, '快捷键帮助', {
        dangerouslyUseHTMLString: true,
        confirmButtonText: '知道了',
        customClass: 'keyboard-shortcuts-dialog'
      })
    })
  }

  function setupShortcuts() {
    if (globalListener) return

    let sequence = ''
    let timer = null

    globalListener = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) {
        if (e.key === 'Escape') {
          e.target.blur()
        }
        return
      }

      if (e.key === 'Escape') {
        import('element-plus').then(({ ElMessageBox }) => {
          try {
            ElMessageBox.close()
          } catch (err) {}
        })
        return
      }

      if (timer) {
        clearTimeout(timer)
      }

      sequence += (sequence ? ' ' : '') + e.key.toLowerCase()
      
      timer = setTimeout(() => {
        sequence = ''
      }, 1000)

      if (shortcuts.has(sequence)) {
        e.preventDefault()
        shortcuts.get(sequence)()
        sequence = ''
      }
    }

    document.addEventListener('keydown', globalListener)
  }

  function cleanup() {
    if (globalListener) {
      document.removeEventListener('keydown', globalListener)
      globalListener = null
    }
  }

  function addShortcut(keys, handler) {
    shortcuts.set(keys, handler)
  }

  function removeShortcut(keys) {
    shortcuts.delete(keys)
  }

  onMounted(() => {
    Object.entries(defaults).forEach(([keys, handler]) => {
      addShortcut(keys, handler)
    })
    setupShortcuts()
  })

  onUnmounted(() => {
    cleanup()
  })

  return { addShortcut, removeShortcut }
}
