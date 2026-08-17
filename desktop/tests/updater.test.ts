import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { isWindowsLockError, pendingUpdateDirectories } from '../src/updater-helpers'

const source = readFileSync(resolve('src/updater.ts'), 'utf-8')

describe('desktop updater contract', () => {
  it('checks once on startup without forcing download', () => {
    expect(source).toContain('autoUpdater.autoDownload = false')
    expect(source).toContain('autoUpdater.autoInstallOnAppQuit = true')
    expect(source).toContain('https://github.com/owen891/tmall-dashboard/releases/latest/download')
    expect(source).not.toContain('setInterval(')
  })

  it('stops the backend before installing an update', () => {
    expect(source.indexOf('await beforeQuitAndInstall()')).toBeGreaterThan(-1)
    expect(source.indexOf('await beforeQuitAndInstall()')).toBeLessThan(source.indexOf('autoUpdater.quitAndInstall()'))
  })

  it('recognizes Windows file lock failures', () => {
    expect(isWindowsLockError(Object.assign(new Error('resource busy'), { code: 'EBUSY' }))).toBe(true)
    expect(isWindowsLockError(Object.assign(new Error('access denied'), { code: 'EPERM' }))).toBe(true)
    expect(isWindowsLockError(new Error('network failed'))).toBe(false)
  })

  it('only targets app-specific pending update directories', () => {
    expect(pendingUpdateDirectories({
      LOCALAPPDATA: 'C:\\Local',
      APPDATA: 'C:\\Roaming',
    })).toEqual([
      'C:\\Local\\TmallDashboard-updater\\pending',
      'C:\\Roaming\\TmallDashboard\\updater\\pending',
    ])
  })
})
