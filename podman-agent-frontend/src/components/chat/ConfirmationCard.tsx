import { useState } from 'react'
import { ShieldAlert, Check, X } from 'lucide-react'

interface ConfirmationCardProps {
  toolName: string
  args: Record<string, unknown>
  reason: string
  requestId: string
  onDecision: (requestId: string, decision: 'approve' | 'reject') => void
}

export function ConfirmationCard({ toolName, args, reason, requestId, onDecision }: ConfirmationCardProps) {
  const [decided, setDecided] = useState<'approve' | 'reject' | null>(null)

  const handleDecision = (decision: 'approve' | 'reject') => {
    if (decided) return // 防止重复点击
    setDecided(decision)
    onDecision(requestId, decision)
  }

  const argsStr = JSON.stringify(args, null, 2)
  const argsShort = argsStr.length > 200 ? argsStr.substring(0, 200) + '…' : argsStr

  return (
    <div className={`confirmation-card${decided ? ' decided' : ''}`}>
      <div className="confirmation-header">
        <ShieldAlert size={15} />
        <span className="confirmation-title">
          {decided === 'approve' ? '已确认执行' : decided === 'reject' ? '已拒绝' : '需要确认'}
        </span>
        <span className="confirmation-tool">{toolName}</span>
      </div>
      <div className="confirmation-body">
        <div className="confirmation-reason">{reason}</div>
        {argsShort !== '{}' && (
          <div className="confirmation-args">
            <code>{argsShort}</code>
          </div>
        )}
      </div>
      {!decided && (
        <div className="confirmation-actions">
          <button className="btn btn-sm btn-confirm" onClick={() => handleDecision('approve')}>
            <Check size={13} />
            <span>确认执行</span>
          </button>
          <button className="btn btn-sm btn-reject" onClick={() => handleDecision('reject')}>
            <X size={13} />
            <span>拒绝</span>
          </button>
        </div>
      )}
    </div>
  )
}
