import { useCallback, useRef, useEffect, useState } from 'react'
import type { ClientMessage, ConnectionStatus, ServerEvent } from '@/lib/types'

interface UseWebSocketOptions {
  url: string
  onEvent: (event: ServerEvent) => void
  reconnectDelay?: number
  maxReconnectAttempts?: number
}

export function useWebSocket({
  url,
  onEvent,
  reconnectDelay = 2000,
  maxReconnectAttempts = 10,
}: UseWebSocketOptions) {
  const [status, setStatus] = useState<ConnectionStatus>('connecting')
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectCount = useRef(0)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  // 连接 ID：防止 StrictMode 下旧连接的 onclose 干扰新连接
  const connId = useRef(0)

  const connect = useCallback(() => {
    // 如果当前连接仍然打开或正在连接中，不重复连接
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) {
      return
    }

    connId.current++
    const myId = connId.current

    setStatus('connecting')
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (myId !== connId.current) return
      setStatus('connected')
      reconnectCount.current = 0
    }

    ws.onmessage = (e) => {
      if (myId !== connId.current) return
      try {
        const event = JSON.parse(e.data) as ServerEvent
        // 心跳响应：自动回复 pong
        if ((event as { type: string }).type === 'ping') {
          send({ type: 'pong' } as unknown as ClientMessage)
          return
        }
        onEventRef.current(event)
      } catch (err) {
        console.error('[WebSocket] parse error:', err)
      }
    }

    ws.onclose = () => {
      if (myId !== connId.current) return
      setStatus('disconnected')
      wsRef.current = null
      scheduleReconnect()
    }

    ws.onerror = () => {
      if (myId !== connId.current) return
      setStatus('error')
    }
  }, [url])

  const scheduleReconnect = useCallback(() => {
    if (reconnectCount.current >= maxReconnectAttempts) return
    const delay = Math.min(
      reconnectDelay * Math.pow(1.5, reconnectCount.current),
      30000,
    )
    reconnectCount.current++
    reconnectTimer.current = setTimeout(connect, delay)
  }, [connect, reconnectDelay, maxReconnectAttempts])

  const send = useCallback((msg: ClientMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg))
    }
  }, [])

  const disconnect = useCallback(() => {
    clearTimeout(reconnectTimer.current)
    reconnectCount.current = maxReconnectAttempts
    connId.current++
    wsRef.current?.close()
    wsRef.current = null
  }, [maxReconnectAttempts])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      connId.current++
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [connect])

  return { status, send, connect, disconnect }
}
