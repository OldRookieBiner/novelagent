// TabNavigation.tsx — 4个标签页

import { Sparkles, BookOpen, GitBranch, BarChart3 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import type { WorkbenchTab } from '@/stores/workbenchStore'

const TABS: { key: WorkbenchTab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: 'writing', label: '写作', icon: Sparkles },
  { key: 'knowledge', label: '知识库', icon: BookOpen },
  { key: 'structure', label: '结构', icon: GitBranch },
  { key: 'tracking', label: '追踪', icon: BarChart3 },
]

export function TabNavigation()
{
  const { activeTab, setActiveTab } = useWorkbenchStore()

  return (
    <div className="flex border-b bg-white">
      {TABS.map((tab) =>
      {
        const Icon = tab.icon
        const isActive = activeTab === tab.key

        return (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'flex items-center gap-2 px-6 py-3 text-sm font-medium transition-colors',
              isActive
                ? 'text-primary border-b-2 border-primary bg-primary/5'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
            )}
          >
            <Icon className="h-4 w-4" />
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
