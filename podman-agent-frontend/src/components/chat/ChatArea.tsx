import { useEffect, useRef, useState, useCallback } from 'react'
import { ArrowDown, Bot } from 'lucide-react'
import type { ChatMessage } from '@/lib/types'
import { MessageBubble } from './MessageBubble'

interface ChatAreaProps {
  messages: ChatMessage[]
  busy: boolean
  onConfirm?: (requestId: string, decision: 'approve' | 'reject') => void
  onRetry?: (messageId: string) => void
  onSend?: (content: string) => void
}

export function ChatArea({ messages, busy, onConfirm, onRetry, onSend }: ChatAreaProps) {
  const areaRef = useRef<HTMLDivElement>(null)
  const [hasScrolledUp, setHasScrolledUp] = useState(false)

  const scrollToBottom = useCallback(() => {
    const el = areaRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
      setHasScrolledUp(false)
    }
  }, [])

  // Track scroll position
  useEffect(() => {
    const el = areaRef.current
    if (!el) return
    const onScroll = () => {
      const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50
      setHasScrolledUp(!atBottom)
    }
    el.addEventListener('scroll', onScroll)
    return () => el.removeEventListener('scroll', onScroll)
  }, [])

  // Auto-scroll on new content
  useEffect(() => {
    if (!hasScrolledUp) scrollToBottom()
  }, [messages, hasScrolledUp, scrollToBottom])

  const showScrollBtn = hasScrolledUp && (areaRef.current?.scrollHeight ?? 0) > (areaRef.current?.clientHeight ?? 0) + 100

  return (
    <>
      <div className="messages-area" ref={areaRef}>
        {messages.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon"><Bot size={28} /></div>
            <div className="empty-title">Podman Agent</div>
            <div className="empty-desc">输入问题开始对话，或点击左侧菜单管理技能与记忆</div>
            <div className="empty-suggestions">
              <button className="suggestion-btn" onClick={() => onSend?.('帮我分析当前项目结构')}>📂 分析项目结构</button>
              <button className="suggestion-btn" onClick={() => onSend?.('帮我写一个 Python 工具脚本')}>🐍 写 Python 脚本</button>
              <button className="suggestion-btn" onClick={() => onSend?.('搜索并总结最新的 AI 新闻')}>🔍 搜索 AI 新闻</button>
            </div>
            <div className="empty-shortcuts">
              <kbd>Enter</kbd> 发送 · <kbd>⌘K</kbd> 新建对话 · <kbd>⌘.</kbd> 停止 · <kbd>/</kbd> 聚焦
            </div>
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            onConfirm={onConfirm}
            onRetry={msg.role === 'assistant' ? () => onRetry?.(msg.id) : undefined}
          />
        ))}
      </div>

      {/* Loading indicator */}
      <div className={`loading-indicator${busy ? ' visible' : ''}`}>
        <div className="loading-spinner" />
        <span>Agent 正在处理...</span>
      </div>

      {/* Scroll-to-bottom button */}
      <div className={`scroll-btn${showScrollBtn ? ' visible' : ''}`} onClick={scrollToBottom}>
        <ArrowDown size={16} />
      </div>
    </>
  )
}
