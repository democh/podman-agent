import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { ChevronDown, ChevronRight, Brain } from 'lucide-react'
import type {
  ChatMessage,
  ServerEvent,
  ContentDeltaEvent,
  ToolCallEvent,
  ToolResultEvent,
  PlanCreatedEvent,
  ReflectionEvent,
  LatsPickEvent,
  FileReadyEvent,
  WarningEvent,
  ContextCompressedEvent,
  ErrorEvent,
  UsageEvent,
  ConfirmationRequestEvent,
} from '@/lib/types'
import { ToolBlock } from './ToolBlock'
import { PlanBlock } from './PlanBlock'
import type { PlanStepStatus } from './PlanBlock'
import { SearchCard } from './SearchCard'
import { FileCard } from './FileCard'
import { ConfirmationCard } from './ConfirmationCard'
import { MessageActions } from './MessageActions'
import { ReflectionMeta, LatsMeta, MetaLine } from './MetaBadges'
import { MarkdownContent } from './MarkdownContent'

interface MessageBubbleProps {
  message: ChatMessage
  onConfirm?: (requestId: string, decision: 'approve' | 'reject') => void
  onRetry?: () => void
}

/* ── Type Guards ── */

function isContentDelta(ev: ServerEvent): ev is ContentDeltaEvent {
  return ev.type === 'content_delta'
}

function isToolCall(ev: ServerEvent): ev is ToolCallEvent {
  return ev.type === 'tool_call'
}

function isToolResult(ev: ServerEvent): ev is ToolResultEvent {
  return ev.type === 'tool_result'
}

function isPlanCreated(ev: ServerEvent): ev is PlanCreatedEvent {
  return ev.type === 'plan_created'
}

function isReflection(ev: ServerEvent): ev is ReflectionEvent {
  return ev.type === 'reflection'
}

function isLatsPick(ev: ServerEvent): ev is LatsPickEvent {
  return ev.type === 'lats_pick'
}

function isFileReady(ev: ServerEvent): ev is FileReadyEvent {
  return ev.type === 'file_ready'
}

function isWarning(ev: ServerEvent): ev is WarningEvent {
  return ev.type === 'warning'
}

function isContextCompressed(ev: ServerEvent): ev is ContextCompressedEvent {
  return ev.type === 'context_compressed'
}

function isError(ev: ServerEvent): ev is ErrorEvent {
  return ev.type === 'error'
}

function isUsage(ev: ServerEvent): ev is UsageEvent {
  return ev.type === 'usage'
}

function isConfirmationRequest(ev: ServerEvent): ev is ConfirmationRequestEvent {
  return ev.type === 'confirmation_request'
}

/* ── Plan Status Computation ── */

/**
 * 纯函数：从事件序列中推导所有计划步骤状态。
 * 为每个 plan_created 事件计算截至该点的最终状态。
 */
function computePlanStatuses(events: ServerEvent[]): Map<number, { statuses: PlanStepStatus[] }> {
  const result = new Map<number, { statuses: PlanStepStatus[] }>()

  for (let i = 0; i < events.length; i++) {
    if (!isPlanCreated(events[i])) continue

    const steps = (events[i] as PlanCreatedEvent).steps
    const statuses: PlanStepStatus[] = steps.map((_, j) => j === 0 ? 'active' : 'pending')
    let currentStep = 0

    for (let j = i + 1; j < events.length; j++) {
      const ev = events[j]
      if (isPlanCreated(ev)) break
      if (isReflection(ev)) {
        if (ev.result === 'DONE') {
          if (currentStep < statuses.length) {
            statuses[currentStep] = 'done'
            if (currentStep + 1 < statuses.length) {
              currentStep++
              statuses[currentStep] = 'active'
            }
          }
        } else if (ev.result === 'REPLAN') {
          if (currentStep < statuses.length) {
            statuses[currentStep] = 'replan'
          }
        }
      }
    }

    result.set(i, { statuses: [...statuses] })
  }

  return result
}

/* ── Element Builder ── */

/**
 * 从消息事件序列构建有序的 React 元素列表。
 * 内容段与工具/计划/元数据块按到达顺序交替渲染。
 *
 * 使用 O(n) 单遍扫描，通过 segStart 变量追踪内容段起点，
 * 避免了之前 getLastFlushPoint 的 O(n²) 回溯。
 */
function buildOrderedElements(message: ChatMessage, onConfirm?: (requestId: string, decision: 'approve' | 'reject') => void): ReactNode[] {
  const { content, events, streaming } = message
  const elements: ReactNode[] = []
  let contentOffset = 0
  let segStart = 0  // 当前内容段在 content 中的起始位置
  let pendingSearchIdx = -1
  // 工具名 → 未匹配元素索引队列（支持 ReWOO 并行模式下多个同名工具同时执行）
  const pendingToolCalls = new Map<string, number[]>()

  const planStatusMap = computePlanStatuses(events)

  for (let i = 0; i < events.length; i++) {
    const ev = events[i]

    if (isContentDelta(ev)) {
      contentOffset += ev.content.length
      continue
    }

    // 遇到非 content 事件时：先 flush 当前累积的内容段
    if (contentOffset > segStart) {
      const segText = content.substring(segStart, contentOffset)
      if (segText) {
        elements.push(<MarkdownContent key={`c-${i}`} text={segText} />)
      }
      segStart = contentOffset
    }

    if (isToolCall(ev)) {
      const argsStr = typeof ev.args === 'object' ? (ev.args as Record<string, unknown>).command || '' : String(ev.args)
      const isSearch = (ev.name === 'run_shell' && String(argsStr).includes('search.py')) || ev.name === 'web_search'
      const elIdx = elements.length
      if (isSearch) pendingSearchIdx = elIdx
      // 按工具名排队，支持同名工具并行执行
      const queue = pendingToolCalls.get(ev.name)
      if (queue) queue.push(elIdx)
      else pendingToolCalls.set(ev.name, [elIdx])
      elements.push(<ToolBlock key={`tc-${i}`} name={ev.name} args={ev.args} result={undefined} />)
    } else if (isToolResult(ev)) {
      // 从同名工具队列中取出最早的未匹配索引（FIFO）
      const evName = ev.name ?? ''
      const queue = pendingToolCalls.get(evName)
      const matchIdx = queue?.length ? queue.shift()! : -1
      if (matchIdx >= 0) {
        if (pendingSearchIdx === matchIdx && !ev.result?.startsWith('Error:')) {
          elements.push(<SearchCard key={`sc-${i}`} resultText={ev.result} />)
          pendingSearchIdx = -1
        }
        const origEl = elements[matchIdx]
        const origName = (origEl as React.ReactElement<{ name: string }>)?.props?.name || evName
        const origArgs = (origEl as React.ReactElement<{ args: Record<string, unknown> | string }>)?.props?.args || ''
        elements[matchIdx] = <ToolBlock key={`tc-${matchIdx}`} name={origName} args={origArgs} result={ev.result} />
      }
    } else if (isPlanCreated(ev)) {
      const info = planStatusMap.get(i)
      elements.push(<PlanBlock key={`plan-${i}`} steps={ev.steps} stepStatuses={info?.statuses} />)
    } else if (isReflection(ev)) {
      elements.push(<ReflectionMeta key={`ref-${i}`} result={ev.result} detail={ev.detail} />)
    } else if (isLatsPick(ev)) {
      elements.push(<LatsMeta key={`lats-${i}`} pick={ev.pick} total={ev.total} chosen={ev.chosen} />)
    } else if (isFileReady(ev)) {
      elements.push(<FileCard key={`file-${i}`} filename={ev.filename} path={ev.path} size={ev.size} description={ev.description} />)
    } else if (isWarning(ev)) {
      elements.push(<MetaLine key={`warn-${i}`} text={'⚠ ' + ev.content} cls="warn" />)
    } else if (isContextCompressed(ev)) {
      const before = ev.before_messages ?? '?'
      const after = ev.after_messages ?? ev.kept ?? '?'
      const saved = ev.saved_tokens ?? 0
      const mode = ev.has_summary ? '摘要' : '截断'
      const detail = saved > 0
        ? `[上下文已压缩: ${before}→${after}条, 节省~${saved.toLocaleString()} tokens (${mode})]`
        : `[上下文已压缩: ${before}→${after}条消息 (${mode})]`
      elements.push(<MetaLine key={`cc-${i}`} text={detail} cls="warn" />)
    } else if (isError(ev)) {
      elements.push(<MetaLine key={`err-${i}`} text={'✗ ' + ev.content} cls="error" />)
    } else if (isUsage(ev)) {
      elements.push(<MetaLine key={`usage-${i}`} text={`tokens: prompt=${ev.prompt_tokens} completion=${ev.completion_tokens} total=${ev.total_tokens}`} />)
    } else if (isConfirmationRequest(ev)) {
      elements.push(
        <ConfirmationCard
          key={`confirm-${i}`}
          toolName={ev.tool_name}
          args={ev.args}
          reason={ev.reason}
          requestId={ev.request_id}
          onDecision={onConfirm || (() => {})}
        />
      )
    }
  }

  // Flush remaining content
  const remaining = content.substring(contentOffset)
  if (remaining || (contentOffset === 0 && content)) {
    const text = remaining || content
    if (text) {
      elements.push(<MarkdownContent key="final" text={text} streaming={streaming} />)
    }
  }

  return elements
}

/* ── ReasoningBlock: 可折叠推理过程 ── */

function ReasoningBlock({ reasoning }: { reasoning: string }) {
  const [expanded, setExpanded] = useState(false)
  const preview = reasoning.length > 100 ? reasoning.substring(0, 100) + '…' : reasoning

  return (
    <div className={`reasoning-block${expanded ? ' expanded' : ''}`}>
      <div className="reasoning-header" onClick={() => setExpanded(!expanded)}>
        <Brain size={14} />
        <span className="reasoning-label">推理过程</span>
        <span className="reasoning-toggle">
          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </span>
      </div>
      {expanded ? (
        <div className="reasoning-content">{reasoning}</div>
      ) : (
        <div className="reasoning-preview">{preview}</div>
      )}
    </div>
  )
}

/* ── Component ── */

export function MessageBubble({ message, onConfirm, onRetry }: MessageBubbleProps) {
  const { role, reasoning, events, content, streaming, files } = message
  const isUser = role === 'user'

  // useMemo: 仅在事件数量、内容或流式状态变化时重新构建元素
  const elements = useMemo(
    () => buildOrderedElements(message, onConfirm),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [events.length, content, streaming, onConfirm]
  )

  return (
    <div className={`msg ${isUser ? 'user' : 'agent'}`}>
      <div className="msg-label">{isUser ? '你' : 'Agent'}</div>
      <div className="msg-bubble">
        {/* 用户上传的文件列表 */}
        {isUser && files && files.length > 0 && (
          <div className="msg-files">
            {files.map((file, i) => (
              <span key={i} className="msg-file-tag">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/></svg>
                {file.filename}
              </span>
            ))}
          </div>
        )}

        {reasoning && (
          <ReasoningBlock reasoning={reasoning} />
        )}

        {elements}

        {!isUser && !content && events.length === 0 && (
          <div className="typing">
            <span /><span /><span />
          </div>
        )}

        {/* 消息操作栏：hover 时显示 */}
        {!streaming && content && (
          <MessageActions content={content} role={role} onRetry={!isUser ? onRetry : undefined} />
        )}
      </div>
    </div>
  )
}
