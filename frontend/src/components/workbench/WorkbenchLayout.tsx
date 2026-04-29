// frontend/src/components/workbench/WorkbenchLayout.tsx

import { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { TabNavigation } from './TabNavigation'
import { WorkbenchSidebar } from './WorkbenchSidebar'

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
      {/* 顶部栏 */}
      <header className="h-14 border-b bg-white flex items-center justify-between px-6">
        <div className="flex items-center gap-4">
          <Link to="/" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft className="h-4 w-4" />
            <span>返回</span>
          </Link>
          <h1 className="text-lg font-semibold">{projectName}</h1>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <div className="w-32 h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
            <span>{progress}%</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="px-3 py-1.5 text-sm bg-primary text-white rounded-md hover:bg-primary/90">
            保存
          </button>
        </div>
      </header>

      {/* Tab 导航 */}
      <TabNavigation />

      {/* 主内容区 */}
      <div className="flex flex-1 overflow-hidden">
        <WorkbenchSidebar />
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  )
}