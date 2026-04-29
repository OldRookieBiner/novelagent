# 工作台页面重设计实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构前端工作台页面，采用 Tab 分组布局，新建 ProjectWorkbench.tsx 页面并逐步迁移现有功能。

**Architecture:** 新建工作台页面组件，采用 Tab + 侧边栏菜单布局。规划/创作/审核三个 Tab，每个 Tab 下有对应的功能菜单。写作页面的 AI 助手合并审核功能。

**Tech Stack:** React 18, TypeScript, Zustand, shadcn/ui, Tailwind CSS

---

## 文件结构

```
frontend/src/
├── pages/
│   └── ProjectWorkbench.tsx           # 新工作台主页面
├── components/workbench/
│   ├── WorkbenchLayout.tsx            # 工作台布局框架
│   ├── TabNavigation.tsx              # Tab导航组件
│   ├── WorkbenchSidebar.tsx           # 左侧功能菜单
│   ├── planning/
│   │   ├── InspirationPanel.tsx       # 灵感采集面板
│   │   ├── CharacterPanel.tsx         # 人物管理面板
│   │   └── RelationPanel.tsx          # 关系管理面板
│   └── creation/
│       ├── OutlinePanel.tsx           # 大纲编辑面板
│       ├── ChapterOutlinePanel.tsx    # 章节大纲面板
│       ├── WritingPanel.tsx           # 写作面板
│       └── AIAssistantPanel.tsx       # AI助手面板（含审核）
├── stores/
│   └── workbenchStore.ts              # 工作台状态管理
└── types/
    └── workbench.ts                   # 工作台类型定义
```

---

## Task 1: 类型定义和状态管理

**Files:**
- Create: `frontend/src/types/workbench.ts`
- Create: `frontend/src/stores/workbenchStore.ts`

- [ ] **Step 1: 创建类型定义文件**

```typescript
// frontend/src/types/workbench.ts

/** 工作台 Tab 类型 */
export type WorkbenchTab = 'planning' | 'creation'

/** 规划功能菜单项 */
export type PlanningMenuItem = 'inspiration' | 'characters' | 'relations'

/** 创作功能菜单项 */
export type CreationMenuItem = 'outline' | 'chapter_outlines' | 'writing'

/** 所有菜单项 */
export type MenuItem = PlanningMenuItem | CreationMenuItem

/** 菜单配置 */
export interface MenuConfig {
  key: MenuItem
  label: string
  icon: string
}

/** 规划菜单配置 */
export const PLANNING_MENUS: MenuConfig[] = [
  { key: 'inspiration', label: '灵感', icon: 'Lightbulb' },
  { key: 'characters', label: '人物', icon: 'Users' },
  { key: 'relations', label: '关系', icon: 'Link' },
]

/** 创作菜单配置 */
export const CREATION_MENUS: MenuConfig[] = [
  { key: 'outline', label: '小说大纲', icon: 'FileText' },
  { key: 'chapter_outlines', label: '章节大纲', icon: 'BookOpen' },
  { key: 'writing', label: '写作', icon: 'PenTool' },
]
```

- [ ] **Step 2: 创建 Zustand Store**

```typescript
// frontend/src/stores/workbenchStore.ts

import { create } from 'zustand'
import type { WorkbenchTab, MenuItem } from '@/types/workbench'

interface WorkbenchState {
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

  // 重置
  reset: () => void
}

const initialState = {
  activeTab: 'planning' as WorkbenchTab,
  activeMenuItem: 'inspiration' as MenuItem,
  sidebarCollapsed: false,
  aiPanelTab: 'assist' as const,
}

export const useWorkbenchStore = create<WorkbenchState>((set) => ({
  ...initialState,

  setActiveTab: (tab) => set({ 
    activeTab: tab,
    // 切换 Tab 时重置菜单项到第一个
    activeMenuItem: tab === 'planning' ? 'inspiration' : 'outline'
  }),

  setActiveMenuItem: (item) => set({ activeMenuItem: item }),

  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

  setAiPanelTab: (tab) => set({ aiPanelTab: tab }),

  reset: () => set(initialState),
}))
```

- [ ] **Step 3: 提交类型和状态管理**

```bash
git add frontend/src/types/workbench.ts frontend/src/stores/workbenchStore.ts
git commit -m "feat(workbench): add workbench types and store"
```

---

## Task 2: 工作台布局组件

**Files:**
- Create: `frontend/src/components/workbench/TabNavigation.tsx`
- Create: `frontend/src/components/workbench/WorkbenchSidebar.tsx`
- Create: `frontend/src/components/workbench/WorkbenchLayout.tsx`

- [ ] **Step 1: 创建 Tab 导航组件**

```tsx
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
```

- [ ] **Step 2: 创建侧边栏菜单组件**

```tsx
// frontend/src/components/workbench/WorkbenchSidebar.tsx

import { Lightbulb, Users, Link, FileText, BookOpen, PenTool, ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { PLANNING_MENUS, CREATION_MENUS } from '@/types/workbench'

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

  const menus = activeTab === 'planning' ? PLANNING_MENUS : CREATION_MENUS

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
```

- [ ] **Step 3: 创建工作台布局组件**

```tsx
// frontend/src/components/workbench/WorkbenchLayout.tsx

import { ReactNode } from 'react'
import { TabNavigation } from './TabNavigation'
import { WorkbenchSidebar } from './WorkbenchSidebar'

interface WorkbenchLayoutProps
{
  projectId: number
  projectName: string
  progress: number
  children: ReactNode
}

export function WorkbenchLayout({ projectId, projectName, progress, children }: WorkbenchLayoutProps)
{
  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* 顶部栏 */}
      <header className="h-14 border-b bg-white flex items-center justify-between px-6">
        <div className="flex items-center gap-4">
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
```

- [ ] **Step 4: 提交布局组件**

```bash
git add frontend/src/components/workbench/
git commit -m "feat(workbench): add layout components"
```

---

## Task 3: 工作台主页面

**Files:**
- Create: `frontend/src/pages/ProjectWorkbench.tsx`
- Modify: `frontend/src/App.tsx` (添加路由)

- [ ] **Step 1: 创建工作台主页面**

```tsx
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
  const { activeMenuItem } = useWorkbenchStore()
  const { project, loading } = useProjectData(projectId)

  if (loading || !project)
  {
    return <div className="flex items-center justify-center h-screen">加载中...</div>
  }

  // 渲染当前菜单对应的面板
  const renderContent = () =>
  {
    switch (activeMenuItem)
    {
      // 规划
      case 'inspiration':
        return <InspirationPanel projectId={projectId!} />
      case 'characters':
        return <CharacterPanel projectId={projectId!} />
      case 'relations':
        return <RelationPanel projectId={projectId!} />
      // 创作
      case 'outline':
        return <OutlinePanel projectId={projectId!} />
      case 'chapter_outlines':
        return <ChapterOutlinePanel projectId={projectId!} />
      case 'writing':
        return <WritingPanel projectId={projectId!} />
      default:
        return null
    }
  }

  return (
    <WorkbenchLayout
      projectId={projectId!}
      projectName={project.name}
      progress={0}
    >
      {renderContent()}
    </WorkbenchLayout>
  )
}
```

- [ ] **Step 2: 添加路由**

在 `frontend/src/App.tsx` 中添加路由：

```tsx
// 在现有路由后添加
import ProjectWorkbench from '@/pages/ProjectWorkbench'

// 在路由配置中添加
<Route path="project/:id/workbench" element={<ProjectWorkbench />} />
```

- [ ] **Step 3: 提交主页面**

```bash
git add frontend/src/pages/ProjectWorkbench.tsx frontend/src/App.tsx
git commit -m "feat(workbench): add ProjectWorkbench page and route"
```

---

## Task 4: 灵感采集面板

**Files:**
- Create: `frontend/src/components/workbench/planning/InspirationPanel.tsx`

- [ ] **Step 1: 创建灵感采集面板**

```tsx
// frontend/src/components/workbench/planning/InspirationPanel.tsx

import { useState } from 'react'
import { Lightbulb, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface InspirationPanelProps
{
  projectId: number
}

export function InspirationPanel({ projectId }: InspirationPanelProps)
{
  const [formData, setFormData] = useState({
    title: '',
    novelType: '玄幻',
    targetReader: '成人',
    coreConcept: '',
    coreTheme: '',
    protagonistName: '',
    protagonistPersonality: '',
    antagonistName: '',
    antagonistMotivation: '',
    mainPlot: '',
    worldSetting: '',
  })

  const handleChange = (field: string, value: string) =>
  {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  return (
    <div className="flex h-full">
      {/* 左侧进度提示 */}
      <div className="w-64 border-r bg-white p-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">灵感完善度</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-primary">35%</div>
            <p className="text-xs text-muted-foreground mt-1">建议补充主角设定和主线剧情</p>
          </CardContent>
        </Card>
      </div>

      {/* 中间表单 */}
      <div className="flex-1 p-6 overflow-auto">
        <div className="max-w-4xl mx-auto space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <Lightbulb className="h-5 w-5" />
              灵感采集
            </h2>
            <Button variant="outline" size="sm">
              <Sparkles className="h-4 w-4 mr-2" />
              AI 帮我完善
            </Button>
          </div>

          {/* 基本信息 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">基本信息</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-muted-foreground">小说标题</label>
                <Input
                  value={formData.title}
                  onChange={(e) => handleChange('title', e.target.value)}
                  placeholder="输入小说标题"
                />
              </div>
              <div>
                <label className="text-sm text-muted-foreground">小说类型</label>
                <select
                  className="w-full h-10 px-3 border rounded-md"
                  value={formData.novelType}
                  onChange={(e) => handleChange('novelType', e.target.value)}
                >
                  <option>玄幻</option>
                  <option>都市</option>
                  <option>科幻</option>
                  <option>言情</option>
                  <option>悬疑</option>
                </select>
              </div>
            </CardContent>
          </Card>

          {/* 核心概念 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">核心概念</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm text-muted-foreground">一句话概述</label>
                <Textarea
                  value={formData.coreConcept}
                  onChange={(e) => handleChange('coreConcept', e.target.value)}
                  placeholder="用一句话概括你的故事"
                  rows={2}
                />
              </div>
              <div>
                <label className="text-sm text-muted-foreground">核心主题</label>
                <Textarea
                  value={formData.coreTheme}
                  onChange={(e) => handleChange('coreTheme', e.target.value)}
                  placeholder="故事想要表达什么主题"
                  rows={2}
                />
              </div>
            </CardContent>
          </Card>

          {/* 主角设定 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">主角设定</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-muted-foreground">姓名</label>
                <Input
                  value={formData.protagonistName}
                  onChange={(e) => handleChange('protagonistName', e.target.value)}
                  placeholder="主角姓名"
                />
              </div>
              <div>
                <label className="text-sm text-muted-foreground">性格特点</label>
                <Input
                  value={formData.protagonistPersonality}
                  onChange={(e) => handleChange('protagonistPersonality', e.target.value)}
                  placeholder="性格描述"
                />
              </div>
            </CardContent>
          </Card>

          {/* 主线剧情 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">主线剧情</CardTitle>
            </CardHeader>
            <CardContent>
              <Textarea
                value={formData.mainPlot}
                onChange={(e) => handleChange('mainPlot', e.target.value)}
                placeholder="描述故事的主线剧情"
                rows={4}
              />
            </CardContent>
          </Card>

          {/* 世界观设定 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">世界观设定</CardTitle>
            </CardHeader>
            <CardContent>
              <Textarea
                value={formData.worldSetting}
                onChange={(e) => handleChange('worldSetting', e.target.value)}
                placeholder="描述故事发生的世界背景"
                rows={4}
              />
            </CardContent>
          </Card>
        </div>
      </div>

      {/* 右侧 AI 助手 */}
      <div className="w-80 border-l bg-white p-4">
        <h3 className="font-medium mb-4">AI 建议</h3>
        <div className="space-y-3">
          <div className="p-3 bg-muted rounded-md text-sm">
            <p className="font-medium">补充主角目标</p>
            <p className="text-muted-foreground text-xs mt-1">主角的核心目标能让故事更有张力</p>
          </div>
          <div className="p-3 bg-muted rounded-md text-sm">
            <p className="font-medium">完善反派动机</p>
            <p className="text-muted-foreground text-xs mt-1">合理的反派动机让冲突更可信</p>
          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 提交灵感面板**

```bash
git add frontend/src/components/workbench/planning/InspirationPanel.tsx
git commit -m "feat(workbench): add InspirationPanel component"
```

---

## Task 5: 人物管理面板（大卡片布局）

**Files:**
- Create: `frontend/src/components/workbench/planning/CharacterPanel.tsx`

- [ ] **Step 1: 创建人物管理面板**

```tsx
// frontend/src/components/workbench/planning/CharacterPanel.tsx

import { useState, useEffect } from 'react'
import { Users, Plus, Edit, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { characterApi } from '@/lib/characterApi'
import type { Character } from '@/types'

interface CharacterPanelProps
{
  projectId: number
}

const ROLE_COLORS: Record<string, string> = {
  '主角': 'bg-yellow-100 text-yellow-800',
  '核心反派': 'bg-red-100 text-red-800',
  '重要配角': 'bg-blue-100 text-blue-800',
  '配角': 'bg-gray-100 text-gray-800',
}

export function CharacterPanel({ projectId }: CharacterPanelProps)
{
  const [characters, setCharacters] = useState<Character[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() =>
  {
    const fetchCharacters = async () =>
    {
      try
      {
        const data = await characterApi.list(projectId)
        setCharacters(data.characters)
      }
      catch (err)
      {
        console.error('Failed to fetch characters:', err)
      }
      finally
      {
        setLoading(false)
      }
    }
    fetchCharacters()
  }, [projectId])

  if (loading)
  {
    return <div className="flex items-center justify-center h-full">加载中...</div>
  }

  return (
    <div className="p-6 overflow-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Users className="h-5 w-5" />
          人物管理
        </h2>
        <Button size="sm">
          <Plus className="h-4 w-4 mr-2" />
          新增人物
        </Button>
      </div>

      {/* 大卡片网格 */}
      <div className="grid grid-cols-2 gap-6">
        {characters.map((character) => (
          <Card key={character.id} className="min-h-[280px]">
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center text-lg font-medium">
                    {character.name.charAt(0)}
                  </div>
                  <div>
                    <CardTitle className="text-lg">{character.name}</CardTitle>
                    <span className={`inline-block mt-1 px-2 py-0.5 text-xs rounded-full ${ROLE_COLORS[character.role] || 'bg-gray-100'}`}>
                      {character.role}
                    </span>
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {character.personality && (
                <div>
                  <span className="text-xs text-muted-foreground">性格</span>
                  <p className="text-sm line-clamp-2">{character.personality}</p>
                </div>
              )}
              {character.core_motivation && (
                <div>
                  <span className="text-xs text-muted-foreground">核心动机</span>
                  <p className="text-sm line-clamp-1">{character.core_motivation}</p>
                </div>
              )}
              {character.catchphrase && (
                <div>
                  <span className="text-xs text-muted-foreground">口头禅</span>
                  <p className="text-sm italic">"{character.catchphrase}"</p>
                </div>
              )}
              <div className="flex items-center justify-between pt-2 border-t">
                <span className="text-xs text-muted-foreground">关系: 0</span>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm">
                    <Edit className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="sm">
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}

        {/* 添加新人物卡片 */}
        <Card className="min-h-[280px] border-dashed flex items-center justify-center cursor-pointer hover:bg-muted/50 transition-colors">
          <div className="text-center text-muted-foreground">
            <Plus className="h-8 w-8 mx-auto mb-2" />
            <span>添加新人物</span>
          </div>
        </Card>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 提交人物面板**

```bash
git add frontend/src/components/workbench/planning/CharacterPanel.tsx
git commit -m "feat(workbench): add CharacterPanel with large cards layout"
```

---

## Task 6: 关系管理面板（列表布局）

**Files:**
- Create: `frontend/src/components/workbench/planning/RelationPanel.tsx`

- [ ] **Step 1: 创建关系管理面板**

```tsx
// frontend/src/components/workbench/planning/RelationPanel.tsx

import { useState, useEffect } from 'react'
import { Link, Plus, Edit, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { relationApi } from '@/lib/characterApi'
import type { RelationWithCharacters } from '@/types'

interface RelationPanelProps
{
  projectId: number
}

const RELATION_COLORS: Record<string, string> = {
  '信任': 'bg-green-100 text-green-800',
  '敌对': 'bg-red-100 text-red-800',
  '感情': 'bg-pink-100 text-pink-800',
  '合作': 'bg-blue-100 text-blue-800',
  '利用': 'bg-orange-100 text-orange-800',
  '陌生': 'bg-gray-100 text-gray-800',
}

export function RelationPanel({ projectId }: RelationPanelProps)
{
  const [relations, setRelations] = useState<RelationWithCharacters[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() =>
  {
    const fetchRelations = async () =>
    {
      try
      {
        const data = await relationApi.list(projectId)
        setRelations(data.relations)
      }
      catch (err)
      {
        console.error('Failed to fetch relations:', err)
      }
      finally
      {
        setLoading(false)
      }
    }
    fetchRelations()
  }, [projectId])

  if (loading)
  {
    return <div className="flex items-center justify-center h-full">加载中...</div>
  }

  return (
    <div className="p-6 overflow-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Link className="h-5 w-5" />
          人物关系
        </h2>
        <Button size="sm">
          <Plus className="h-4 w-4 mr-2" />
          新增关系
        </Button>
      </div>

      {/* 关系列表表格 */}
      <div className="bg-white rounded-lg border">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-4 py-3 text-left text-sm font-medium">人物A</th>
              <th className="px-4 py-3 text-left text-sm font-medium">关系类型</th>
              <th className="px-4 py-3 text-left text-sm font-medium">人物B</th>
              <th className="px-4 py-3 text-left text-sm font-medium">当前状态</th>
              <th className="px-4 py-3 text-left text-sm font-medium">信任度</th>
              <th className="px-4 py-3 text-left text-sm font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {relations.map((relation) => (
              <tr key={relation.id} className="border-b last:border-b-0 hover:bg-muted/30">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-sm">
                      {relation.character_a?.name?.charAt(0) || '?'}
                    </div>
                    <span className="font-medium">{relation.character_a?.name || '未知'}</span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 text-xs rounded-full ${RELATION_COLORS[relation.relation_type] || 'bg-gray-100'}`}>
                    {relation.relation_type}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-sm">
                      {relation.character_b?.name?.charAt(0) || '?'}
                    </div>
                    <span className="font-medium">{relation.character_b?.name || '未知'}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-sm text-muted-foreground">
                  {relation.current_status || '-'}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div 
                        className={`h-full rounded-full ${relation.trust_level > 60 ? 'bg-green-500' : relation.trust_level > 30 ? 'bg-yellow-500' : 'bg-red-500'}`}
                        style={{ width: `${relation.trust_level}%` }}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground">{relation.trust_level}</span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1">
                    <Button variant="ghost" size="sm">
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm">
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {relations.length === 0 && (
          <div className="py-12 text-center text-muted-foreground">
            <Link className="h-12 w-12 mx-auto mb-4 opacity-20" />
            <p>暂无人物关系</p>
            <p className="text-sm mt-1">点击上方按钮添加人物关系</p>
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 提交关系面板**

```bash
git add frontend/src/components/workbench/planning/RelationPanel.tsx
git commit -m "feat(workbench): add RelationPanel with table layout"
```

---

## Task 7: 小说大纲面板

**Files:**
- Create: `frontend/src/components/workbench/creation/OutlinePanel.tsx`

- [ ] **Step 1: 创建大纲面板**

```tsx
// frontend/src/components/workbench/creation/OutlinePanel.tsx

import { useState, useEffect } from 'react'
import { FileText, Sparkles, Save, Plus, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { outlineApi } from '@/lib/api'
import type { Outline } from '@/types'

interface OutlinePanelProps
{
  projectId: number
}

export function OutlinePanel({ projectId }: OutlinePanelProps)
{
  const [outline, setOutline] = useState<Outline | null>(null)
  const [loading, setLoading] = useState(true)
  const [plotPoints, setPlotPoints] = useState<string[]>([])

  useEffect(() =>
  {
    const fetchOutline = async () =>
    {
      try
      {
        const data = await outlineApi.get(projectId)
        setOutline(data)
        setPlotPoints(data.plot_points?.map(p => typeof p === 'string' ? p : p.event) || [])
      }
      catch (err)
      {
        console.error('Failed to fetch outline:', err)
      }
      finally
      {
        setLoading(false)
      }
    }
    fetchOutline()
  }, [projectId])

  const addPlotPoint = () =>
  {
    setPlotPoints([...plotPoints, ''])
  }

  const removePlotPoint = (index: number) =>
  {
    setPlotPoints(plotPoints.filter((_, i) => i !== index))
  }

  const updatePlotPoint = (index: number, value: string) =>
  {
    const updated = [...plotPoints]
    updated[index] = value
    setPlotPoints(updated)
  }

  if (loading)
  {
    return <div className="flex items-center justify-center h-full">加载中...</div>
  }

  return (
    <div className="flex h-full">
      {/* 左侧 AI 助手 */}
      <div className="w-80 border-r bg-white p-4">
        <h3 className="font-medium mb-4 flex items-center gap-2">
          <Sparkles className="h-4 w-4" />
          AI 建议
        </h3>
        <div className="space-y-3">
          <div className="p-3 bg-muted rounded-md text-sm">
            <p className="font-medium">情节建议</p>
            <p className="text-muted-foreground text-xs mt-1">可以在第3章加入转折</p>
          </div>
          <div className="p-3 bg-muted rounded-md text-sm">
            <p className="font-medium">角色发展</p>
            <p className="text-muted-foreground text-xs mt-1">主角的动机可以更明确</p>
          </div>
        </div>
      </div>

      {/* 中间编辑区 */}
      <div className="flex-1 p-6 overflow-auto">
        <div className="max-w-3xl mx-auto space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <FileText className="h-5 w-5" />
              小说大纲
            </h2>
            <div className="flex gap-2">
              <Button variant="outline" size="sm">
                <Sparkles className="h-4 w-4 mr-2" />
                AI 生成
              </Button>
              <Button size="sm">
                <Save className="h-4 w-4 mr-2" />
                保存
              </Button>
            </div>
          </div>

          <Card>
            <CardContent className="pt-6 space-y-4">
              <div>
                <label className="text-sm text-muted-foreground">小说标题</label>
                <Input
                  value={outline?.title || ''}
                  placeholder="输入小说标题"
                  className="mt-1"
                />
              </div>

              <div>
                <label className="text-sm text-muted-foreground">一句话简介</label>
                <Input
                  value={outline?.summary?.split('\n')[0] || ''}
                  placeholder="用一句话概括故事"
                  className="mt-1"
                />
              </div>

              <div>
                <label className="text-sm text-muted-foreground">故事概述</label>
                <Textarea
                  value={outline?.summary || ''}
                  placeholder="详细描述故事内容"
                  rows={6}
                  className="mt-1"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm text-muted-foreground">主要情节节点</label>
                  <Button variant="outline" size="sm" onClick={addPlotPoint}>
                    <Plus className="h-4 w-4 mr-1" />
                    添加
                  </Button>
                </div>
                <div className="space-y-2">
                  {plotPoints.map((point, index) => (
                    <div key={index} className="flex gap-2">
                      <span className="w-8 h-8 flex items-center justify-center bg-muted rounded text-sm">
                        {index + 1}
                      </span>
                      <Input
                        value={point}
                        onChange={(e) => updatePlotPoint(index, e.target.value)}
                        placeholder="描述情节节点"
                        className="flex-1"
                      />
                      <Button variant="ghost" size="sm" onClick={() => removePlotPoint(index)}>
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-sm text-muted-foreground">章节数量建议</label>
                <Input
                  type="number"
                  value={outline?.chapter_count_suggested || 10}
                  className="mt-1 w-32"
                />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 提交大纲面板**

```bash
git add frontend/src/components/workbench/creation/OutlinePanel.tsx
git commit -m "feat(workbench): add OutlinePanel component"
```

---

## Task 8: 章节大纲面板（三栏布局）

**Files:**
- Create: `frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx`

- [ ] **Step 1: 创建章节大纲面板**

```tsx
// frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx

import { useState, useEffect } from 'react'
import { BookOpen, Plus, Save, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { chapterOutlinesApi } from '@/lib/api'
import type { ChapterOutline } from '@/types'

interface ChapterOutlinePanelProps
{
  projectId: number
}

export function ChapterOutlinePanel({ projectId }: ChapterOutlinePanelProps)
{
  const [chapters, setChapters] = useState<ChapterOutline[]>([])
  const [selectedChapter, setSelectedChapter] = useState<ChapterOutline | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() =>
  {
    const fetchChapters = async () =>
    {
      try
      {
        const data = await chapterOutlinesApi.list(projectId)
        setChapters(data)
        if (data.length > 0)
        {
          setSelectedChapter(data[0])
        }
      }
      catch (err)
      {
        console.error('Failed to fetch chapters:', err)
      }
      finally
      {
        setLoading(false)
      }
    }
    fetchChapters()
  }, [projectId])

  if (loading)
  {
    return <div className="flex items-center justify-center h-full">加载中...</div>
  }

  return (
    <div className="flex h-full">
      {/* 左侧章节列表 */}
      <div className="w-44 border-r bg-white">
        <div className="p-3 border-b flex items-center justify-between">
          <span className="text-sm font-medium">章节列表</span>
          <Button variant="ghost" size="sm">
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        <div className="overflow-auto">
          {chapters.map((chapter) => (
            <button
              key={chapter.id}
              onClick={() => setSelectedChapter(chapter)}
              className={`w-full px-3 py-2 text-left text-sm border-b hover:bg-muted/50 ${
                selectedChapter?.id === chapter.id ? 'bg-primary/10 border-l-2 border-l-primary' : ''
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">{chapter.chapter_number}.</span>
                <span className="truncate">{chapter.title || '未命名'}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* 中间编辑区 */}
      <div className="flex-1 p-6 overflow-auto">
        {selectedChapter ? (
          <div className="max-w-2xl mx-auto space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">第 {selectedChapter.chapter_number} 章</h2>
              <div className="flex gap-2">
                <Button variant="outline" size="sm">
                  <Sparkles className="h-4 w-4 mr-2" />
                  AI 生成
                </Button>
                <Button size="sm">
                  <Save className="h-4 w-4 mr-2" />
                  保存
                </Button>
              </div>
            </div>

            <div>
              <label className="text-sm text-muted-foreground">章节标题</label>
              <Input
                value={selectedChapter.title || ''}
                placeholder="输入章节标题"
                className="mt-1"
              />
            </div>

            <div>
              <label className="text-sm text-muted-foreground">章节摘要</label>
              <Textarea
                value={selectedChapter.summary || ''}
                placeholder="描述本章主要内容"
                rows={4}
                className="mt-1"
              />
            </div>

            <div>
              <label className="text-sm text-muted-foreground">预估字数</label>
              <Input
                type="number"
                value={selectedChapter.estimated_words || 3000}
                className="mt-1 w-32"
              />
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            选择章节查看大纲
          </div>
        )}
      </div>

      {/* 右侧详情面板 */}
      <div className="w-80 border-l bg-white p-4">
        <h3 className="font-medium mb-4">章节详情</h3>
        {selectedChapter ? (
          <div className="space-y-4">
            <Card>
              <CardContent className="pt-4">
                <div className="text-sm">
                  <span className="text-muted-foreground">状态: </span>
                  <span className={selectedChapter.confirmed ? 'text-green-600' : 'text-yellow-600'}>
                    {selectedChapter.confirmed ? '已确认' : '草稿'}
                  </span>
                </div>
              </CardContent>
            </Card>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">选择章节查看详情</p>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 提交章节大纲面板**

```bash
git add frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx
git commit -m "feat(workbench): add ChapterOutlinePanel with three-column layout"
```

---

## Task 9: 写作面板（含合并的AI助手）

**Files:**
- Create: `frontend/src/components/workbench/creation/WritingPanel.tsx`
- Create: `frontend/src/components/workbench/creation/AIAssistantPanel.tsx`

- [ ] **Step 1: 创建 AI 助手面板（含审核功能）**

```tsx
// frontend/src/components/workbench/creation/AIAssistantPanel.tsx

import { useState } from 'react'
import { Sparkles, AlertCircle, CheckCircle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

interface AIAssistantPanelProps
{
  chapterContent?: string
}

export function AIAssistantPanel({ chapterContent }: AIAssistantPanelProps)
{
  const [activeTab, setActiveTab] = useState<'assist' | 'review'>('assist')

  return (
    <div className="w-[350px] border-l bg-white flex flex-col">
      {/* Tab 切换 */}
      <div className="flex border-b">
        <button
          onClick={() => setActiveTab('assist')}
          className={cn(
            'flex-1 px-4 py-2 text-sm font-medium transition-colors',
            activeTab === 'assist'
              ? 'text-primary border-b-2 border-primary'
              : 'text-muted-foreground hover:text-foreground'
          )}
        >
          <Sparkles className="h-4 w-4 inline mr-1" />
          写作辅助
        </button>
        <button
          onClick={() => setActiveTab('review')}
          className={cn(
            'flex-1 px-4 py-2 text-sm font-medium transition-colors',
            activeTab === 'review'
              ? 'text-primary border-b-2 border-primary'
              : 'text-muted-foreground hover:text-foreground'
          )}
        >
          <AlertCircle className="h-4 w-4 inline mr-1" />
          质量检测
        </button>
      </div>

      {/* 内容区 */}
      <div className="flex-1 overflow-auto p-4">
        {activeTab === 'assist' ? (
          <div className="space-y-4">
            {/* 情节建议 */}
            <div className="p-3 bg-muted rounded-md">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium">情节建议</span>
                <Button variant="ghost" size="sm">
                  <RefreshCw className="h-3 w-3" />
                </Button>
              </div>
              <p className="text-sm text-muted-foreground">
                可以在本章加入一个意外转折，让读者对后续情节产生期待...
              </p>
              <Button variant="outline" size="sm" className="mt-2">
                采纳建议
              </Button>
            </div>

            {/* 续写建议 */}
            <div className="p-3 bg-muted rounded-md">
              <span className="text-sm font-medium">续写建议</span>
              <p className="text-sm text-muted-foreground mt-1">
                接下来可以描写主角的内心挣扎...
              </p>
            </div>

            {/* 角色提示 */}
            <div className="p-3 bg-muted rounded-md">
              <span className="text-sm font-medium">角色提示</span>
              <p className="text-sm text-muted-foreground mt-1">
                李星河在第3章表现出勇敢的性格，保持一致性
              </p>
            </div>

            {/* 用户输入 */}
            <div className="pt-2 border-t">
              <Textarea placeholder="向 AI 提问..." rows={2} />
              <Button size="sm" className="mt-2 w-full">
                发送
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {/* 整体评分 */}
            <div className="p-4 bg-muted rounded-md text-center">
              <div className="text-3xl font-bold text-primary">85</div>
              <div className="text-sm text-muted-foreground">整体评分</div>
            </div>

            {/* 分项评分 */}
            <div className="space-y-2">
              {[
                { label: '情节连贯性', score: 90 },
                { label: '人物塑造', score: 85 },
                { label: '文笔表达', score: 80 },
                { label: '节奏把控', score: 88 },
              ].map((item) => (
                <div key={item.label} className="flex items-center gap-2">
                  <span className="text-sm w-20">{item.label}</span>
                  <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-primary rounded-full"
                      style={{ width: `${item.score}%` }}
                    />
                  </div>
                  <span className="text-sm text-muted-foreground w-8">{item.score}</span>
                </div>
              ))}
            </div>

            {/* 问题列表 */}
            <div className="space-y-2">
              <span className="text-sm font-medium">发现问题</span>
              <div className="p-2 bg-yellow-50 border border-yellow-200 rounded text-sm">
                <AlertCircle className="h-4 w-4 inline text-yellow-600 mr-1" />
                <span>第2段情节转折略显突兀</span>
              </div>
            </div>

            {/* 改进建议 */}
            <div className="p-3 bg-muted rounded-md">
              <span className="text-sm font-medium">改进建议</span>
              <p className="text-sm text-muted-foreground mt-1">
                可以增加过渡描写，让情节转折更自然
              </p>
              <div className="flex gap-2 mt-2">
                <Button variant="outline" size="sm">修改</Button>
                <Button variant="ghost" size="sm">忽略</Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 创建写作面板**

```tsx
// frontend/src/components/workbench/creation/WritingPanel.tsx

import { useState, useEffect } from 'react'
import { PenTool, Save, ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { chapterOutlinesApi } from '@/lib/api'
import { AIAssistantPanel } from './AIAssistantPanel'
import type { ChapterOutline } from '@/types'

interface WritingPanelProps
{
  projectId: number
}

export function WritingPanel({ projectId }: WritingPanelProps)
{
  const [chapters, setChapters] = useState<ChapterOutline[]>([])
  const [selectedChapter, setSelectedChapter] = useState<ChapterOutline | null>(null)
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() =>
  {
    const fetchChapters = async () =>
    {
      try
      {
        const data = await chapterOutlinesApi.list(projectId)
        setChapters(data)
        if (data.length > 0)
        {
          setSelectedChapter(data[0])
        }
      }
      catch (err)
      {
        console.error('Failed to fetch chapters:', err)
      }
      finally
      {
        setLoading(false)
      }
    }
    fetchChapters()
  }, [projectId])

  const navigateChapter = (direction: 'prev' | 'next') =>
  {
    if (!selectedChapter) return
    const currentIndex = chapters.findIndex(c => c.id === selectedChapter.id)
    if (direction === 'prev' && currentIndex > 0)
    {
      setSelectedChapter(chapters[currentIndex - 1])
    }
    else if (direction === 'next' && currentIndex < chapters.length - 1)
    {
      setSelectedChapter(chapters[currentIndex + 1])
    }
  }

  if (loading)
  {
    return <div className="flex items-center justify-center h-full">加载中...</div>
  }

  return (
    <div className="flex h-full">
      {/* 左侧章节列表 */}
      <div className="w-44 border-r bg-white">
        <div className="p-3 border-b">
          <span className="text-sm font-medium">章节列表</span>
        </div>
        <div className="overflow-auto">
          {chapters.map((chapter) => (
            <button
              key={chapter.id}
              onClick={() => setSelectedChapter(chapter)}
              className={`w-full px-3 py-2 text-left text-sm border-b hover:bg-muted/50 ${
                selectedChapter?.id === chapter.id ? 'bg-primary/10 border-l-2 border-l-primary' : ''
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">{chapter.chapter_number}.</span>
                <span className="truncate">{chapter.title || '未命名'}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* 中间写作区 */}
      <div className="flex-1 flex flex-col">
        <div className="flex-1 p-6 overflow-auto">
          {selectedChapter ? (
            <div className="max-w-3xl mx-auto">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">{selectedChapter.title || `第 ${selectedChapter.chapter_number} 章`}</h2>
                <Button size="sm">
                  <Save className="h-4 w-4 mr-2" />
                  保存
                </Button>
              </div>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="开始写作..."
                className="w-full h-[calc(100vh-200px)] p-4 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              选择章节开始写作
            </div>
          )}
        </div>

        {/* 底部导航 */}
        <div className="border-t p-3 flex items-center justify-between bg-white">
          <div className="text-sm text-muted-foreground">
            字数: {content.length}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => navigateChapter('prev')}>
              <ChevronLeft className="h-4 w-4 mr-1" />
              上一章
            </Button>
            <Button variant="outline" size="sm" onClick={() => navigateChapter('next')}>
              下一章
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      </div>

      {/* 右侧 AI 助手（含审核功能） */}
      <AIAssistantPanel chapterContent={content} />
    </div>
  )
}
```

- [ ] **Step 3: 提交写作面板**

```bash
git add frontend/src/components/workbench/creation/WritingPanel.tsx frontend/src/components/workbench/creation/AIAssistantPanel.tsx
git commit -m "feat(workbench): add WritingPanel with merged AI assistant"
```

---

## Task 10: 构建和测试

**Files:**
- 无新增文件

- [ ] **Step 1: 构建前端**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no errors

- [ ] **Step 2: 运行测试**

```bash
cd frontend && npm run test:run
```

Expected: All tests pass

- [ ] **Step 3: 重建 Docker 容器**

```bash
docker compose build --no-cache frontend && docker compose up -d frontend
```

Expected: Frontend container starts successfully

- [ ] **Step 4: 提交所有更改**

```bash
git add -A
git commit -m "feat(workbench): complete workbench page redesign"
```

---

## 完成标准

- [ ] 工作台页面可通过 `/project/:id/workbench` 访问
- [ ] Tab 切换正常（规划/创作）
- [ ] 左侧菜单切换正常
- [ ] 各面板渲染正常
- [ ] AI 助手面板 Tab 切换正常（写作辅助/质量检测）
- [ ] 构建无错误
- [ ] 测试通过
