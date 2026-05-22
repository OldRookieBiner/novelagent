import { Check, Loader2, X } from 'lucide-react'
import type { AiAction } from '@/stores/workbenchStore'

interface AIActionCardProps
{
  actions: AiAction[]
}

export function AIActionCard({ actions }: AIActionCardProps)
{
  if (actions.length === 0) return null

  return (
    <div className="space-y-1.5 my-2">
      {actions.map((action, i) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          {action.status === 'done' && <Check className="h-3 w-3 text-green-400" />}
          {action.status === 'running' && <Loader2 className="h-3 w-3 text-blue-400 animate-spin" />}
          {action.status === 'error' && <X className="h-3 w-3 text-red-400" />}
          <span className={action.status === 'running' ? 'text-blue-300' : 'text-slate-400'}>
            {action.description}
          </span>
        </div>
      ))}
    </div>
  )
}
