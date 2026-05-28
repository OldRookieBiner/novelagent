// WritingTab.tsx — 写作标签页主组件

import { useState } from 'react'
import { Info, X } from 'lucide-react'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { WritingPanel } from './WritingPanel'

interface WritingTabProps {
  projectId: number
}

const PHASE_GUIDANCE: Record<string, { message: string; show: boolean }> = {
  incubation: {
    message: '当前处于创意孵化阶段，请先在右侧智能体中完善知识库，完成后切换到结构设计阶段',
    show: true,
  },
  structure: {
    message: '请完成结构设计后再开始写作，你可以在右侧智能体中讨论情节安排',
    show: true,
  },
  writing: { message: '', show: false },
  revision: { message: '', show: false },
}

export function WritingTab({ projectId }: WritingTabProps) {
  const phase = useWorkbenchStore((s) => s.phase)
  const [dismissed, setDismissed] = useState(false)
  const guidance = PHASE_GUIDANCE[phase]

  return (
    <div className="flex flex-col h-full">
      {guidance.show && !dismissed && (
        <div className="mx-6 mt-4 flex items-start gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-xs text-blue-800">
          <Info className="h-4 w-4 shrink-0 mt-0.5" />
          <span className="flex-1">{guidance.message}</span>
          <button
            onClick={() => setDismissed(true)}
            className="shrink-0 text-blue-400 hover:text-blue-600"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
      <WritingPanel projectId={projectId} />
    </div>
  )
}
