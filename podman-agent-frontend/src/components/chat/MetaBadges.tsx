interface MetaLineProps {
  text: string
  cls?: string
}

export function MetaLine({ text, cls }: MetaLineProps) {
  return <div className={`meta-line ${cls || ''}`}>{text}</div>
}

interface ReflectionMetaProps {
  result: 'DONE' | 'RETRY' | 'REPLAN'
  detail?: string
}

export function ReflectionMeta({ result, detail }: ReflectionMetaProps) {
  const cls = result.toLowerCase()
  const label = result === 'DONE' ? '完成' : result === 'RETRY' ? '重试' : result === 'REPLAN' ? '重规划' : result
  const preview = detail ? (detail.length > 80 ? detail.substring(0, 80) + '…' : detail) : ''

  return (
    <div className="reflection-meta">
      <span className={`result-badge ${cls}`}>{label}</span>
      <span>{preview}</span>
    </div>
  )
}

interface LatsMetaProps {
  pick: number
  total: number
  chosen?: string
}

export function LatsMeta({ pick, total, chosen }: LatsMetaProps) {
  return (
    <div className="lats-meta">
      <span className="lats-badge">LATS</span>
      <span>候选 {pick}/{total} → {chosen || ''}</span>
    </div>
  )
}
