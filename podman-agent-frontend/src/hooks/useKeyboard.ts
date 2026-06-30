import { useEffect } from 'react'

interface KeyboardShortcuts {
  onNewChat?: () => void
  onStopAgent?: () => void
  onFocusInput?: () => void
}

/**
 * 全局快捷键系统：
 * - Ctrl/Cmd + K: 新建对话 (reset)
 * - Ctrl/Cmd + .: 停止 Agent
 * - /: 聚焦输入框
 */
export function useKeyboard({ onNewChat, onStopAgent, onFocusInput }: KeyboardShortcuts) {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const isMod = e.metaKey || e.ctrlKey
      const target = e.target as HTMLElement
      const isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable

      // Ctrl/Cmd + K: 新建对话
      if (isMod && e.key === 'k') {
        e.preventDefault()
        onNewChat?.()
        return
      }

      // Ctrl/Cmd + .: 停止
      if (isMod && e.key === '.') {
        e.preventDefault()
        onStopAgent?.()
        return
      }

      // / : 聚焦输入框（仅在非输入状态时）
      if (e.key === '/' && !isInput && !isMod) {
        e.preventDefault()
        onFocusInput?.()
        return
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onNewChat, onStopAgent, onFocusInput])
}
