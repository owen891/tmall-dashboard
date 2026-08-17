(function () {
  const panel = document.querySelector('[data-desktop-settings]')
  const desktop = window.tmallDesktop
  if (!panel || !desktop?.isDesktop) return

  const version = panel.querySelector('[data-desktop-version]')
  const button = panel.querySelector('[data-desktop-check-update]')
  const status = panel.querySelector('[data-desktop-update-status]')

  const statusText = update => {
    if (!update || typeof update !== 'object') return '更新状态未知'
    if (update.state === 'checking') return '正在检查更新…'
    if (update.state === 'available') return `发现新版本 ${update.version}`
    if (update.state === 'not-available') return '当前已是最新版本'
    if (update.state === 'downloading') return `正在下载更新 ${Math.round(update.percent || 0)}%`
    if (update.state === 'downloaded') return `新版本 ${update.version} 已下载`
    if (update.state === 'development') return '开发版不检查在线更新'
    if (update.state === 'error') return `检查更新失败：${update.message || '未知错误'}`
    return '更新状态未知'
  }

  const renderStatus = update => {
    if (status) status.textContent = statusText(update)
  }

  panel.hidden = false
  desktop.getVersion().then(value => {
    if (version) version.textContent = value
  }).catch(() => {
    if (version) version.textContent = '--'
  })

  button?.addEventListener('click', async () => {
    button.disabled = true
    renderStatus({ state: 'checking' })
    try {
      renderStatus(await desktop.checkForUpdates())
    } finally {
      button.disabled = false
    }
  })

  desktop.onUpdateStatus?.(renderStatus)
})()
