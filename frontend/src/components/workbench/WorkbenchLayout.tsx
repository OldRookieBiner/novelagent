// WorkbenchLayout.tsx — 三栏+标签页+底栏布局

import { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { LayoutList } from 'lucide-react'
import { Button } from '@/components/ui/button'
import Header from '@/components/layout/Header'
import { TabNavigation } from './TabNavigation'
import { ChapterListPanel } from './ChapterListPanel'
import { AgentChatPanel } from './AgentChatPanel'
import { ProgressDashboard } from './ProgressDashboard'
import { useWorkbenchStore } from '@/stores/workbenchStore'

export interface PlotBlockGroup {
  title: string
  chapters: { chapterNumber: number; title: string; status: 'written' | 'writing' | 'pending' }[]
  isActive: boolean
}

interface WorkbenchLayoutProps {
  projectName: string
  progress: number
  plotBlocks: PlotBlockGroup[]
  rhythmData?: number[]
  pendingForeshadowings?: number
  overdueForeshadowings?: number
  styleStatus?: 'stable' | 'drift' | 'unknown'
  currentBlock?: string
  children: ReactNode
}

export function WorkbenchLayout({
  projectName,
  progress,
  plotBlocks,
  rhythmData = [],
  pendingForeshadowings = 0,
  overdueForeshadowings = 0,
  styleStatus = 'unknown',
  currentBlock = '',
  children,
}: WorkbenchLayoutProps) {
  const phase = useWorkbenchStore((s) => s.phase)

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* 全局 Header */}
      <Header />

      {/* 项目 Header */}
      <header className="h-12 border-b bg-white flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-base font-semibold">{projectName}</h1>
          <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
            {phase === 'incubation' ? '创意孵化' : phase === 'structure' ? '结构设计' : phase === 'writing' ? '写作中' : '修订中'}
          </span>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <div className="w-32 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all bg-primary"
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className="text-[10px]">{progress}%</span>
          </div>
        </div>
        <Button asChild variant="outline" size="sm" className="gap-1.5">
          <Link to="/">
            <LayoutList className="h-3.5 w-3.5" />
            项目列表
          </Link>
        </Button>
      </header>

      {/* Tab 导航 */}
      <TabNavigation />

      {/* 主内容区：三栏 */}
      <div className="flex flex-1 overflow-hidden">
        {/* 左栏：章节列表 */}
        <ChapterListPanel blocks={plotBlocks} />

        {/* 中栏：标签页内容 */}
        <main className="flex-1 overflow-auto">
          {children}
        </main>

        {/* 右栏：智能体对话 */}
        <AgentChatPanel />
      </div>

      {/* 底栏：进度仪表盘 */}
      <ProgressDashboard
        rhythmData={rhythmData}
        pendingForeshadowings={pendingForeshadowings}
        overdueForeshadowings={overdueForeshadowings}
        styleStatus={styleStatus}
        currentBlock={currentBlock}
        progress={progress}
      />
    </div>
  )
}
