import { app, BrowserWindow, dialog, ipcMain, Menu, nativeImage, shell, Tray, type OpenDialogOptions } from 'electron'
import { join } from 'node:path'
import { type BackendHandle, startBackend } from './backend'
import { zhCN } from './i18n'
import { createDesktopUpdater, type DesktopUpdater, type UpdateStatus } from './updater'

let mainWindow: BrowserWindow | null = null
let tray: Tray | null = null
let backend: BackendHandle | null = null
let isQuitting = false
let updater: DesktopUpdater | null = null

function showMainWindow(): void {
  if (!mainWindow) return
  if (mainWindow.isMinimized()) mainWindow.restore()
  mainWindow.show()
  mainWindow.focus()
}

function createMainWindow(url: string): BrowserWindow {
  const allowedOrigin = new URL(url).origin
  const window = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1100,
    minHeight: 720,
    show: false,
    title: zhCN.appName,
    autoHideMenuBar: true,
    webPreferences: {
      preload: join(__dirname, 'preload.js'),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
    },
  })
  window.webContents.setWindowOpenHandler(details => {
    try {
      const target = new URL(details.url)
      if (target.protocol === 'https:' && target.hostname === 'github.com') void shell.openExternal(target.toString())
    } catch {
      // Keep malformed and untrusted popup URLs blocked.
    }
    return { action: 'deny' }
  })
  window.webContents.on('will-navigate', event => {
    if (new URL(event.url).origin !== allowedOrigin) event.preventDefault()
  })
  window.once('ready-to-show', () => window.show())
  window.on('close', event => {
    if (isQuitting) return
    event.preventDefault()
    window.hide()
  })
  void window.loadURL(url)
  return window
}

function rebuildTrayMenu(): void {
  if (!tray) return
  const openAtLogin = app.getLoginItemSettings().openAtLogin
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: zhCN.show, click: showMainWindow },
    { label: zhCN.hide, click: () => mainWindow?.hide() },
    { label: zhCN.checkForUpdates, click: () => { void checkForUpdates() } },
    { type: 'separator' },
    {
      label: zhCN.openAtLogin,
      type: 'checkbox',
      checked: openAtLogin,
      click: item => {
        app.setLoginItemSettings({ openAtLogin: item.checked })
        rebuildTrayMenu()
      },
    },
    { type: 'separator' },
    { label: '退出天猫数据仪表盘', click: () => void quitApp() },
  ]))
}

// 托盘图标解析顺序：打包进 resources 的图标 → exe 自身图标 → 空图。
// 之前只用 app.getFileIcon(process.execPath)：开发态 exe 是 electron.exe，
// 取不到自定义图标，托盘位置就是空白。
function trayIcon(): Electron.NativeImage {
  // 打包态图标在 resources 下；开发态退到仓库内的 assets。
  const roots = app.isPackaged
    ? [process.resourcesPath]
    : [join(__dirname, '..', 'assets'), join(app.getAppPath(), 'assets')]
  const names = process.platform === 'win32' ? ['tray.ico', 'tray.png'] : ['tray.png']
  for (const root of roots) {
    for (const name of names) {
      const candidate = nativeImage.createFromPath(join(root, name))
      if (!candidate.isEmpty()) return candidate
    }
  }
  return nativeImage.createEmpty()
}

async function createTray(): Promise<void> {
  const packaged = trayIcon()
  const icon = packaged.isEmpty()
    ? await app.getFileIcon(process.execPath, { size: 'small' })
    : packaged
  tray = new Tray(icon.isEmpty() ? nativeImage.createFromPath(process.execPath) : icon)
  tray.setToolTip(zhCN.appName)
  tray.on('double-click', showMainWindow)
  rebuildTrayMenu()
}

export async function prepareAppShutdown(): Promise<void> {
  const current = backend
  backend = null
  await current?.stop()
}

async function quitApp(): Promise<void> {
  if (isQuitting) return
  isQuitting = true
  await prepareAppShutdown()
  tray?.destroy()
  app.exit(0)
}

function registerDesktopIpc(): void {
  ipcMain.handle('desktop:get-version', () => app.getVersion())
  ipcMain.handle('desktop:check-for-updates', () => checkForUpdates(true))
  ipcMain.handle('desktop:select-scan-folder', async () => {
    const options: OpenDialogOptions = {
      title: '选择扫描文件夹',
      buttonLabel: '选择此文件夹',
      properties: ['openDirectory'],
    }
    const result = mainWindow
      ? await dialog.showOpenDialog(mainWindow, options)
      : await dialog.showOpenDialog(options)
    return result.canceled ? null : (result.filePaths[0] || null)
  })
}

function checkForUpdates(manual = true): Promise<UpdateStatus> {
  if (!updater) return Promise.resolve({ state: 'error', message: '更新服务尚未就绪' })
  return updater.checkForUpdates(manual)
}

function publishUpdateStatus(status: UpdateStatus): void {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('desktop:update-status', status)
  }
}

async function prepareUpdateInstall(): Promise<void> {
  isQuitting = true
  await prepareAppShutdown()
  tray?.destroy()
}

async function bootstrap(): Promise<void> {
  Menu.setApplicationMenu(null)
  registerDesktopIpc()
  backend = await startBackend(process.resourcesPath)
  mainWindow = createMainWindow(backend.url)
  await createTray()
  updater = createDesktopUpdater({
    beforeQuitAndInstall: prepareUpdateInstall,
    getWindow: () => mainWindow,
    onStatus: publishUpdateStatus,
  })
  void checkForUpdates(false)
}

function run(): void {
  const gotLock = app.requestSingleInstanceLock()
  if (!gotLock) {
    app.quit()
    return
  }
  app.on('second-instance', showMainWindow)
  app.whenReady().then(bootstrap).catch(async error => {
    console.error('[desktop] startup failed', error)
    await dialog.showMessageBox({
      type: 'error',
      title: zhCN.startupFailed,
      message: zhCN.startupFailedDetail,
      detail: error instanceof Error ? error.message : String(error),
    })
    await quitApp()
  })
  app.on('activate', showMainWindow)
  app.on('window-all-closed', () => undefined)
  app.on('before-quit', event => {
    if (isQuitting) return
    event.preventDefault()
    void quitApp()
  })
}

run()
