import { useCallback, useEffect, useReducer, useRef } from 'react'
import { useWebSocket } from './useWebSocket'
import type {
  ChatMessage,
  ClientMessage,
  ServerEvent,
  SkillSummary,
  UploadedFileInfo,
} from '@/lib/types'

interface AgentState {
  messages: ChatMessage[]
  currentMsgId: string | null
  busy: boolean
  model: string
  tools: string[]
  skills: SkillSummary[]
  totalTokens: number
  memoryResult: string | null
  historyLoaded: boolean
  tokenWarning: { usage_pct: number; message: string } | null
}

type AgentAction =
  | { type: 'EVENT'; event: ServerEvent }
  | { type: 'SEND'; userMsg: ChatMessage }
  | { type: 'RESET' }
  | { type: 'HISTORY'; messages: ChatMessage[] }

let msgCounter = 0
function nextId() {
  return `msg-${Date.now()}-${++msgCounter}`
}

function ensureAssistant(state: AgentState): { messages: ChatMessage[]; idx: number } {
  const messages = [...state.messages]
  let idx = state.currentMsgId ? messages.findIndex((m) => m.id === state.currentMsgId) : -1
  if (idx < 0) {
    const newMsg: ChatMessage = {
      id: nextId(),
      role: 'assistant',
      content: '',
      events: [],
      timestamp: Date.now(),
    }
    messages.push(newMsg)
    idx = messages.length - 1
  }
  return { messages, idx }
}

function reducer(state: AgentState, action: AgentAction): AgentState {
  if (action.type === 'RESET') {
    return { ...initialState, model: state.model, tools: state.tools, skills: state.skills }
  }
  if (action.type === 'HISTORY') {
    if (state.historyLoaded) return state
    return { ...state, messages: [...action.messages, ...state.messages], historyLoaded: true }
  }
  if (action.type === 'SEND') {
    const userMsg = action.userMsg
    return {
      ...state,
      messages: [...state.messages, userMsg],
      currentMsgId: null,
      busy: true,
    }
  }
  const ev = action.event
  switch (ev.type) {
    case 'info':
      // info 事件不应覆盖 busy 状态（可能在 Agent 运行期间收到 stop 响应）
      return { ...state, model: ev.model ?? state.model, tools: ev.tools ?? state.tools, skills: ev.skills ?? state.skills, totalTokens: ev.total_tokens ?? state.totalTokens }
    case 'content_delta': {
      const { messages, idx } = ensureAssistant(state)
      messages[idx] = {
        ...messages[idx],
        content: messages[idx].content + ev.content,
        events: [...messages[idx].events, ev],
        streaming: true,
      }
      return { ...state, messages, currentMsgId: messages[idx].id }
    }
    case 'reasoning_delta':
    case 'reasoning': {
      const { messages, idx } = ensureAssistant(state)
      messages[idx] = { ...messages[idx], reasoning: (messages[idx].reasoning ?? '') + ev.content }
      return { ...state, messages, currentMsgId: messages[idx].id }
    }
    case 'tool_call': case 'tool_result': case 'plan_created': case 'reflection':
    case 'lats_pick': case 'warning': case 'context_compressed': case 'file_ready':
    case 'usage': case 'confirmation_request': {
      const { messages, idx } = ensureAssistant(state)
      messages[idx] = { ...messages[idx], events: [...messages[idx].events, ev] }
      return { ...state, messages, currentMsgId: messages[idx].id }
    }
    case 'token_warning':
      return { ...state, tokenWarning: { usage_pct: ev.usage_pct, message: ev.message } }
    case 'compress_result': {
      // 压缩结果：更新 token 数并清除警告
      const newTokens = ev.after_tokens ?? state.totalTokens
      return {
        ...state,
        totalTokens: newTokens > 0 ? newTokens : state.totalTokens,
        tokenWarning: ev.compressed ? null : state.tokenWarning,
      }
    }
    case 'stream_end': case 'separator':
      return state  // 不存储，不触发重渲染
    case 'done': {
      // Mark the last assistant message as no longer streaming
      const msgs = state.messages.map(m =>
        m.role === 'assistant' && m.streaming ? { ...m, streaming: false } : m
      )
      return { ...state, messages: msgs, busy: false, currentMsgId: null }
    }
    case 'error': {
      const { messages, idx } = ensureAssistant(state)
      messages[idx] = { ...messages[idx], events: [...messages[idx].events, ev], streaming: false }
      return { ...state, messages, busy: false, currentMsgId: null }
    }
    case 'reset_ok': return { ...state, messages: [], currentMsgId: null, busy: false }
    case 'skill_list': return { ...state, skills: ev.skills }
    case 'skill_updated': return state
    case 'memory_list_result': return { ...state, memoryResult: ev.result }
    case 'conversation_history': return state
    default: return state
  }
}

const initialState: AgentState = {
  messages: [], currentMsgId: null, busy: false, model: '', tools: [], skills: [], totalTokens: 0, memoryResult: null, historyLoaded: false, tokenWarning: null,
}

function parseHistory(text: string): ChatMessage[] {
  if (!text || text.includes('(无对话历史)')) return []
  const msgs: ChatMessage[] = []
  text = text.replace(/\r\n/g, '\n')
  const dayBlocks = text.split(/^---\n(?=title:|date:)/m).filter((s) => s.trim())
  for (const block of dayBlocks) {
    const lines = block.split('\n')
    let bodyStart = 0
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].startsWith('---') && i > 0) { bodyStart = i + 1; break }
      if (lines[i].startsWith('## ')) { bodyStart = i; break }
    }
    const body = lines.slice(bodyStart).join('\n')
    const turns = body.split(/^## (\d{2}:\d{2}:\d{2})/m)
    for (let i = 1; i < turns.length; i += 2) {
      const content = turns[i + 1] || ''
      const userMatch = content.match(/\*\*用户:\*\*\n\n([\s\S]*?)(?=\*\*工具调用|\*\*助手|$)/)
      if (userMatch) {
        msgs.push({ id: nextId(), role: 'user', content: userMatch[1].trim(), events: [], timestamp: Date.now() })
      }
      const agentRe = new RegExp('\\*\\*助手:\\*\\*\\n\\n([\\s\\S]*?)(?=\\n\\n---\\n\\n## \\d{2}:\\d{2}:\\d{2}|\\n\\n---\\n\\s*$)', 'g')
      for (const am of [...content.matchAll(agentRe)]) {
        let agentText = am[1].trim()
          .replace(/<!--file path="[^"]*" desc="[^"]*"-->/g, '').trim()
          .replace(/<!--search\s+[A-Za-z0-9+/=]+-->/g, '').trim()
        if (agentText) {
          msgs.push({ id: nextId(), role: 'assistant', content: agentText, events: [], timestamp: Date.now() })
        }
      }
    }
  }
  return msgs
}

export function useAgent() {
  const [state, dispatch] = useReducer(reducer, initialState)
  const sendRef = useRef<((msg: ClientMessage) => void) | null>(null)

  const handleEvent = useCallback((event: ServerEvent) => {
    dispatch({ type: 'EVENT', event })
    if (event.type === 'conversation_history') {
      const historyMsgs = parseHistory(event.result || '')
      if (historyMsgs.length > 0) dispatch({ type: 'HISTORY', messages: historyMsgs })
    }
    if (event.type === 'skill_updated') {
      sendRef.current?.({ type: 'skill_list' })
    }
  }, [])

  const wsUrl = import.meta.env.VITE_WS_URL || `ws://${window.location.hostname}:8000/ws/chat`
  const ws = useWebSocket({ url: wsUrl, onEvent: handleEvent })
  sendRef.current = ws.send

  // 每次连接成功时请求对话历史（处理 StrictMode 重挂载和断线重连）
  const historyRequested = useRef(false)
  useEffect(() => {
    if (ws.status === 'connected' && !historyRequested.current) {
      historyRequested.current = true
      const timer = setTimeout(() => {
        ws.send({ type: 'conversation_recent', days: 2 })
      }, 200)
      return () => {
        clearTimeout(timer)
        historyRequested.current = false
      }
    }
  }, [ws.status, ws])

  const send = useCallback((content: string, files?: UploadedFileInfo[]) => {
    if (!content.trim() || state.busy) return
    const userMsg: ChatMessage = {
      id: nextId(),
      role: 'user',
      content: content.trim(),
      events: [],
      timestamp: Date.now(),
      files: files && files.length > 0 ? files : undefined,
    }
    dispatch({ type: 'SEND', userMsg })
    ws.send({ type: 'message', content: content.trim(), files })
  }, [state.busy, ws])

  const stop = useCallback(() => ws.send({ type: 'stop' }), [ws])
  const reset = useCallback(() => ws.send({ type: 'reset' }), [ws])
  const compress = useCallback(() => ws.send({ type: 'compress' }), [ws])
  const refreshMemory = useCallback(() => ws.send({ type: 'memory_list' }), [ws])
  const toggleSkill = useCallback((name: string, enabled: boolean) =>
    ws.send({ type: enabled ? 'skill_enable' : 'skill_disable', name }), [ws])
  const confirm = useCallback((requestId: string, decision: 'approve' | 'reject') =>
    ws.send({ type: 'confirm', request_id: requestId, decision }), [ws])

  const retry = useCallback((messageId: string) => {
    // 找到该消息前的最后一条用户消息，重新发送
    const idx = state.messages.findIndex((m) => m.id === messageId)
    if (idx < 0 || state.busy) return
    // 向前查找对应的用户消息
    for (let i = idx - 1; i >= 0; i--) {
      if (state.messages[i].role === 'user') {
        const content = state.messages[i].content
        ws.send({ type: 'message', content })
        const userMsg: ChatMessage = { id: nextId(), role: 'user', content, events: [], timestamp: Date.now() }
        dispatch({ type: 'SEND', userMsg })
        return
      }
    }
  }, [state.messages, state.busy, ws])

  return { messages: state.messages, busy: state.busy, model: state.model, tools: state.tools, skills: state.skills, totalTokens: state.totalTokens, memoryResult: state.memoryResult, tokenWarning: state.tokenWarning, status: ws.status, send, stop, reset, compress, refreshMemory, toggleSkill, confirm, retry }
}
