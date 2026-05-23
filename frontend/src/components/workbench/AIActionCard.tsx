// frontend/src/components/workbench/AIActionCard.tsx

import { useState } from 'react'
import { Check, Loader2, X, ChevronDown, ChevronRight } from 'lucide-react'
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
        <ActionItem key={i} action={action} />
      ))}
    </div>
  )
}

function ActionItem({ action }: { action: AiAction })
{
  const [expanded, setExpanded] = useState(false)
  const hasDetails = action.args || action.result

  return (
    <div className="rounded bg-slate-800/40 border border-slate-700/30">
      <button
        onClick={() => hasDetails && setExpanded(!expanded)}
        className="flex items-center gap-2 text-xs w-full text-left px-2 py-1.5 hover:bg-slate-700/30 transition-colors"
      >
        {action.status === 'done' && <Check className="h-3 w-3 text-green-400 shrink-0" />}
        {action.status === 'running' && <Loader2 className="h-3 w-3 text-blue-400 animate-spin shrink-0" />}
        {action.status === 'error' && <X className="h-3 w-3 text-red-400 shrink-0" />}
        <span className={action.status === 'running' ? 'text-blue-300' : 'text-slate-400'}>
          {action.description}
        </span>
        {hasDetails && (
          expanded
            ? <ChevronDown className="h-3 w-3 text-slate-500 ml-auto shrink-0" />
            : <ChevronRight className="h-3 w-3 text-slate-500 ml-auto shrink-0" />
        )}
      </button>
      {expanded && hasDetails && (
        <div className="px-2 pb-2 space-y-1.5 border-t border-slate-700/30">
          {action.args && (
            <div>
              <div className="text-[10px] text-slate-500 mb-0.5">输入参数</div>
              <pre className="text-[10px] text-slate-400 bg-slate-900/50 rounded px-2 py-1 overflow-auto max-h-32">
                {JSON.stringify(action.args, null, 2)}
              </pre>
            </div>
          )}
          {action.result && (
            <div>
              <div className="text-[10px] text-slate-500 mb-0.5">执行结果</div>
              <pre className="text-[10px] text-slate-400 bg-slate-900/50 rounded px-2 py-1 overflow-auto max-h-32">
                {JSON.stringify(action.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
