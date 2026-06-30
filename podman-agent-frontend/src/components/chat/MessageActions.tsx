import { useState, useCallback } from 'react'
import { Copy, Check, RotateCcw } from 'lucide-react'

interface MessageActionsProps {
  content: string
  role: 'user' | 'assistant'
  onRetry?: () => void
}

/**
 * 消息操作栏：hover 时显示于消息气泡底部。
 * - 复制：将消息文本拷贝到剪贴板
 * - 重试：仅 assistant 消息显示，触发重新生成
 */
export function MessageActions({ content, role, onRetry }: MessageActionsProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // fallback for insecure contexts
      const ta = document.createElement('textarea')
      ta.value = content
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }, [content])

  return (
    <div className="message-actions">
      <button
        className="action-btn"
        onClick={handleCopy}
        title={copied ? '已复制' : '复制'}
      >
        {copied ? <Check size={14} /> : <Copy size={14} />}
      </button>
      {role === 'assistant' && onRetry && (
        <button
          className="action-btn"
          onClick={onRetry}
          title="重新生成"
        >
          <RotateCcw size={14} />
        </button>
      )}
    </div>
  )
}
