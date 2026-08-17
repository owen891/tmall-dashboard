import { type ChildProcess, execFile, spawn } from 'node:child_process'
import { createServer } from 'node:net'
import { join } from 'node:path'

export interface BackendLaunchOptions {
  command: string
  args: string[]
  env: NodeJS.ProcessEnv
}

export interface BackendHandle {
  child: ChildProcess
  url: string
  stop: () => Promise<void>
}

export function backendLaunchOptions(
  resourcesPath: string,
  port: number,
  parentPid: number,
  environment: NodeJS.ProcessEnv = process.env,
): BackendLaunchOptions {
  if (!Number.isInteger(port) || port < 1024 || port > 65535) {
    throw new RangeError('桌面后端端口必须在 1024 到 65535 之间')
  }
  if (!Number.isInteger(parentPid) || parentPid <= 0) {
    throw new RangeError('桌面父进程 PID 必须是正整数')
  }
  return {
    command: join(resourcesPath, 'backend', 'TmallDashboardServer.exe'),
    args: ['--port', String(port), '--parent-pid', String(parentPid)],
    env: {
      ...environment,
      TMALL_DESKTOP_MODE: '1',
    },
  }
}

export function backendUrl(port: number): string {
  if (!Number.isInteger(port) || port < 1024 || port > 65535) {
    throw new RangeError('桌面后端端口必须在 1024 到 65535 之间')
  }
  return `http://127.0.0.1:${port}`
}

export function reserveLoopbackPort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const listener = createServer()
    listener.once('error', reject)
    listener.listen(0, '127.0.0.1', () => {
      const address = listener.address()
      if (!address || typeof address === 'string') {
        listener.close(() => reject(new Error('无法分配本地服务端口')))
        return
      }
      const port = address.port
      listener.close(error => error ? reject(error) : resolve(port))
    })
  })
}

async function waitForHealth(child: ChildProcess, url: string, timeoutMs = 30_000): Promise<void> {
  const deadline = Date.now() + timeoutMs
  let lastError = ''
  while (Date.now() < deadline) {
    if (child.exitCode !== null) {
      throw new Error(`本地服务提前退出，代码 ${child.exitCode}`)
    }
    try {
      const response = await fetch(`${url}/healthz`, { signal: AbortSignal.timeout(1_000) })
      if (response.ok) {
        const payload = await response.json() as { ok?: boolean }
        if (payload.ok) return
      }
      lastError = `HTTP ${response.status}`
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error)
    }
    await new Promise(resolve => setTimeout(resolve, 150))
  }
  throw new Error(`本地服务启动超时：${lastError || '未返回健康状态'}`)
}

function waitForExit(child: ChildProcess, timeoutMs: number): Promise<boolean> {
  if (child.exitCode !== null) return Promise.resolve(true)
  return new Promise(resolve => {
    const timer = setTimeout(() => resolve(false), timeoutMs)
    child.once('exit', () => {
      clearTimeout(timer)
      resolve(true)
    })
  })
}

async function stopChild(child: ChildProcess): Promise<void> {
  if (child.exitCode !== null || !child.pid) return
  child.kill()
  if (await waitForExit(child, 5_000)) return
  if (process.platform === 'win32') {
    await new Promise<void>(resolve => {
      execFile('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true }, () => resolve())
    })
  } else {
    child.kill('SIGKILL')
  }
  await waitForExit(child, 5_000)
}

export async function startBackend(resourcesPath: string): Promise<BackendHandle> {
  const port = await reserveLoopbackPort()
  const launch = backendLaunchOptions(resourcesPath, port, process.pid)
  const child = spawn(launch.command, launch.args, {
    env: launch.env,
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  child.stdout?.on('data', chunk => console.log(`[backend] ${String(chunk).trimEnd()}`))
  child.stderr?.on('data', chunk => console.error(`[backend] ${String(chunk).trimEnd()}`))
  const url = backendUrl(port)
  try {
    await waitForHealth(child, url)
  } catch (error) {
    await stopChild(child)
    throw error
  }
  return {
    child,
    url,
    stop: () => stopChild(child),
  }
}
