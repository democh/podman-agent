/* ═══ WebSocket 事件类型（与后端 agent.py 完全对齐）═══ */

// 客户端 -> 服务端
export type ClientMessage =
  | { type: 'message'; content: string; files?: UploadedFileInfo[] }
  | { type: 'stop' }
  | { type: 'reset' }
  | { type: 'compress' }
  | { type: 'info' }
  | { type: 'skill_list' }
  | { type: 'skill_enable'; name: string }
  | { type: 'skill_disable'; name: string }
  | { type: 'memory_list' }
  | { type: 'conversation_recent'; days?: number }
  | { type: 'confirm'; request_id: string; decision: 'approve' | 'reject' }

// 上传文件信息（随消息发送）
export interface UploadedFileInfo {
  filename: string
  path: string
  size: number
  type: string
  markdown: string
}

// 服务端 -> 客户端
export type ServerEvent =
  | InfoEvent
  | ReasoningDeltaEvent
  | ContentDeltaEvent
  | StreamEndEvent
  | ReasoningEvent
  | UsageEvent
  | WarningEvent
  | TokenWarningEvent
  | ToolCallEvent
  | ToolResultEvent
  | SeparatorEvent
  | ContextCompressedEvent
  | CompressResultEvent
  | PlanCreatedEvent
  | ReflectionEvent
  | LatsPickEvent
  | DoneEvent
  | ErrorEvent
  | FileReadyEvent
  | ResetOkEvent
  | SkillListEvent
  | SkillUpdatedEvent
  | MemoryListResultEvent
  | ConversationHistoryEvent
  | ConfirmationRequestEvent

export interface InfoEvent {
  type: 'info'
  model?: string
  workspace?: string
  stream?: boolean
  enable_thinking?: boolean
  tools?: string[]
  skills?: SkillSummary[]
  total_tokens?: number
}

export interface ReasoningDeltaEvent {
  type: 'reasoning_delta'
  content: string
}

export interface ContentDeltaEvent {
  type: 'content_delta'
  content: string
}

export interface StreamEndEvent {
  type: 'stream_end'
}

export interface ReasoningEvent {
  type: 'reasoning'
  content: string
}

export interface UsageEvent {
  type: 'usage'
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

export interface WarningEvent {
  type: 'warning'
  content: string
}

export interface ToolCallEvent {
  type: 'tool_call'
  name: string
  args: Record<string, unknown> | string
}

export interface ToolResultEvent {
  type: 'tool_result'
  name?: string
  result: string
  preview?: string
}

export interface SeparatorEvent {
  type: 'separator'
}

export interface ContextCompressedEvent {
  type: 'context_compressed'
  compressed: boolean
  before_messages?: number
  after_messages?: number
  before_tokens?: number
  after_tokens?: number
  saved_tokens?: number
  has_summary?: boolean
  kept?: number
}

export interface TokenWarningEvent {
  type: 'token_warning'
  total_tokens: number
  threshold: number
  usage_pct: number
  message: string
}

export interface CompressResultEvent {
  type: 'compress_result'
  compressed: boolean
  reason?: string
  before_messages?: number
  after_messages?: number
  before_tokens?: number
  after_tokens?: number
  saved_tokens?: number
  has_summary?: boolean
}

export interface PlanCreatedEvent {
  type: 'plan_created'
  steps: string[]
}

export interface ReflectionEvent {
  type: 'reflection'
  result: 'DONE' | 'RETRY' | 'REPLAN'
  detail?: string
}

export interface LatsPickEvent {
  type: 'lats_pick'
  pick: number
  total: number
  chosen?: string
}

export interface DoneEvent {
  type: 'done'
  content?: string
}

export interface ErrorEvent {
  type: 'error'
  content: string
}

export interface FileReadyEvent {
  type: 'file_ready'
  path: string
  filename: string
  size: number
  description?: string
}

export interface ResetOkEvent {
  type: 'reset_ok'
}

export interface SkillListEvent {
  type: 'skill_list'
  skills: SkillSummary[]
}

export interface SkillUpdatedEvent {
  type: 'skill_updated'
  result: string
}

export interface MemoryListResultEvent {
  type: 'memory_list_result'
  result: string
}

export interface ConversationHistoryEvent {
  type: 'conversation_history'
  result: string
}

export interface ConfirmationRequestEvent {
  type: 'confirmation_request'
  tool_name: string
  args: Record<string, unknown>
  reason: string
  request_id: string
}

// 通用类型
export interface SkillSummary {
  name: string
  description: string
  enabled: boolean
  triggers?: string[]
}

// 前端消息模型
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  reasoning?: string
  events: ServerEvent[]
  timestamp: number
  streaming?: boolean
  files?: UploadedFileInfo[]
}

// 连接状态
export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

// ── Settings 配置类型 ──
export interface SettingsData {
  llm: {
    base_url: string
    model: string
    max_iterations: number
    temperature: number
    top_p: number | null
    max_tokens: number | null
    stream: boolean
    enable_thinking: boolean
  }
  agent: {
    context_token_threshold: number
    keep_recent: number
    loop_window: number
    guardrails_interval: number
  }
  planning: {
    enable_planning: boolean
    enable_reflection: boolean
    max_retries_per_step: number
  }
  lats: {
    enable_lats: boolean
    lats_candidates: number
  }
  security: {
    allow_shell: boolean
    shell_blacklist: string
  }
  hitl: {
    hitl_mode: string
    hitl_tools: string
  }
  evolution: {
    enable_evolution: boolean
    evolution_reflect_min_tools: number
    evolution_analysis_interval: number
  }
}
