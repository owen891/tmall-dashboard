import { describe, expect, it } from 'vitest'
import { backendExecutableName, backendLaunchOptions, backendUrl } from '../src/backend'

describe('desktop backend launch', () => {
  it('spawns only the packaged loopback backend', () => {
    const launch = backendLaunchOptions('C:\\Program Files\\TmallDashboard\\resources', 49152, 123, {
      TMALL_BACKEND_EXE: 'C:\\malicious\\Server.exe',
    }, 'win32')

    expect(launch.command).toBe('C:\\Program Files\\TmallDashboard\\resources\\backend\\TmallDashboardServer.exe')
    expect(launch.args).toEqual(['--port', '49152', '--parent-pid', '123'])
    expect(launch.env.TMALL_DESKTOP_MODE).toBe('1')
  })

  it('uses the platform executable name for Windows and macOS', () => {
    expect(backendExecutableName('win32')).toBe('TmallDashboardServer.exe')
    expect(backendExecutableName('darwin')).toBe('TmallDashboardServer')
    const macCommand = backendLaunchOptions('/Applications/TmallDashboard.app/Contents/Resources', 49152, 123, {}, 'darwin').command
    expect(macCommand).toBe('/Applications/TmallDashboard.app/Contents/Resources/backend/TmallDashboardServer')
  })

  it('constructs only loopback backend urls', () => {
    expect(backendUrl(49152)).toBe('http://127.0.0.1:49152')
  })

  it('rejects non-user ports before spawning', () => {
    expect(() => backendLaunchOptions('C:\\resources', 1023, 123)).toThrow(/端口必须在 1024 到 65535 之间/)
    expect(() => backendLaunchOptions('C:\\resources', 65536, 123)).toThrow(/端口必须在 1024 到 65535 之间/)
  })

  it('rejects invalid parent pids with a Chinese error', () => {
    expect(() => backendLaunchOptions('C:\\resources', 49152, 0)).toThrow(/父进程 PID 必须是正整数/)
  })
})
