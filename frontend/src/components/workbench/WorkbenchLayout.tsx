// frontend/src/components/workbench/WorkbenchLayout.tsx

import { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { LayoutList } from 'lucide-react'
import { Button } from '@/components/ui/button'
import Header from '@/components/layout/Header'
import { TabNavigation } from './TabNavigation'
import { WorkbenchSidebar } from './WorkbenchSidebar'
import { AICompanionSidebar } from './AICompanionSidebar'

interface WorkbenchLayoutProps
{
  projectName: string
  progress: number
  children: ReactNode
}

export function WorkbenchLayout({ projectName, progress, children }: WorkbenchLayoutProps)
{
  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* 全局 Header */}
      <Header />

      {/* 项目 Header */}
      <header className="h-14 border-b bg-white flex items-center justify-between px-6 shrink-0">
        <div className="flex items-center gap-4">
          <h1 className="text-lg font-semibold">{projectName}</h1>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <div className="w-48 h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all bg-primary"
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className="text-xs font-medium text-muted-foreground">{progress}%</span>
          </div>
        </div>
        <Button asChild className="gap-1.5">
            <Link to="/">
              <LayoutList className="h-4 w-4" />
              项目列表
            </Link>
          </Button>
      </header>

      {/* Tab 导航 */}
      <TabNavigation />

      {/* 主内容区 */}
      <div className="flex flex-1 overflow-hidden">
        <WorkbenchSidebar />
        <main className="flex-1 overflow-auto">
          {children}
        </main>
        <AICompanionSidebar />
      </div>
    </div>
  )
}