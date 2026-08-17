import { app, type BrowserWindow, dialog } from 'electron'
import { rm } from 'node:fs/promises'
import { autoUpdater } from 'electron-updater'
import { isWindowsLockError, pendingUpdateDirectories } from './updater-helpers'
import { zhCN } from './i18n'

const UPDATE_FEED_URL = 'https://github.com/owen891/tmall-dashboard/releases/latest/download'

export type UpdateStatus =
  | { state: 'checking' }
  | { state: 'available'; version: string }
  | { state: 'not-available' }
  | { state: 'downloading'; percent: number }
  | { state: 'downloaded'; version: string }
  | { state: 'error'; message: string }
  | { state: 'development' }

interface UpdaterOptions {
  beforeQuitAndInstall: () => Promise<void>
  getWindow: () => BrowserWindow | null
  onStatus: (status: UpdateStatus) => void
}

export interface DesktopUpdater {
  checkForUpdates: (manual?: boolean) => Promise<UpdateStatus>
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

async function clearPendingUpdateCache(): Promise<void> {
  await Promise.all(pendingUpdateDirectories().map(directory => rm(directory, { recursive: true, force: true })))
}

export function createDesktopUpdater(options: UpdaterOptions): DesktopUpdater {
  const { beforeQuitAndInstall } = options
  autoUpdater.setFeedURL({ provider: 'generic', url: UPDATE_FEED_URL })
  autoUpdater.autoDownload = false
  autoUpdater.autoInstallOnAppQuit = true

  let manualCheck = false
  let checking = false
  let lastStatus: UpdateStatus = { state: 'not-available' }

  const publish = (status: UpdateStatus): UpdateStatus => {
    lastStatus = status
    options.onStatus(status)
    return status
  }

  const showMessage = async (messageOptions: Electron.MessageBoxOptions) => {
    const window = options.getWindow()
    return window ? dialog.showMessageBox(window, messageOptions) : dialog.showMessageBox(messageOptions)
  }

  autoUpdater.on('checking-for-update', () => publish({ state: 'checking' }))
  autoUpdater.on('update-not-available', () => {
    publish({ state: 'not-available' })
    if (manualCheck) {
      void showMessage({ type: 'info', title: zhCN.updateTitle, message: zhCN.alreadyLatest, buttons: [zhCN.confirm] })
    }
  })
  autoUpdater.on('update-available', info => {
    publish({ state: 'available', version: info.version })
    void showMessage({
      type: 'info',
      title: zhCN.updateTitle,
      message: zhCN.updateAvailable.replace('{version}', info.version),
      buttons: [zhCN.downloadUpdate, zhCN.later],
      defaultId: 0,
      cancelId: 1,
    }).then(result => {
      if (result.response === 0) void autoUpdater.downloadUpdate()
    })
  })
  autoUpdater.on('download-progress', progress => {
    publish({ state: 'downloading', percent: Math.max(0, Math.min(100, progress.percent)) })
  })
  autoUpdater.on('update-downloaded', info => {
    publish({ state: 'downloaded', version: info.version })
    void showMessage({
      type: 'info',
      title: zhCN.updateTitle,
      message: zhCN.updateDownloaded.replace('{version}', info.version),
      buttons: [zhCN.restartAndInstall, zhCN.installLater],
      defaultId: 0,
      cancelId: 1,
    }).then(async result => {
      if (result.response !== 0) return
      await beforeQuitAndInstall()
      autoUpdater.quitAndInstall()
    })
  })
  autoUpdater.on('error', error => {
    publish({ state: 'error', message: errorMessage(error) })
    if (!isWindowsLockError(error)) return
    void clearPendingUpdateCache().then(() => showMessage({
      type: 'warning',
      title: zhCN.updateTitle,
      message: zhCN.updateFileLocked,
      buttons: [zhCN.retry, zhCN.cancel],
      defaultId: 0,
      cancelId: 1,
    })).then(result => {
      if (result.response === 0) void checkForUpdates(true)
    })
  })

  async function checkForUpdates(manual = true): Promise<UpdateStatus> {
    manualCheck = manual
    if (!app.isPackaged) return publish({ state: 'development' })
    if (checking) return lastStatus
    checking = true
    try {
      await autoUpdater.checkForUpdates()
      return lastStatus
    } catch (error) {
      return publish({ state: 'error', message: errorMessage(error) })
    } finally {
      checking = false
    }
  }

  return { checkForUpdates }
}
