(function () {
  const panel = document.querySelector('[data-sidebar-meta]') || document.querySelector('[data-desktop-settings]')
  const desktop = window.tmallDesktop
  if (!panel) return

  const sidebar = panel.matches('[data-sidebar-meta]')
  const version = panel.querySelector(sidebar ? '[data-sidebar-version]' : '[data-desktop-version]')
  const button = panel.querySelector(sidebar ? '[data-sidebar-check-update]' : '[data-desktop-check-update]')
  const status = panel.querySelector(sidebar ? '[data-sidebar-update-status]' : '[data-desktop-update-status]')

  const project = window.TMALL_PROJECT || {
    latestRelease: 'https://gitcode.com/owen891/tmall-dashboard/releases/latest',
    latestReleaseApi: 'https://gitcode.com/api/v5/repos/owen891/tmall-dashboard/releases/latest',
  }
  const normalizeVersion = value => {
    const normalized = String(value ?? '').trim().replace(/^v/i, '')
    return /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(normalized) ? normalized : null
  }
  const newerThan = (candidate, current) => {
    const next = normalizeVersion(candidate)?.split('.').map(Number)
    const installed = normalizeVersion(current)?.split('.').map(Number)
    if (!next || !installed) return false
    return next.some((part, index) => part !== installed[index] && part > installed[index])
  }
  const currentVersion = () => window.TMALL_WEB_VERSION || version?.textContent?.trim() || '0.0.0'
  const setStatus = (text, title = text) => {
    if (!status) return
    status.textContent = text
    status.title = title
  }
  const checkRelease = async () => {
    if (button) button.disabled = true
    setStatus('检查中…', '正在检查 GitCode 更新…')
    try {
      const response = await fetch(project.latestReleaseApi, { cache: 'no-store', headers: { Accept: 'application/json' } })
      if (!response.ok) throw new Error('暂时无法连接 GitCode')
      const release = await response.json()
      const latestVersion = normalizeVersion(release?.tag_name || release?.name)
      if (!latestVersion) throw new Error('GitCode Release 版本号不可识别')
      if (newerThan(latestVersion, currentVersion())) setStatus('有新版本', `发现新版本 v${latestVersion}，请查看更新说明后升级。`)
      else setStatus('最新', `已是最新版本；GitCode Release v${latestVersion}`)
    } catch (error) {
      setStatus('检查失败', error.message || 'GitCode 更新检查失败，请稍后重试。')
    } finally {
      if (button) button.disabled = false
    }
  }

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
    const text = statusText(update)
    if (!status) return
    if (!sidebar) {
      status.textContent = text
      return
    }
    const compact = {
      '正在检查更新…': '检查中…',
      '当前已是最新版本': '最新',
      '开发版不检查在线更新': '开发版',
    }[text] || (text.startsWith('发现新版本') ? '有新版本' : text.startsWith('检查更新失败') ? '检查失败' : text)
    setStatus(compact, text)
  }

  panel.hidden = false
  if (!desktop?.isDesktop) {
    button?.removeAttribute('hidden')
    if (button) button.querySelector('span')?.replaceChildren(document.createTextNode('检查升级'))
    if (window.TMALL_WEB_VERSION && version) version.textContent = window.TMALL_WEB_VERSION
    fetch(new URL('../api/version?client=web', new URL('.', document.currentScript?.src || window.location.href)))
      .then(response => response.ok ? response.json() : null)
      .then(payload => { if (payload?.data?.version && version) version.textContent = payload.data.version })
      .catch(() => {})
    button?.addEventListener('click', checkRelease)
    return
  }
  if (button) button.hidden = false
  if (button) button.querySelector('span')?.replaceChildren(document.createTextNode('检查更新'))
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
