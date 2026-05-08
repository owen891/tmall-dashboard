import { ElNotification } from 'element-plus'

class WebSocketClient {
  constructor() {
    this.ws = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 3
    this.reconnectDelay = 5000
    this.messageHandlers = new Map()
    this.channel = 'global'
    this.manualClose = false
    this.heartbeatTimer = null
    this.heartbeatInterval = 30000
    this.enabled = false
  }

  connect(channel = 'global') {
    if (!this.enabled) return

    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      if (this.channel === channel) return
      this.disconnect()
    }

    this.channel = channel
    this.manualClose = false
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/api/realtime/ws?channel=${channel}`

    try {
      this.ws = new WebSocket(url)

      this.ws.onopen = () => {
        console.log('WebSocket connected')
        this.reconnectAttempts = 0
        this.startHeartbeat()
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'pong') return
          this.handleMessage(data)
        } catch (e) {
          // ignore parse errors
        }
      }

      this.ws.onclose = (event) => {
        this.stopHeartbeat()
        if (!this.manualClose) {
          this.scheduleReconnect()
        }
      }

      this.ws.onerror = () => {
        // silent - don't log WebSocket errors
      }
    } catch (e) {
      if (!this.manualClose) {
        this.scheduleReconnect()
      }
    }
  }

  startHeartbeat() {
    this.stopHeartbeat()
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ping()
      }
    }, this.heartbeatInterval)
  }

  stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  scheduleReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      const delay = this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1)
      const jitter = delay * (0.5 + Math.random() * 0.5)
      setTimeout(() => this.connect(this.channel), jitter)
    } else {
      this.enabled = false
    }
  }

  handleMessage(data) {
    if (data.type === 'notification') {
      const validTypes = ['success', 'warning', 'info', 'error']
      ElNotification({
        title: data.title || '通知',
        message: data.message || '',
        type: validTypes.includes(data.level) ? data.level : 'info',
        duration: 4000,
      })
    }

    const handlers = this.messageHandlers.get(data.type)
    if (handlers) {
      handlers.forEach((handler) => handler(data))
    }
  }

  on(type, handler) {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, [])
    }
    this.messageHandlers.get(type).push(handler)
  }

  off(type, handler) {
    const handlers = this.messageHandlers.get(type)
    if (handlers) {
      const index = handlers.indexOf(handler)
      if (index > -1) {
        handlers.splice(index, 1)
      }
    }
  }

  offAll() {
    this.messageHandlers.clear()
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  ping() {
    this.send({ type: 'ping' })
  }

  disconnect() {
    this.manualClose = true
    this.stopHeartbeat()
    if (this.ws) {
      this.ws.close(1000, 'Manual disconnect')
      this.ws = null
    }
  }

  enable() {
    this.enabled = true
    this.reconnectAttempts = 0
    this.connect()
  }
}

export const wsClient = new WebSocketClient()
