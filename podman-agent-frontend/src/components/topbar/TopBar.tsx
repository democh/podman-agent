import { Menu, Coins, Archive, Settings } from 'lucide-react'
import type { ConnectionStatus, SkillSummary } from '@/lib/types'

interface TopBarProps {
  model: string
  tools: string[]
  skills: SkillSummary[]
  status: ConnectionStatus
  busy: boolean
  totalTokens?: number
  tokenWarning?: { usage_pct: number; message: string } | null
  onToggleSidebar: () => void
  onReset: () => void
  onCompress: () => void
  onToggleSettings: () => void
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

export function TopBar({ model, tools, skills, status, busy, totalTokens, tokenWarning, onToggleSidebar, onReset, onCompress, onToggleSettings }: TopBarProps) {
  const activeSkills = skills.filter((s) => s.enabled).length
  const statusClass = busy ? 'busy' : status === 'connected' ? 'connected' : status === 'error' ? 'error' : ''
  const statusLabel = busy ? '思考中' : status === 'connected' ? '已连接' : status === 'connecting' ? '连接中' : status === 'disconnected' ? '已断开' : '错误'

  return (
    <div className="topbar">
      <button className="btn btn-ghost btn-icon" onClick={onToggleSidebar} title="技能与记忆">
        <Menu size={16} />
      </button>
      <span className="logo">Podman Agent</span>
      <span className="badge-pill">{model || '—'}</span>
      <span className="badge-pill">{tools.length} tools</span>
      {skills.length > 0 && (
        <span className="badge-pill">
          <span className="dot" style={{ background: activeSkills > 0 ? 'hsl(var(--success))' : 'hsl(var(--muted-foreground))' }} />
          {activeSkills}/{skills.length} skills
        </span>
      )}
      {(totalTokens ?? 0) > 0 && (
        <span className={`badge-pill token-badge${tokenWarning ? ' token-warning' : ''}`} title={`累计 token 用量: ${totalTokens}`}>
          <Coins size={12} />
          {formatTokens(totalTokens ?? 0)}
        </span>
      )}
      {tokenWarning && (
        <button
          className="btn btn-sm btn-compress"
          title={tokenWarning.message}
          disabled={busy}
          onClick={onCompress}
        >
          <Archive size={12} />
          <span>压缩</span>
        </button>
      )}
      <div className="spacer" />
      <span className={`status-dot ${statusClass}`} />
      <span className="status-text">{statusLabel}</span>
      <button className="btn btn-sm" disabled={busy} onClick={onReset}>重置</button>
      <button className="btn btn-ghost btn-icon btn-settings" onClick={onToggleSettings} title="设置">
        <Settings size={15} />
      </button>
    </div>
  )
}
