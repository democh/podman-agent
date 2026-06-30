import { useState, useEffect, useRef } from 'react'
import { ChevronRight, Check, X, Loader2 } from 'lucide-react'

interface ToolBlockProps {
  name: string
  args: Record<string, unknown> | string
  result?: string
}

export function ToolBlock({ name, args, result }: ToolBlockProps) {
  const [expanded, setExpanded] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const startRef = useRef(Date.now())
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // 执行计时器：无结果时每 100ms 更新
  useEffect(() => {
    if (!result) {
      startRef.current = Date.now()
      timerRef.current = setInterval(() => {
        setElapsed(Date.now() - startRef.current)
      }, 100)
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [result])

  // 结果到达时停止计时
  useEffect(() => {
    if (result && timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
      setElapsed(Date.now() - startRef.current)
    }
  }, [result])

  const argsStr = typeof args === 'object' ? JSON.stringify(args) : String(args)
  const argsShort = argsStr.length > 80 ? argsStr.substring(0, 80) + '…' : argsStr
  const isError = result?.startsWith('Error:')
  const isRunning = !result
  const elapsedStr = elapsed < 1000 ? `${elapsed}ms` : `${(elapsed / 1000).toFixed(1)}s`

  return (
    <div className={`tool-block${expanded ? ' expanded' : ''}${isRunning ? ' running' : ''}${isError ? ' error' : ''}`}>
      <div className="tool-header" onClick={() => setExpanded(!expanded)}>
        <span className="tool-status-icon">
          {isRunning ? (
            <Loader2 size={14} className="tool-spinner" />
          ) : isError ? (
            <X size={14} className="tool-icon-error" />
          ) : (
            <Check size={14} className="tool-icon-success" />
          )}
        </span>
        <span className="tool-name">{name}</span>
        <span className="tool-args">{argsShort}</span>
        <span className="tool-elapsed">{elapsedStr}</span>
        <span className="tool-chevron">
          <ChevronRight size={12} />
        </span>
      </div>
      {expanded && (
        <div className="tool-body">
          <div className="tool-args-full">
            <pre>{typeof args === 'object' ? JSON.stringify(args, null, 2) : String(args)}</pre>
          </div>
          {result && (
            <div className={isError ? 'tool-result-err' : 'tool-result-ok'}>
              <pre>{result}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
