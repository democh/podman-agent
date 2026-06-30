import { useState } from 'react'
import { X } from 'lucide-react'
import type { SkillSummary } from '@/lib/types'

interface SidebarProps {
  open: boolean
  onClose: () => void
  skills: SkillSummary[]
  onToggleSkill: (name: string, enabled: boolean) => void
  memoryResult: string | null
  onRefreshMemory: () => void
}

export function Sidebar({ open, onClose, skills, onToggleSkill, memoryResult, onRefreshMemory }: SidebarProps) {
  const [tab, setTab] = useState<'skills' | 'memory'>('skills')

  const switchTab = (t: 'skills' | 'memory') => {
    setTab(t)
    if (t === 'memory') onRefreshMemory()
  }

  return (
    <div className={`sidebar${open ? '' : ' collapsed'}`}>
      <div className="sidebar-header">
        <span className="sidebar-title">{tab === 'skills' ? '技能管理' : '记忆库'}</span>
        <button className="btn btn-ghost btn-icon btn-sm" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      <div className="sidebar-tabs">
        <div className={`sidebar-tab${tab === 'skills' ? ' active' : ''}`} onClick={() => switchTab('skills')}>技能</div>
        <div className={`sidebar-tab${tab === 'memory' ? ' active' : ''}`} onClick={() => switchTab('memory')}>记忆</div>
      </div>
      <div className="sidebar-content">
        {tab === 'skills' ? (
          <SkillsList skills={skills} onToggle={onToggleSkill} />
        ) : (
          <MemoryList memoryResult={memoryResult} />
        )}
      </div>
    </div>
  )
}

function SkillsList({ skills, onToggle }: { skills: SkillSummary[]; onToggle: (name: string, enabled: boolean) => void }) {
  if (!skills.length) {
    return (
      <div style={{ textAlign: 'center', color: 'hsl(var(--muted-foreground))', fontSize: 13, padding: '20px 8px' }}>
        暂无技能<br /><span style={{ fontSize: 11 }}>在 skills/ 目录创建 .md 文件</span>
      </div>
    )
  }
  return (
    <>
      {skills.map((s) => (
        <div className="skill-card" key={s.name}>
          <div className="skill-card-top">
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="skill-name">{s.name}</div>
              <div className="skill-desc">{s.description || ''}</div>
            </div>
            <label className="toggle">
              <input type="checkbox" checked={s.enabled} onChange={(e) => onToggle(s.name, e.target.checked)} />
              <span className="toggle-slider" />
            </label>
          </div>
          {s.triggers && s.triggers.length > 0 && (
            <div className="skill-triggers">
              {s.triggers.map((t) => (
                <span className="skill-trigger" key={t}>{t}</span>
              ))}
            </div>
          )}
        </div>
      ))}
    </>
  )
}

function MemoryList({ memoryResult }: { memoryResult: string | null }) {
  if (!memoryResult) {
    return (
      <div style={{ textAlign: 'center', padding: '16px 8px', color: 'hsl(var(--muted-foreground))', fontSize: 13 }}>
        记忆列表加载中...
      </div>
    )
  }
  if (memoryResult.includes('(记忆库为空)')) {
    return (
      <div style={{ textAlign: 'center', color: 'hsl(var(--muted-foreground))', fontSize: 13, padding: '20px 8px' }}>
        记忆库为空<br /><span style={{ fontSize: 11 }}>对话中让 Agent 记住信息</span>
      </div>
    )
  }
  const lines = memoryResult.split('\n').filter((l) => l.trim())
  return (
    <>
      {lines.map((line, i) => {
        const m = line.match(/^\s*-\s*\[(\w+)\]\s*(.+?)\s*\(keywords:\s*(.*?),\s*updated:\s*(.*?)\)\s*$/)
        if (m) {
          return (
            <div className="memory-card" key={i}>
              <div className="mem-title">{m[2]}</div>
              <div className="mem-meta">[{m[1]}] {m[3]} · {m[4]}</div>
            </div>
          )
        }
        return (
          <div className="memory-card" key={i}>
            <div className="mem-title">{line}</div>
          </div>
        )
      })}
    </>
  )
}
