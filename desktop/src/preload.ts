import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('tmallDesktop', {
  isDesktop: true,
  getVersion: () => ipcRenderer.invoke('desktop:get-version'),
  checkForUpdates: () => ipcRenderer.invoke('desktop:check-for-updates'),
  selectScanFolder: () => ipcRenderer.invoke('desktop:select-scan-folder'),
  onUpdateStatus: (listener: (status: unknown) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, status: unknown) => listener(status)
    ipcRenderer.on('desktop:update-status', handler)
    return () => ipcRenderer.removeListener('desktop:update-status', handler)
  },
})
