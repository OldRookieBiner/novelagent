# 标签页重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将小说大纲从创作 Tab 移到规划 Tab，废除创作 Tab，将章节大纲和章节正文提升为独立顶层 Tab

**Architecture:** 修改前端类型系统、Store、Tab 导航和侧边栏组件、页面渲染逻辑。不涉及后端、API、面板组件内部逻辑。

**Tech Stack:** React, TypeScript, Zustand

---

## Files to Modify

| 文件 | 改动 |
|------|------|
| `frontend/src/types/workbench.ts` | 更新类型和菜单定义 |
| `frontend/src/stores/workbenchStore.ts` | 更新 setActiveTab 逻辑 |
| `frontend/src/components/workbench/TabNavigation.tsx` | 3 个 Tab 按钮 |
| `frontend/src/components/workbench/WorkbenchSidebar.tsx` | 移除创作菜单，限制 planning Tab 显示 |
| `frontend/src/pages/ProjectWorkbench.tsx` | 更新渲染逻辑 |
| `frontend/src/components/workbench/planning/InspirationPanel.tsx` | 修复 setActiveTab('creation') 调用 |

---

### Task 1: 修改类型定义

**Files:**
- Modify: `frontend/src/types/workbench.ts`

- [ ] **Step 1: 更新 workbench.ts 类型和菜单**

```typescript
// frontend/src/types/workbench.ts

/** 工作台 Tab 类型 */
export type WorkbenchTab = 'planning' | 'chapter_outlines' | 'writing'

/** 规划功能菜单项 */
export type PlanningMenuItem = 'inspiration' | 'outline' | 'characters' | 'relations'

/** 所有菜单项 */
export type MenuItem = PlanningMenuItem

/** 菜单配置 */
export interface MenuConfig {
  key: MenuItem
  label: string
  icon: string
}

/** 规划菜单配置 */
export const PLANNING_MENUS: MenuConfig[] = [
  { key: 'inspiration', label: '灵感', icon: 'Lightbulb' },
  { key: 'outline', label: '小说大纲', icon: 'FileText' },
  { key: 'characters', label: '人物', icon: 'Users' },
  { key: 'relations', label: '关系', icon: 'Link' },
]
```

- [ ] **Step 2: 验证 TypeScript 编译**

Run: `docker exec novelagent-frontend-1 npx tsc --noEmit 2>&1 | head -30`

Expected: 会有类型错误（其他文件尚未更新）。确认错误来自预期位置即可。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/workbench.ts
git commit -m "refactor(workbench): update tab types, move outline to planning menus"
```

---

### Task 2: 修改 Store 逻辑

**Files:**
- Modify: `frontend/src/stores/workbenchStore.ts`

- [ ] **Step 1: 更新 setActiveTab 逻辑**

将 `setActiveTab` 方法中的三元表达式替换为：

```typescript
// frontend/src/stores/workbenchStore.ts

import { create } from 'zustand'
import type { WorkbenchTab, MenuItem } from '@/types/workbench'

interface WorkbenchState
{
  // Tab 状态
  activeTab: WorkbenchTab
  setActiveTab: (tab: WorkbenchTab) => void

  // 菜单状态
  activeMenuItem: MenuItem
  setActiveMenuItem: (item: MenuItem) => void

  // 侧边栏状态
  sidebarCollapsed: boolean
  toggleSidebar: () => void

  // AI 面板状态
  aiPanelTab: 'assist' | 'review'
  setAiPanelTab: (tab: 'assist' | 'review') => void

  // Tab 切换状态保留
  panelStates: Record<string, { dirty: boolean }>
  setPanelDirty: (panelKey: string, dirty: boolean) => void

  // 重置
  reset: () => void
}

const initialState = {
  activeTab: 'planning' as WorkbenchTab,
  activeMenuItem: 'inspiration' as MenuItem,
  sidebarCollapsed: false,
  aiPanelTab: 'assist' as const,
  panelStates: {} as Record<string, { dirty: boolean }>,
}

export const useWorkbenchStore = create<WorkbenchState>((set) => ({
  ...initialState,

  setActiveTab: (tab) => {
    // 切换到规划 Tab 时重置菜单项为灵感
    if (tab === 'planning') {
      set({ activeTab: tab, activeMenuItem: 'inspiration' })
    }
    else {
      set({ activeTab: tab })
    }
  },

  setActiveMenuItem: (item) => set({ activeMenuItem: item }),

  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

  setAiPanelTab: (tab) => set({ aiPanelTab: tab }),

  setPanelDirty: (panelKey, dirty) => set((state) => ({
    panelStates: {
      ...state.panelStates,
      [panelKey]: { ...state.panelStates[panelKey], dirty }
    }
  })),

  reset: () => set(initialState),
}))
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/stores/workbenchStore.ts
git commit -m "refactor(workbench): update setActiveTab to handle new tab structure"
```

---

### Task 3: 修改 TabNavigation 组件

**Files:**
- Modify: `frontend/src/components/workbench/TabNavigation.tsx`

- [ ] **Step 1: 更新 TABS 数组**

```typescript
// frontend/src/components/workbench/TabNavigation.tsx

import { Lightbulb, BookOpen, PenTool } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useWorkbenchStore } from '@/stores/workbenchStore'

const TABS = [
  { key: 'planning' as const, label: '规划', icon: Lightbulb },
  { key: 'chapter_outlines' as const, label: '章节大纲', icon: BookOpen },
  { key: 'writing' as const, label: '章节正文', icon: PenTool },
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
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/workbench/TabNavigation.tsx
git commit -m "refactor(workbench): add chapter_outlines and 章节正文 tabs, remove 创作 tab"
```

---

### Task 4: 修改 WorkbenchSidebar 组件

**Files:**
- Modify: `frontend/src/components/workbench/WorkbenchSidebar.tsx`

- [ ] **Step 1: 仅在 planning Tab 显示侧边栏**

```typescript
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
  if (activeTab !== 'planning') {
    return null
  }

  return (
    <div className={cn(
      'flex flex-col border-r bg-white transition-all duration-300',
      sidebarCollapsed ? 'w-12' : 'w-[200px]'
    )}>
      {/* 菜单列表 */}
      <div className="flex-1 py-2">
        {PLANNING_MENUS.map((menu) =>
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
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/workbench/WorkbenchSidebar.tsx
git commit -m "refactor(workbench): hide sidebar for non-planning tabs"
```

---

### Task 5: 修改 ProjectWorkbench 页面

**Files:**
- Modify: `frontend/src/pages/ProjectWorkbench.tsx`

- [ ] **Step 1: 更新渲染逻辑为基于 activeTab**

```typescript
// frontend/src/pages/ProjectWorkbench.tsx

import { useParams } from 'react-router-dom'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { WorkbenchLayout } from '@/components/workbench/WorkbenchLayout'
import { InspirationPanel } from '@/components/workbench/planning/InspirationPanel'
import { CharacterPanel } from '@/components/workbench/planning/CharacterPanel'
import { RelationPanel } from '@/components/workbench/planning/RelationPanel'
import { OutlinePanel } from '@/components/workbench/creation/OutlinePanel'
import { ChapterOutlinePanel } from '@/components/workbench/creation/ChapterOutlinePanel'
import { WritingPanel } from '@/components/workbench/creation/WritingPanel'
import { useProjectData } from '@/hooks/useProjectData'

export default function ProjectWorkbench()
{
  const { id } = useParams<{ id: string }>()
  const projectId = id ? parseInt(id) : null
  const { activeTab, activeMenuItem } = useWorkbenchStore()
  const { project, loading } = useProjectData(projectId)

  if (loading || !project)
  {
    return <div className="flex items-center justify-center h-screen">加载中...</div>
  }

  // 渲染当前 Tab/菜单对应的面板
  const renderContent = () =>
  {
    switch (activeTab)
    {
      // 章节大纲和章节正文是独立 Tab，直接渲染面板
      case 'chapter_outlines':
        return <ChapterOutlinePanel projectId={projectId!} />
      case 'writing':
        return <WritingPanel projectId={projectId!} />

      // 规划 Tab 按侧边栏菜单项渲染
      case 'planning':
        switch (activeMenuItem)
        {
          case 'inspiration':
            return <InspirationPanel projectId={projectId!} />
          case 'outline':
            return <OutlinePanel projectId={projectId!} />
          case 'characters':
            return <CharacterPanel projectId={projectId!} />
          case 'relations':
            return <RelationPanel projectId={projectId!} />
          default:
            return null
        }

      default:
        return null
    }
  }

  return (
    <WorkbenchLayout
      projectName={project.name}
      progress={project.progress_percentage || 0}
    >
      {renderContent()}
    </WorkbenchLayout>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/ProjectWorkbench.tsx
git commit -m "refactor(workbench): update render logic to use activeTab for navigation"
```

---

### Task 6: 修复 InspirationPanel 中的 setActiveTab('creation')

**Files:**
- Modify: `frontend/src/components/workbench/planning/InspirationPanel.tsx:340`

- [ ] **Step 1: 更新灵感提交后的跳转逻辑**

将第 340-341 行：
```typescript
      setActiveTab('creation')
      setActiveMenuItem('outline')
```

改为：
```typescript
      setActiveMenuItem('outline')
```

因为小说大纲现在是规划 Tab 的子菜单项，不需要切换 Tab 了。

- [ ] **Step 2: 检查是否 setActiveTab 导入仍需保留**

看第 99 行 `const { setActiveTab, setActiveMenuItem } = useWorkbenchStore()` — `setActiveTab` 如果不再使用，移除它以消除未使用变量警告。

如果第 99 行变为：
```typescript
const { setActiveMenuItem } = useWorkbenchStore()
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workbench/planning/InspirationPanel.tsx
git commit -m "fix(workbench): update inspiration panel to navigate within planning tab"
```

---

### Task 7: 前端 TypeScript 编译和 lint 验证

**Files:**
- Verify: all modified files compile without errors

- [ ] **Step 1: TypeScript 编译检查**

Run:
```bash
docker exec novelagent-frontend-1 npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 2: Lint 检查**

Run:
```bash
docker exec novelagent-frontend-1 npm run lint
```

Expected: No errors (or only pre-existing errors unrelated to this change).

- [ ] **Step 3: Docker 构建验证**

Run:
```bash
docker compose build frontend
```

Expected: Build succeeds without errors.

- [ ] **Step 4: 启动服务验证**

Run:
```bash
docker compose up -d frontend
```

Expected: 服务正常启动，访问 http://localhost:3001 可看到新标签页布局。

- [ ] **Step 5: Commit**

```bash
git commit -m "chore: verified build and lint after tab refactor" --allow-empty
```

---

### Task 8: 手动功能验证清单

- [ ] **Step 1: 验证 3 个 Tab 正常显示**

打开项目工作台，确认看到 [规划] [章节大纲] [章节正文] 三个 Tab

- [ ] **Step 2: 验证规划 Tab 侧边栏菜单**

确认侧边栏显示：灵感 → 小说大纲 → 人物 → 关系

- [ ] **Step 3: 验证章节大纲和章节正文 Tab 无侧边栏**

切换到章节大纲/章节正文 Tab，确认侧边栏不显示，面板全屏显示

- [ ] **Step 4: 验证各面板功能正常**

在规划 Tab 下点击灵感/小说大纲/人物/关系，确认内容正常显示
在章节大纲 Tab 下确认章节大纲面板正常显示
在章节正文 Tab 下确认写作面板正常显示

- [ ] **Step 5: 验证灵感提交后跳转到小说大纲**

在灵感面板填写内容后点击确认，确认自动跳转到小说大纲面板