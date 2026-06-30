import { useState, useEffect, useRef, useCallback } from 'react'
import { X, Save, RotateCcw, Loader2, ChevronDown, Check } from 'lucide-react'
import type { SettingsData } from '@/lib/types'

const API_BASE = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`

interface SettingsPanelProps {
  open: boolean
  onClose: () => void
}

// 配置字段定义：环境变量名 -> 显示信息
interface FieldDef {
  envKey: string
  label: string
  type: 'text' | 'number' | 'toggle' | 'select' | 'multiselect'
  step?: number
  min?: number
  max?: number
  options?: { value: string; label: string }[]
  hint?: string
  /** 动态获取选项列表（优先级高于 options） */
  getOptions?: () => { value: string; label: string }[]
}

interface SectionDef {
  key: keyof SettingsData
  title: string
  fields: FieldDef[]
}

const SECTIONS: SectionDef[] = [
  {
    key: 'llm', title: 'LLM 连接',
    fields: [
      { envKey: 'LLM_MODEL', label: '模型', type: 'text' },
      { envKey: 'LLM_BASE_URL', label: 'API 地址', type: 'text' },
      { envKey: 'MAX_ITERATIONS', label: '最大迭代步数', type: 'number', min: 1, max: 100, step: 1 },
      { envKey: 'TEMPERATURE', label: '温度', type: 'number', min: 0, max: 2, step: 0.1 },
      { envKey: 'TOP_P', label: 'Top-P 采样', type: 'number', min: 0, max: 1, step: 0.05, hint: '留空=不传' },
      { envKey: 'MAX_TOKENS', label: '最大 Token 数', type: 'number', min: 0, step: 256, hint: '留空=模型端控制' },
      { envKey: 'STREAM', label: '流式输出', type: 'toggle' },
      { envKey: 'ENABLE_THINKING', label: '思考模式', type: 'toggle', hint: '仅 DeepSeek R1 等模型' },
    ],
  },
  {
    key: 'agent', title: 'Agent 行为',
    fields: [
      { envKey: 'CONTEXT_TOKEN_THRESHOLD', label: '上下文 Token 阈值', type: 'number', min: 1000, step: 10000 },
      { envKey: 'KEEP_RECENT', label: '保留最近消息数', type: 'number', min: 1, max: 100, step: 1 },
      { envKey: 'LOOP_WINDOW', label: '循环检测窗口', type: 'number', min: 1, max: 20, step: 1 },
      { envKey: 'GUARDRAILS_INTERVAL', label: '护栏注入间隔', type: 'number', min: 1, max: 50, step: 1 },
    ],
  },
  {
    key: 'planning', title: 'Plan-Execute-Reflect',
    fields: [
      { envKey: 'ENABLE_PLANNING', label: '启用任务规划', type: 'toggle' },
      { envKey: 'ENABLE_REFLECTION', label: '启用步骤反思', type: 'toggle' },
      { envKey: 'MAX_RETRIES_PER_STEP', label: '每步最大重试', type: 'number', min: 0, max: 10, step: 1 },
    ],
  },
  {
    key: 'lats', title: 'LATS 候选搜索',
    fields: [
      { envKey: 'ENABLE_LATS', label: '启用 LATS', type: 'toggle', hint: '增加 2× LLM 调用' },
      { envKey: 'LATS_CANDIDATES', label: '候选方案数', type: 'number', min: 2, max: 10, step: 1 },
    ],
  },
  {
    key: 'security', title: '安全策略',
    fields: [
      { envKey: 'ALLOW_SHELL', label: '允许 Shell 命令', type: 'toggle' },
      { envKey: 'SHELL_BLACKLIST', label: 'Shell 黑名单', type: 'text', hint: '逗号分隔' },
    ],
  },
  {
    key: 'hitl', title: 'Human-in-the-Loop',
    fields: [
      { envKey: 'HITL_MODE', label: '确认模式', type: 'select', options: [
        { value: 'all', label: '全部确认' },
        { value: 'risky', label: '仅高危确认' },
        { value: 'none', label: '直接放行' },
      ]},
      { envKey: 'HITL_TOOLS', label: '需确认工具', type: 'multiselect', hint: '仅 risky 模式生效' },
    ],
  },
  {
    key: 'evolution', title: '自进化系统',
    fields: [
      { envKey: 'ENABLE_EVOLUTION', label: '启用自进化', type: 'toggle' },
      { envKey: 'EVOLUTION_REFLECT_MIN_TOOLS', label: '反思最小工具数', type: 'number', min: 1, max: 20, step: 1 },
      { envKey: 'EVOLUTION_ANALYSIS_INTERVAL', label: '深度分析间隔(h)', type: 'number', min: 1, max: 168, step: 1 },
    ],
  },
]

// 精确映射
function getFlatValue(data: SettingsData, envKey: string): string | number | boolean | null {
  const mapping: Record<string, [keyof SettingsData, string]> = {
    LLM_MODEL: ['llm', 'model'],
    LLM_BASE_URL: ['llm', 'base_url'],
    MAX_ITERATIONS: ['llm', 'max_iterations'],
    TEMPERATURE: ['llm', 'temperature'],
    TOP_P: ['llm', 'top_p'],
    MAX_TOKENS: ['llm', 'max_tokens'],
    STREAM: ['llm', 'stream'],
    ENABLE_THINKING: ['llm', 'enable_thinking'],
    CONTEXT_TOKEN_THRESHOLD: ['agent', 'context_token_threshold'],
    KEEP_RECENT: ['agent', 'keep_recent'],
    LOOP_WINDOW: ['agent', 'loop_window'],
    GUARDRAILS_INTERVAL: ['agent', 'guardrails_interval'],
    ENABLE_PLANNING: ['planning', 'enable_planning'],
    ENABLE_REFLECTION: ['planning', 'enable_reflection'],
    MAX_RETRIES_PER_STEP: ['planning', 'max_retries_per_step'],
    ENABLE_LATS: ['lats', 'enable_lats'],
    LATS_CANDIDATES: ['lats', 'lats_candidates'],
    ALLOW_SHELL: ['security', 'allow_shell'],
    SHELL_BLACKLIST: ['security', 'shell_blacklist'],
    HITL_MODE: ['hitl', 'hitl_mode'],
    HITL_TOOLS: ['hitl', 'hitl_tools'],
    ENABLE_EVOLUTION: ['evolution', 'enable_evolution'],
    EVOLUTION_REFLECT_MIN_TOOLS: ['evolution', 'evolution_reflect_min_tools'],
    EVOLUTION_ANALYSIS_INTERVAL: ['evolution', 'evolution_analysis_interval'],
  }
  const m = mapping[envKey]
  if (!m) return null
  const group = data[m[0]] as Record<string, unknown>
  const v = group[m[1]]
  return (v ?? null) as string | number | boolean | null
}

// ── 多选下拉组件 ──────────────────────────────────────────────────
interface MultiSelectProps {
  envKey: string
  value: string  // 逗号分隔
  options: { value: string; label: string }[]
  isOpen: boolean
  onToggle: () => void
  onChange: (value: string) => void
}

function MultiSelect({ value, options, isOpen, onToggle, onChange }: MultiSelectProps) {
  const dropdownRef = useRef<HTMLDivElement>(null)
  const selected = value ? value.split(',').map((s) => s.trim()).filter(Boolean) : []

  // 点击外部关闭下拉
  useEffect(() => {
    if (!isOpen) return
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        onToggle()  // 关闭
      }
    }
    const timer = setTimeout(() => document.addEventListener('mousedown', handler), 50)
    return () => {
      clearTimeout(timer)
      document.removeEventListener('mousedown', handler)
    }
  }, [isOpen, onToggle])

  const toggleItem = (itemValue: string) => {
    const next = selected.includes(itemValue)
      ? selected.filter((v) => v !== itemValue)
      : [...selected, itemValue]
    onChange(next.join(','))
  }

  return (
    <div className="settings-multiselect" ref={dropdownRef}>
      <button className="settings-multiselect-trigger" onClick={onToggle}>
        <span className="settings-multiselect-value">
          {selected.length > 0 ? `已选 ${selected.length} 项` : '未选择'}
        </span>
        <ChevronDown size={14} className={`settings-multiselect-arrow${isOpen ? ' open' : ''}`} />
      </button>
      {isOpen && (
        <div className="settings-multiselect-dropdown">
          {options.length === 0 ? (
            <div className="settings-multiselect-empty">加载中...</div>
          ) : (
            options.map((opt) => (
              <label key={opt.value} className="settings-multiselect-item" onClick={() => toggleItem(opt.value)}>
                <span className={`settings-multiselect-checkbox${selected.includes(opt.value) ? ' checked' : ''}`}>
                  {selected.includes(opt.value) && <Check size={12} />}
                </span>
                <span className="settings-multiselect-label">{opt.label}</span>
              </label>
            ))
          )}
        </div>
      )}
    </div>
  )
}

export function SettingsPanel({ open, onClose }: SettingsPanelProps) {
  const [data, setData] = useState<SettingsData | null>(null)
  const [changes, setChanges] = useState<Record<string, string | number | boolean>>({})
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState<{ type: 'success' | 'error'; msg: string } | null>(null)
  const [toolOptions, setToolOptions] = useState<{ value: string; label: string }[]>([])
  const [openDropdown, setOpenDropdown] = useState<string | null>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  // 加载配置
  const loadSettings = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/api/settings`)
      const json = await resp.json()
      setData(json as SettingsData)
      setChanges({})
    } catch {
      setToast({ type: 'error', msg: '加载配置失败' })
    }
  }, [])

  // 加载工具列表
  const loadTools = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/api/tools`)
      const json = await resp.json()
      const tools = (json.tools || []) as string[]
      setToolOptions(tools.map((t) => ({ value: t, label: t })))
    } catch {
      // 工具列表加载失败不影响其他功能
    }
  }, [])

  useEffect(() => {
    if (open) {
      loadSettings()
      loadTools()
    }
  }, [open, loadSettings, loadTools])

  // 点击外部关闭
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    const timer = setTimeout(() => document.addEventListener('mousedown', handler), 100)
    return () => {
      clearTimeout(timer)
      document.removeEventListener('mousedown', handler)
    }
  }, [open, onClose])

  const setValue = (envKey: string, value: string | number | boolean) => {
    setChanges((prev) => ({ ...prev, [envKey]: value }))
  }

  const getDisplayValue = (envKey: string): string | number | boolean | null => {
    if (envKey in changes) return changes[envKey]
    if (!data) return null
    return getFlatValue(data, envKey)
  }

  const hasChanges = Object.keys(changes).length > 0

  const handleSave = async () => {
    if (!hasChanges) return
    setSaving(true)
    try {
      const resp = await fetch(`${API_BASE}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ changes }),
      })
      const json = await resp.json()
      if (json.updated?.length > 0) {
        setToast({ type: 'success', msg: `已更新 ${json.updated.length} 项配置` })
        setData(json.settings)
        setChanges({})
      } else {
        setToast({ type: 'error', msg: '无有效变更' })
      }
    } catch {
      setToast({ type: 'error', msg: '保存失败' })
    } finally {
      setSaving(false)
      setTimeout(() => setToast(null), 3000)
    }
  }

  const handleReset = () => {
    setChanges({})
    setToast(null)
  }

  if (!open) return null

  return (
    <div className="settings-overlay">
      <div className="settings-panel" ref={panelRef}>
        <div className="settings-header">
          <h3>Settings</h3>
          <button className="settings-close" onClick={onClose} title="关闭">
            <X size={16} />
          </button>
        </div>

        <div className="settings-body">
          {SECTIONS.map((section) => (
            <div key={section.key} className="settings-section">
              <div className="settings-section-title">{section.title}</div>
              {section.fields.map((field) => {
                const val = getDisplayValue(field.envKey)
                const changed = field.envKey in changes
                return (
                  <div key={field.envKey} className={`settings-field${changed ? ' changed' : ''}`}>
                    <label className="settings-label">
                      {field.label}
                      {field.hint && <span className="settings-hint">{field.hint}</span>}
                    </label>
                    {field.type === 'toggle' ? (
                      <button
                        className={`settings-toggle${val ? ' active' : ''}`}
                        onClick={() => setValue(field.envKey, !val)}
                      >
                        <span className="settings-toggle-thumb" />
                      </button>
                    ) : field.type === 'select' ? (
                      <select
                        className="settings-select"
                        value={String(val ?? '')}
                        onChange={(e) => setValue(field.envKey, e.target.value)}
                      >
                        {field.options?.map((opt) => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </select>
                    ) : field.type === 'multiselect' ? (
                      <MultiSelect
                        envKey={field.envKey}
                        value={String(val ?? '')}
                        options={field.getOptions ? field.getOptions() : (field.options || toolOptions)}
                        isOpen={openDropdown === field.envKey}
                        onToggle={() => setOpenDropdown(openDropdown === field.envKey ? null : field.envKey)}
                        onChange={(v) => setValue(field.envKey, v)}
                      />
                    ) : (
                      <input
                        className="settings-input"
                        type={field.type === 'number' ? 'number' : 'text'}
                        value={val != null ? String(val) : ''}
                        step={field.step}
                        min={field.min}
                        max={field.max}
                        placeholder={field.type === 'number' ? '默认' : ''}
                        onChange={(e) => {
                          const v = field.type === 'number'
                            ? (e.target.value === '' ? '' : Number(e.target.value))
                            : e.target.value
                          setValue(field.envKey, v)
                        }}
                      />
                    )}
                  </div>
                )
              })}
            </div>
          ))}
        </div>

        <div className="settings-footer">
          {toast && (
            <span className={`settings-toast ${toast.type}`}>{toast.msg}</span>
          )}
          <div className="settings-actions">
            {hasChanges && (
              <button className="btn btn-sm" onClick={handleReset} disabled={saving}>
                <RotateCcw size={13} />
                <span>重置</span>
              </button>
            )}
            <button
              className="btn btn-sm btn-primary"
              onClick={handleSave}
              disabled={saving || !hasChanges}
            >
              {saving ? <Loader2 size={13} className="spin" /> : <Save size={13} />}
              <span>{saving ? '保存中...' : '保存'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
