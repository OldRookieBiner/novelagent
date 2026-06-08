// frontend/src/components/workbench/creation/AIAssistantPanel.tsx

import { ShieldCheck, ChevronLeft, ChevronRight } from 'lucide-react'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { Button } from '@/components/ui/button'
import type { ReviewResponse } from '@/types'

interface AIAssistantPanelProps
{
  projectId?: number
  chapterNumber?: number
  chapterContent?: string
  initialReviewResult?: ReviewResponse | null
  onReviewComplete?: (result: ReviewResponse) => void
  onRewriteChunk?: (chunk: string) => void
  onRewriteDone?: (data: { chapter: { id?: number; content?: string; word_count?: number } }) => void
  onReviewCleared?: () => void
  onIssueClick?: (issue: any) => void
  collapsed?: boolean
  onToggleCollapse?: () => void
}

export function AIAssistantPanel({
  collapsed,
  onToggleCollapse,
}: AIAssistantPanelProps)
{
  const toggleAiSidebar = useWorkbenchStore((s) => s.toggleAiSidebar)

  return (
    <div className={`border-l bg-white flex flex-col h-full shrink-0 transition-all duration-300 ${collapsed ? 'w-12' : 'w-[360px]'} relative`}>
      {/* 收缩展开按钮 */}
      <button
        onClick={onToggleCollapse}
        className="absolute left-[-14px] top-1/2 -translate-y-1/2 z-10 w-7 h-7 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full flex items-center justify-center shadow-md transition-colors"
      >
        {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
      </button>
      {!collapsed && (
        <>
          {/* 标题栏 */}
          <div className="flex items-center gap-2 px-4 py-3 border-b flex-shrink-0">
            <ShieldCheck className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium">审核</span>
          </div>

          {/* 内容区 */}
          <div className="flex-1 overflow-auto p-3">
            <div className="space-y-3">
              <div className="p-4 bg-muted rounded-md text-center">
                <ShieldCheck className="h-8 w-8 text-muted-foreground/40 mx-auto mb-2" />
                <div className="text-xs text-muted-foreground leading-relaxed">
                  通过右侧 Agent 对话进行审核与重写
                </div>
              </div>
              <Button
                onClick={toggleAiSidebar}
                size="sm"
                className="w-full text-xs"
              >
                <ShieldCheck className="h-3 w-3 mr-1" />
                打开 Agent 对话
              </Button>
            </div>
          </div>
        </>
      )}
      {collapsed && (
        <div className="flex flex-col items-center pt-4 gap-3">
          <ShieldCheck className="h-4 w-4 text-muted-foreground" />
        </div>
      )}
    </div>
  )
}
