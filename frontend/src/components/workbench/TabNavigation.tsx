// frontend/src/components/workbench/TabNavigation.tsx

import { Lightbulb, PenTool } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useWorkbenchStore } from '@/stores/workbenchStore'

const TABS = [
  { key: 'planning' as const, label: '规划', icon: Lightbulb },
  { key: 'creation' as const, label: '创作', icon: PenTool },
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