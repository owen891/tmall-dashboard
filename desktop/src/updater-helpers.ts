import { join } from 'node:path'

interface ErrorWithCode {
  code?: unknown
  message?: unknown
}

export function isWindowsLockError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false
  const candidate = error as ErrorWithCode
  const code = typeof candidate.code === 'string' ? candidate.code.toUpperCase() : ''
  if (['EBUSY', 'EPERM', 'EACCES'].includes(code)) return true
  const message = typeof candidate.message === 'string' ? candidate.message.toLowerCase() : ''
  return message.includes('resource busy') || message.includes('file is being used') || message.includes('access is denied')
}

export function pendingUpdateDirectories(environment: NodeJS.ProcessEnv = process.env): string[] {
  const directories: string[] = []
  if (environment.LOCALAPPDATA) {
    directories.push(join(environment.LOCALAPPDATA, 'TmallDashboard-updater', 'pending'))
  }
  if (environment.APPDATA) {
    directories.push(join(environment.APPDATA, 'TmallDashboard', 'updater', 'pending'))
  }
  return directories
}
