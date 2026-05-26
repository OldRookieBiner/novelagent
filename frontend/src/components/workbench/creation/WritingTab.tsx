// WritingTab.tsx — 写作标签页主组件

import { useWorkbenchStore } from '@/stores/workbenchStore'
import { InspirationChat } from './InspirationChat'
import { WritingPanel } from './WritingPanel'

interface WritingTabProps {
  projectId: number
}

export function WritingTab({ projectId }: WritingTabProps) {
  const phase = useWorkbenchStore((s) => s.phase)

  // 创意孵化阶段显示灵感对话
  if (phase === 'incubation') {
    return <InspirationChat projectId={projectId} />
  }

  // 结构/写作/修订阶段显示写作面板
  return <WritingPanel projectId={projectId} />
}
