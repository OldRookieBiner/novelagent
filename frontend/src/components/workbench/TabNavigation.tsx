// frontend/src/components/workbench/TabNavigation.tsx

import { Sparkles, Settings, BookOpen, PenTool } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import type { WorkbenchTab } from '@/types/workbench'

const TABS: { key: WorkbenchTab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: 'inspiration', label: '灵感', icon: Sparkles },
  { key: 'settings', label: '设定', icon: Settings },
  { key: 'chapter_outlines', label: '章节大纲', icon: BookOpen },
  { key: 'writing', label: '章节正文', icon: PenTool },
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