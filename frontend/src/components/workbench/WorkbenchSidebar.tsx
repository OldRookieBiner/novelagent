// frontend/src/components/workbench/WorkbenchSidebar.tsx

import { Lightbulb, Users, Link, FileText, BookOpen, PenTool, ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { PLANNING_MENUS } from '@/types/workbench'

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  Lightbulb,
  Users,
  Link,
  FileText,
  BookOpen,
  PenTool,
}

export function WorkbenchSidebar()
{
  const { activeTab, activeMenuItem, setActiveMenuItem, sidebarCollapsed, toggleSidebar } = useWorkbenchStore()

  // 仅在规划 Tab 显示侧边栏菜单
  if (activeTab !== 'planning')
  {
    return null
  }

  const menus = PLANNING_MENUS

  return (
    <div className={cn(
      'flex flex-col border-r bg-white transition-all duration-300',
      sidebarCollapsed ? 'w-12' : 'w-[200px]'
    )}>
      {/* 菜单列表 */}
      <div className="flex-1 py-2">
        {menus.map((menu) =>
        {
          const Icon = ICON_MAP[menu.icon]
          const isActive = activeMenuItem === menu.key

          return (
            <button
              key={menu.key}
              onClick={() => setActiveMenuItem(menu.key)}
              className={cn(
                'w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors',
                isActive
                  ? 'text-primary bg-primary/10 border-r-2 border-primary'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
              )}
            >
              {Icon && <Icon className="h-4 w-4 flex-shrink-0" />}
              {!sidebarCollapsed && <span>{menu.label}</span>}
            </button>
          )
        })}
      </div>

      {/* 折叠按钮 */}
      <button
        onClick={toggleSidebar}
        className="flex items-center justify-center py-2 border-t text-muted-foreground hover:text-foreground"
      >
        {sidebarCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
      </button>
    </div>
  )
}