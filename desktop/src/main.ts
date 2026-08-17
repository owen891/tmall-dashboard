import { app, BrowserWindow, dialog, ipcMain, Menu, nativeImage, Tray, type OpenDialogOptions } from 'electron'
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
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
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

function createTray(): void {
  const icon = nativeImage.createFromPath(process.execPath)
  tray = new Tray(icon.isEmpty() ? nativeImage.createEmpty() : icon)
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
  createTray()
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
