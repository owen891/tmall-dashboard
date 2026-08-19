import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const source = readFileSync(resolve('src/main.ts'), 'utf-8')
const i18nSource = readFileSync(resolve('src/i18n.ts'), 'utf-8')
const preloadSource = readFileSync(resolve('src/preload.ts'), 'utf-8')
const builderConfig = readFileSync(resolve('electron-builder.yml'), 'utf-8')

describe('desktop main process contract', () => {
  it('uses a secure window and one application instance', () => {
    expect(source).toContain('requestSingleInstanceLock()')
    expect(source).toContain('contextIsolation: true')
    expect(source).toContain('sandbox: true')
    expect(source).toContain('nodeIntegration: false')
    expect(source).toContain('Menu.setApplicationMenu(null)')
  })

  it('keeps close-to-tray separate from explicit quit', () => {
    expect(source).toContain("label: '退出天猫数据仪表盘'")
    expect(source).toContain('event.preventDefault()')
    expect(source).toContain('window.hide()')
    expect(source).toContain('await prepareAppShutdown()')
  })

  it('allows navigation inside the local app while blocking external origins', () => {
    expect(source).toContain('const allowedOrigin = new URL(url).origin')
    expect(source).toContain('new URL(event.url).origin !== allowedOrigin')
    expect(source).toContain('event.preventDefault()')
  })

  it('routes tray and settings update checks to the desktop updater', () => {
    expect(i18nSource).toContain("checkForUpdates: '检查更新'")
    expect(source).toContain('label: zhCN.checkForUpdates')
    expect(source).toContain("ipcMain.handle('desktop:check-for-updates'")
    expect(source).toContain('createDesktopUpdater({')
    expect(source).toContain('void checkForUpdates(false)')
  })

  it('exposes a native folder picker for scan jobs', () => {
    expect(source).toContain("ipcMain.handle('desktop:select-scan-folder'")
    expect(source).toContain('dialog.showOpenDialog')
    expect(source).toContain("properties: ['openDirectory']")
    expect(preloadSource).toContain('selectScanFolder')
    expect(preloadSource).toContain("ipcRenderer.invoke('desktop:select-scan-folder')")
  })

  it('packages the current TM logo as the Windows application icon', () => {
    expect(builderConfig).toContain('icon: assets/tmall-dashboard.ico')
  })

  it('defines signed-ready macOS dmg and zip targets for both architectures', () => {
    expect(builderConfig).toContain('target: dmg')
    expect(builderConfig).toContain('target: zip')
    expect(builderConfig).toContain('icon: assets/tmall-dashboard-logo-1024.png')
    expect(builderConfig).toContain('category: public.app-category.business')
    expect(builderConfig).toContain('arm64')
    expect(builderConfig).toContain('x64')
  })

  it('packages a macOS icon at the minimum supported resolution', () => {
    const icon = readFileSync(resolve('assets/tmall-dashboard-logo-1024.png'))
    expect(icon.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a')
    expect(icon.readUInt32BE(16)).toBeGreaterThanOrEqual(512)
    expect(icon.readUInt32BE(20)).toBeGreaterThanOrEqual(512)
  })
})
