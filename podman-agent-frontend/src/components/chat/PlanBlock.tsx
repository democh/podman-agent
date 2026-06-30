import { useState } from 'react'
import { Map, Circle, Loader2, CheckCircle2, Shuffle, ChevronRight } from 'lucide-react'

export type PlanStepStatus = 'pending' | 'active' | 'done' | 'replan'

interface PlanBlockProps {
  steps: string[]
  stepStatuses?: PlanStepStatus[]
}

const statusIcon: Record<PlanStepStatus, React.ReactNode> = {
  active: <Loader2 size={14} style={{ color: 'hsl(210 100% 45%)' }} className="animate-spin" />,
  done: <CheckCircle2 size={14} style={{ color: 'hsl(var(--success))' }} />,
  replan: <Shuffle size={14} style={{ color: 'hsl(38 92% 50%)' }} />,
  pending: <Circle size={14} style={{ color: 'hsl(var(--muted-foreground))' }} />,
}

export function PlanBlock({ steps, stepStatuses }: PlanBlockProps) {
  const [expanded, setExpanded] = useState(true)
  const statuses = stepStatuses || steps.map((_, i) => i === 0 ? 'active' as const : 'pending' as const)

  return (
    <div className={`plan-block${expanded ? ' expanded' : ''}`}>
      <div className="plan-block-header" onClick={() => setExpanded(!expanded)}>
        <span className="plan-icon"><Map size={16} /></span>
        <span>执行计划 ({steps.length} 步)</span>
        <span className="plan-chevron"><ChevronRight size={12} /></span>
      </div>
      <div className="plan-block-body">
        {steps.map((s, i) => (
          <div className="plan-step" key={i}>
            <span className="plan-step-icon">{statusIcon[statuses[i] || 'pending']}</span>
            <span className="plan-step-text">{s}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
