import { Card } from '@/components/ui/card'
import { Bot } from 'lucide-react'

interface EmptyStateProps {
  title?: string
  description?: string
}

export function EmptyState({ title = 'Podman Agent', description = '输入问题开始对话，或点击左侧菜单管理技能与记忆' }: EmptyStateProps) {
  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <Card className="flex flex-col items-center gap-3 border-none bg-transparent p-8 text-center shadow-none">
        <div className="flex size-14 items-center justify-center rounded-xl bg-secondary">
          <Bot className="size-7 text-muted-foreground" />
        </div>
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="text-sm text-muted-foreground">{description}</p>
      </Card>
    </div>
  )
}
