# AI 搭档模式 + 工作台重构 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构工作台标签结构、新增常驻 AI 搭档侧栏、实现后端 Agent 模式

**Architecture:** 前端改为左工作区+右 AI 侧栏布局，灵感独立标签页，规划更名设定。后端基于 LangGraph `create_react_agent` 构建全流程 Agent，将现有节点能力封装为 tools。双模式并存，共享数据模型和数据库。

**Tech Stack:** React 18 / Zustand / Tailwind / LangGraph 1.2 / FastAPI / @dnd-kit

---

## 文件结构总览

### 新增文件

| 文件 | 职责 |
|------|------|
| `frontend/src/components/workbench/AICompanionSidebar.tsx` | AI 搭档侧栏容器（header + 聊天区 + 输入区 + 折叠） |
| `frontend/src/components/workbench/AICompanionChat.tsx` | 聊天消息列表渲染 |
| `frontend/src/components/workbench/AICompanionInput.tsx` | 输入框 + 发送按钮 |
| `frontend/src/components/workbench/AIActionCard.tsx` | Agent 操作步骤卡片（✓/⏳ 状态） |
| `frontend/src/lib/agentApi.ts` | Agent API 客户端（SSE 流式） |
| `backend/app/agents/agent_state.py` | Agent State 定义 |
| `backend/app/agents/agent_graph.py` | Agent 图构建（ReAct） |
| `backend/app/agents/agent_tools.py` | Agent tools 定义（读写各模块） |
| `backend/app/api/agent.py` | Agent API 路由 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `frontend/src/types/workbench.ts` | Tab 类型 + 菜单类型更名 |
| `frontend/src/stores/workbenchStore.ts` | 新增 AI 侧栏状态，Tab/菜单类型更新 |
| `frontend/src/components/workbench/TabNavigation.tsx` | 4 个标签 |
| `frontend/src/components/workbench/WorkbenchSidebar.tsx` | 仅设定标签显示，菜单项更新 |
| `frontend/src/components/workbench/WorkbenchLayout.tsx` | 增加右侧 AI 侧栏 |
| `frontend/src/pages/ProjectWorkbench.tsx` | 路由分发逻辑更新 |
| `frontend/src/components/workbench/creation/OutlinePanel.tsx` | 双栏布局 + 移除 AI 分析 + 拖拽 |
| `frontend/src/components/workbench/planning/InspirationPanel.tsx` | 适配全宽布局 |
| `backend/app/agents/sse_events.py` | 新增 Agent SSE 事件格式化函数 |
| `backend/app/main.py` | 注册 Agent 路由 |

---

## Phase 1: 前端布局重构

### Task 1: 更新类型定义和 Store

**Files:**
- Modify: `frontend/src/types/workbench.ts`
- Modify: `frontend/src/stores/workbenchStore.ts`

- [ ] **Step 1: 更新 workbench.ts 类型**

```typescript
// frontend/src/types/workbench.ts

/** 工作台 Tab 类型 */
export type WorkbenchTab = 'inspiration' | 'settings' | 'chapter_outlines' | 'writing'

/** 设定功能菜单项 */
export type SettingsMenuItem = 'outline' | 'characters' | 'relations'

/** 所有菜单项 */
export type MenuItem = SettingsMenuItem

/** 菜单配置 */
export interface MenuConfig {
  key: MenuItem
  label: string
  icon: string
}

/** 设定菜单配置 */
export const SETTINGS_MENUS: MenuConfig[] = [
  { key: 'outline', label: '大纲', icon: 'FileText' },
  { key: 'characters', label: '人物', icon: 'Users' },
  { key: 'relations', label: '关系', icon: 'Link' },
]
```

- [ ] **Step 2: 更新 workbenchStore.ts**

主要改动：
- `WorkbenchTab` 类型自动跟随 types 变更
- `activeTab` 默认值改为 `'inspiration'`
- `setActiveTab` 中 `'planning'` 改为 `'settings'`，切换到设定时重置菜单为 `'outline'`
- `activeMenuItem` 默认值改为 `'outline'`
- 新增 AI 侧栏状态：`aiSidebarOpen`、`toggleAiSidebar`、`aiMessages`、`addAiMessage`、`clearAiMessages`

```typescript
// 新增到 WorkbenchState 接口
  // AI 侧栏状态
  aiSidebarOpen: boolean
  toggleAiSidebar: () => void
  aiMessages: AiMessage[]
  addAiMessage: (message: AiMessage) => void
  clearAiMessages: () => void

// 新增 AiMessage 类型（文件顶部）
export interface AiMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  actions?: AiAction[]
  timestamp: number
}

export interface AiAction {
  tool: string
  status: 'running' | 'done' | 'error'
  description: string
}
```

initialState 新增：
```typescript
  aiSidebarOpen: true,
  aiMessages: [],
```

- [ ] **Step 3: 验证编译通过**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -30`

此时会有其他文件引用旧类型报错，这是预期的，后续 Task 修复。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/workbench.ts frontend/src/stores/workbenchStore.ts
git commit -m "refactor(frontend): update tab/menu types for inspiration+settings split"
```

---

### Task 2: 更新 TabNavigation 和 WorkbenchSidebar

**Files:**
- Modify: `frontend/src/components/workbench/TabNavigation.tsx`
- Modify: `frontend/src/components/workbench/WorkbenchSidebar.tsx`

- [ ] **Step 1: 更新 TabNavigation.tsx**

将 TABS 数组改为 4 个标签，灵感用 `Sparkles` 图标，设定用 `Settings` 图标：

```typescript
import { Sparkles, Settings, BookOpen, PenTool } from 'lucide-react'

const TABS = [
  { key: 'inspiration' as const, label: '灵感', icon: Sparkles },
  { key: 'settings' as const, label: '设定', icon: Settings },
  { key: 'chapter_outlines' as const, label: '章节大纲', icon: BookOpen },
  { key: 'writing' as const, label: '章节正文', icon: PenTool },
]
```

其余代码不变。

- [ ] **Step 2: 更新 WorkbenchSidebar.tsx**

改动：
- `activeTab !== 'planning'` 改为 `activeTab !== 'settings'`
- 引用 `SETTINGS_MENUS` 替代 `PLANNING_MENUS`
- 移除 `Lightbulb` 图标导入（灵感不再在侧边栏中）

```typescript
import { Users, Link, FileText, BookOpen, PenTool, ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { SETTINGS_MENUS } from '@/types/workbench'

// ... ICON_MAP 不变 ...

export function WorkbenchSidebar()
{
  const { activeTab, activeMenuItem, setActiveMenuItem, sidebarCollapsed, toggleSidebar } = useWorkbenchStore()

  // 仅在设定 Tab 显示侧边栏菜单
  if (activeTab !== 'settings')
  {
    return null
  }

  const menus = SETTINGS_MENUS
  // ... 其余渲染逻辑不变 ...
}
```

- [ ] **Step 3: 验证编译通过**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -30`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workbench/TabNavigation.tsx frontend/src/components/workbench/WorkbenchSidebar.tsx
git commit -m "refactor(frontend): update tab navigation and sidebar for new tab structure"
```

---

### Task 3: 更新 ProjectWorkbench 路由分发

**Files:**
- Modify: `frontend/src/pages/ProjectWorkbench.tsx`

- [ ] **Step 1: 更新 renderContent 逻辑**

将 `case 'planning'` 改为 `case 'settings'`，移除 `inspiration` 子菜单项，灵感面板移到独立标签：

```typescript
const renderContent = () =>
{
  switch (activeTab)
  {
    // 灵感 Tab：全宽展示灵感面板
    case 'inspiration':
      return <InspirationPanel projectId={projectId!} hasOutline={!!outline?.title} onPlanningComplete={refreshOutline} />

    // 章节大纲和章节正文是独立 Tab
    case 'chapter_outlines':
      return <ChapterOutlinePanel projectId={projectId!} />
    case 'writing':
      return <WritingPanel projectId={projectId!} />

    // 设定 Tab 按侧边栏菜单项渲染
    case 'settings':
      switch (activeMenuItem)
      {
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
```

- [ ] **Step 2: 验证编译和页面渲染**

Run: `cd frontend && npx tsc --noEmit`

浏览器访问 http://localhost:3001 验证：
- 4 个标签显示正确
- 灵感标签页全宽展示灵感面板
- 设定标签页显示侧边栏（大纲/人物/关系）
- 章节大纲和章节正文标签正常

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ProjectWorkbench.tsx
git commit -m "refactor(frontend): update workbench routing for inspiration+settings split"
```

---

### Task 4: 创建 AI 搭档侧栏 UI（壳，无后端连接）

**Files:**
- Create: `frontend/src/components/workbench/AICompanionSidebar.tsx`
- Create: `frontend/src/components/workbench/AICompanionChat.tsx`
- Create: `frontend/src/components/workbench/AICompanionInput.tsx`
- Create: `frontend/src/components/workbench/AIActionCard.tsx`

- [ ] **Step 1: 创建 AIActionCard.tsx**

展示 Agent 操作步骤的小卡片，含工具名、描述、状态图标：

```tsx
// frontend/src/components/workbench/AIActionCard.tsx

import { Check, Loader2, X } from 'lucide-react'
import type { AiAction } from '@/stores/workbenchStore'

interface AIActionCardProps
{
  actions: AiAction[]
}

export function AIActionCard({ actions }: AIActionCardProps)
{
  if (actions.length === 0) return null

  return (
    <div className="space-y-1.5 my-2">
      {actions.map((action, i) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          {action.status === 'done' && <Check className="h-3 w-3 text-green-400" />}
          {action.status === 'running' && <Loader2 className="h-3 w-3 text-blue-400 animate-spin" />}
          {action.status === 'error' && <X className="h-3 w-3 text-red-400" />}
          <span className={action.status === 'running' ? 'text-blue-300' : 'text-slate-400'}>
            {action.description}
          </span>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: 创建 AICompanionChat.tsx**

聊天消息列表，AI 左对齐、用户右对齐：

```tsx
// frontend/src/components/workbench/AICompanionChat.tsx

import { useEffect, useRef } from 'react'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { AIActionCard } from './AIActionCard'

export function AICompanionChat()
{
  const messages = useWorkbenchStore((s) => s.aiMessages)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() =>
  {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex-1 overflow-auto p-3 space-y-3">
      {messages.length === 0 && (
        <div className="flex flex-col items-center justify-center h-full gap-2 text-center">
          <div className="text-2xl">🤖</div>
          <p className="text-xs text-slate-500 leading-relaxed">
            我是你的 AI 编剧搭档<br />
            跟我说说你对小说的想法<br />
            我会帮你修改大纲、角色、章节...
          </p>
        </div>
      )}
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          <div
            className={`max-w-[85%] rounded-lg px-3 py-2 text-xs leading-relaxed ${
              msg.role === 'user'
                ? 'bg-blue-900/50 text-blue-200'
                : 'bg-emerald-900/40 text-emerald-200'
            }`}
          >
            {msg.content}
            {msg.actions && msg.actions.length > 0 && <AIActionCard actions={msg.actions} />}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
```

- [ ] **Step 3: 创建 AICompanionInput.tsx**

输入框 + 发送按钮：

```tsx
// frontend/src/components/workbench/AICompanionInput.tsx

import { useState } from 'react'
import { Send } from 'lucide-react'

interface AICompanionInputProps
{
  onSend: (message: string) => void
  disabled?: boolean
}

export function AICompanionInput({ onSend, disabled }: AICompanionInputProps)
{
  const [input, setInput] = useState('')

  const handleSubmit = (e: React.FormEvent) =>
  {
    e.preventDefault()
    const trimmed = input.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setInput('')
  }

  return (
    <form onSubmit={handleSubmit} className="border-t border-slate-700 p-2">
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="说说你的想法..."
          disabled={disabled}
          className="flex-1 bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={disabled || !input.trim()}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:hover:bg-blue-600 text-white px-3 py-2 rounded-md text-xs transition-colors"
        >
          <Send className="h-3.5 w-3.5" />
        </button>
      </div>
    </form>
  )
}
```

- [ ] **Step 4: 创建 AICompanionSidebar.tsx**

整合 header + 聊天区 + 输入区 + 折叠状态：

```tsx
// frontend/src/components/workbench/AICompanionSidebar.tsx

import { PanelRightClose, PanelRightOpen } from 'lucide-react'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { AICompanionChat } from './AICompanionChat'
import { AICompanionInput } from './AICompanionInput'

export function AICompanionSidebar()
{
  const { aiSidebarOpen, toggleAiSidebar, addAiMessage } = useWorkbenchStore()

  // 折叠状态
  if (!aiSidebarOpen)
  {
    return (
      <div className="w-10 bg-slate-950 border-l border-slate-800 flex flex-col items-center pt-3 gap-2">
        <button
          onClick={toggleAiSidebar}
          className="p-1.5 text-slate-500 hover:text-slate-300 transition-colors"
          title="展开 AI 搭档"
        >
          <PanelRightOpen className="h-4 w-4" />
        </button>
        <span className="text-slate-600 text-[10px] writing-vertical"
          style={{ writingMode: 'vertical-lr' }}
        >
          AI 搭档
        </span>
      </div>
    )
  }

  const handleSend = (message: string) =>
  {
    // MVP 阶段：仅添加用户消息到本地，后端连接在 Phase 3 实现
    addAiMessage({
      id: crypto.randomUUID(),
      role: 'user',
      content: message,
      timestamp: Date.now(),
    })
    // 临时 AI 回复（占位，Phase 3 替换为真实 API 调用）
    setTimeout(() =>
    {
      addAiMessage({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: '收到！我正在思考如何帮你优化小说...',
        timestamp: Date.now(),
      })
    }, 500)
  }

  return (
    <div className="w-[340px] bg-slate-950 border-l border-slate-800 flex flex-col shrink-0">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-200">🤖 AI 搭档</span>
          <span className="text-[9px] px-1.5 py-0.5 bg-green-500/20 text-green-400 rounded">在线</span>
        </div>
        <button
          onClick={toggleAiSidebar}
          className="p-1 text-slate-500 hover:text-slate-300 transition-colors"
          title="折叠 AI 搭档"
        >
          <PanelRightClose className="h-4 w-4" />
        </button>
      </div>

      {/* 聊天区 */}
      <AICompanionChat />

      {/* 输入区 */}
      <AICompanionInput onSend={handleSend} />
    </div>
  )
}
```

- [ ] **Step 5: 验证编译通过**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -20`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/workbench/AICompanionSidebar.tsx frontend/src/components/workbench/AICompanionChat.tsx frontend/src/components/workbench/AICompanionInput.tsx frontend/src/components/workbench/AIActionCard.tsx
git commit -m "feat(frontend): add AI companion sidebar UI shell"
```

---

### Task 5: 将 AI 侧栏集成到 WorkbenchLayout

**Files:**
- Modify: `frontend/src/components/workbench/WorkbenchLayout.tsx`

- [ ] **Step 1: 修改 WorkbenchLayout.tsx**

在主内容区右侧添加 AI 侧栏：

```tsx
// 在 import 区域添加
import { AICompanionSidebar } from './AICompanionSidebar'

// 修改主内容区 div
// 原：
//   <div className="flex flex-1 overflow-hidden">
//     <WorkbenchSidebar />
//     <main className="flex-1 overflow-auto">{children}</main>
//   </div>
// 改为：
      <div className="flex flex-1 overflow-hidden">
        <WorkbenchSidebar />
        <main className="flex-1 overflow-auto">
          {children}
        </main>
        <AICompanionSidebar />
      </div>
```

- [ ] **Step 2: 验证页面布局**

浏览器访问 http://localhost:3001 验证：
- 右侧出现 AI 侧栏（深色背景）
- 折叠/展开按钮正常工作
- 切换标签页时 AI 侧栏不消失
- 设定标签页下三栏并存（设定侧边栏 + 主内容 + AI 侧栏）

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workbench/WorkbenchLayout.tsx
git commit -m "feat(frontend): integrate AI companion sidebar into workbench layout"
```

---

### Task 6: 重构 OutlinePanel（双栏 + 移除 AI 分析 + 拖拽）

**Files:**
- Modify: `frontend/src/components/workbench/creation/OutlinePanel.tsx`

- [ ] **Step 1: 安装 @dnd-kit 依赖**

Run: `cd frontend && npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities`

- [ ] **Step 2: 重构 OutlinePanel**

主要改动：
1. 移除右侧 AI 分析面板相关代码（`handleAnalyze`、`analysisResult`、`aiPanelCollapsed`、`rightCollapsed`、`acceptAnalysis`、整个右侧 div）
2. 移除 `max-w-3xl` 限制，改为双栏 flex 布局
3. 左栏：基本信息卡片（标题、章节数、概述）+ 确认按钮
4. 右栏：情节节点列表，使用 `@dnd-kit/sortable` 实现拖拽排序
5. 新增空状态

关键代码结构：

```tsx
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors } from '@dnd-kit/core'
import { SortableContext, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical } from 'lucide-react'

// 可排序情节节点组件
function SortablePlotPoint({ id, index, value, onChange, onRemove })
{
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id })
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  return (
    <div ref={setNodeRef} style={style} className="flex gap-2 items-center">
      <button {...attributes} {...listeners} className="cursor-grab text-muted-foreground hover:text-foreground">
        <GripVertical className="h-4 w-4" />
      </button>
      <span className="w-7 h-7 flex items-center justify-center bg-muted rounded text-xs text-muted-foreground shrink-0">
        {index + 1}
      </span>
      <Input value={value} onChange={(e) => onChange(e.target.value)} className="flex-1" />
      <Button variant="ghost" size="sm" onClick={onRemove} className="shrink-0">
        <X className="h-3.5 w-3.5" />
      </Button>
    </div>
  )
}

// 主组件 render 部分
return (
  <div className="flex h-full flex-col md:flex-row">
    {/* 左栏：基本信息 */}
    <div className="flex-1 min-w-0 p-6 overflow-auto md:border-r">
      <div className="max-w-2xl mx-auto space-y-5">
        {/* 标题栏 */}
        {/* 基本信息卡片 */}
        {/* 内容概述卡片 */}
        {/* 确认按钮 */}
      </div>
    </div>

    {/* 右栏：情节节点 */}
    <div className="flex-1 min-w-0 p-6 overflow-auto">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          <span className="text-emerald-500">📍</span> 情节节点 ({plotPoints.length})
        </h3>
        <Button variant="outline" size="sm" onClick={addPlotPoint}>
          <Plus className="h-3.5 w-3.5 mr-1" /> 添加
        </Button>
      </div>

      {plotPoints.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <p className="text-sm">暂无情节节点</p>
          <p className="text-xs mt-1">点击「添加」或在右侧 AI 搭档中描述你的故事</p>
        </div>
      ) : (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={plotPoints.map((_, i) => `plot-${i}`)} strategy={verticalListSortingStrategy}>
            <div className="space-y-2">
              {plotPoints.map((point, index) => (
                <SortablePlotPoint
                  key={`plot-${index}`}
                  id={`plot-${index}`}
                  index={index}
                  value={point}
                  onChange={(v) => updatePlotPoint(index, v)}
                  onRemove={() => removePlotPoint(index)}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}
    </div>
  </div>
)
```

拖拽结束处理函数：

```typescript
const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))

const handleDragEnd = (event: any) =>
{
  const { active, over } = event
  if (!over || active.id === over.id) return

  const oldIndex = parseInt(active.id.replace('plot-', ''))
  const newIndex = parseInt(over.id.replace('plot-', ''))
  const updated = [...plotPoints]
  const [moved] = updated.splice(oldIndex, 1)
  updated.splice(newIndex, 0, moved)
  setPlotPoints(updated)
}
```

- [ ] **Step 3: 验证大纲页面布局**

浏览器访问设定 → 大纲标签，验证：
- 双栏布局正确显示
- 情节节点可拖拽排序
- 右侧 AI 分析面板已移除
- 空状态文案正确显示
- 保存和确认按钮正常工作

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workbench/creation/OutlinePanel.tsx frontend/package.json frontend/package-lock.json
git commit -m "refactor(frontend): outline panel dual-column layout with drag-sort, remove AI analysis panel"
```

---

### Task 7: 适配 InspirationPanel 全宽布局

**Files:**
- Modify: `frontend/src/components/workbench/planning/InspirationPanel.tsx`

- [ ] **Step 1: 调整 InspirationPanel 布局**

InspirationPanel 现在是独立标签页，不再受设定侧边栏挤压，需要：
- 移除可能存在的固定宽度限制
- 确保聊天模式和表单模式在全宽下表现正常
- 由于不再有侧边栏空间，右侧预览区域可适当加宽

检查文件中是否有硬编码宽度或 `max-w-*` 限制，根据实际情况调整。主要关注：
- 聊天模式：左侧聊天 + 右侧预览的 flex 比例
- 表单模式：左侧表单 + 右侧创作提示的布局

- [ ] **Step 2: 验证灵感页面**

浏览器访问灵感标签页，验证：
- 全宽展示正常
- 聊天模式和表单模式切换正常
- 右侧预览/提示区正常

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workbench/planning/InspirationPanel.tsx
git commit -m "refactor(frontend): adapt inspiration panel for full-width tab layout"
```

---

## Phase 2: 后端 Agent 模式

### Task 8: 定义 AgentState（内嵌于 agent_graph.py）

> 注意：`create_react_agent` 使用内置的 messages state，不支持自定义 state_schema。
> 因此不单独创建 agent_state.py 文件，避免产生无用代码。
> 项目上下文通过 system message 注入，不依赖 state 字段。

此 Task 省略，上下文注入逻辑在 Task 10 的 `build_project_context` 中实现。

从新增文件列表中移除 `backend/app/agents/agent_state.py`。

---

### Task 9: 创建 Agent Tools（编号不变，Task 8 已省略）

**Files:**
- Create: `backend/app/agents/agent_tools.py`

- [ ] **Step 1: 创建 agent_tools.py**

将现有 API 能力封装为 LangChain Tool 对象。每个 tool 接收 `project_id` 和必要参数，通过数据库直接读写：

```python
# backend/app/agents/agent_tools.py

"""AI 搭档 Agent 的工具集"""

from langchain_core.tools import tool
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.outline import Outline, ChapterOutline
from app.models.character import Character


def _get_db() -> Session:
    """获取数据库 Session，确保调用方负责关闭"""
    return SessionLocal()


@tool
def read_outline(project_id: int) -> dict:
    """读取项目的大纲信息，包括标题、概述、情节节点、确认状态"""
    db = _get_db()
    try:
        outline = db.query(Outline).filter(Outline.project_id == project_id).first()
        if not outline:
            return {"error": "大纲不存在"}
        return {
            "title": outline.title,
            "summary": outline.summary,
            "plot_points": outline.plot_points,
            "chapter_count_suggested": outline.chapter_count_suggested,
            "confirmed": outline.confirmed,
        }
    finally:
        db.close()


@tool
def update_outline(project_id: int, title: str = None, summary: str = None, plot_points: list = None) -> dict:
    """修改项目的大纲。可以修改标题、概述或情节节点，只传需要修改的字段"""
    db = _get_db()
    try:
        outline = db.query(Outline).filter(Outline.project_id == project_id).first()
        if not outline:
            return {"error": "大纲不存在"}
        if title is not None:
            outline.title = title
        if summary is not None:
            outline.summary = summary
        if plot_points is not None:
            outline.plot_points = plot_points
        db.commit()
        return {"success": True, "message": "大纲已更新"}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@tool
def read_characters(project_id: int) -> list:
    """读取项目的所有角色信息"""
    db = _get_db()
    try:
        characters = db.query(Character).filter(Character.project_id == project_id).all()
        return [
            {
                "id": c.id,
                "name": c.name,
                "role": c.role,
                "personality": c.personality,
                "core_motivation": c.core_motivation,
                "growth_arc": c.growth_arc,
            }
            for c in characters
        ]
    finally:
        db.close()


@tool
def update_character(project_id: int, character_id: int, name: str = None, role: str = None, personality: str = None, core_motivation: str = None, growth_arc: str = None) -> dict:
    """修改指定角色的信息。只传需要修改的字段"""
    db = _get_db()
    try:
        character = db.query(Character).filter(
            Character.id == character_id,
            Character.project_id == project_id
        ).first()
        if not character:
            return {"error": "角色不存在"}
        if name is not None:
            character.name = name
        if role is not None:
            character.role = role
        if personality is not None:
            character.personality = personality
        if core_motivation is not None:
            character.core_motivation = core_motivation
        if growth_arc is not None:
            character.growth_arc = growth_arc
        db.commit()
        return {"success": True, "message": f"角色「{character.name}」已更新"}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@tool
def create_character(project_id: int, name: str, role: str, personality: str = "", core_motivation: str = "") -> dict:
    """为项目新增一个角色"""
    db = _get_db()
    try:
        character = Character(
            project_id=project_id,
            name=name,
            role=role,
            personality=personality,
            core_motivation=core_motivation,
        )
        db.add(character)
        db.commit()
        return {"success": True, "message": f"角色「{name}」已创建", "id": character.id}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@tool
def read_chapter_outlines(project_id: int) -> list:
    """读取项目的所有章节大纲"""
    db = _get_db()
    try:
        outlines = db.query(ChapterOutline).filter(ChapterOutline.project_id == project_id).order_by(ChapterOutline.chapter_number).all()
        return [
            {
                "id": co.id,
                "chapter_number": co.chapter_number,
                "title": co.title,
                "plot": co.plot,
                "confirmed": co.confirmed,
            }
            for co in outlines
        ]
    finally:
        db.close()


@tool
def update_chapter_outline(project_id: int, chapter_outline_id: int, title: str = None, plot: str = None) -> dict:
    """修改指定章节的大纲。只传需要修改的字段"""
    db = _get_db()
    try:
        outline = db.query(ChapterOutline).filter(
            ChapterOutline.id == chapter_outline_id,
            ChapterOutline.project_id == project_id
        ).first()
        if not outline:
            return {"error": "章节大纲不存在"}
        if title is not None:
            outline.title = title
        if plot is not None:
            outline.plot = plot
        db.commit()
        return {"success": True, "message": f"第{outline.chapter_number}章大纲已更新"}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


# 所有 tools 列表，供 agent_graph.py 使用
AGENT_TOOLS = [
    read_outline,
    update_outline,
    read_characters,
    update_character,
    create_character,
    read_chapter_outlines,
    update_chapter_outline,
]
```

注意：`generate_chapter_content`、`review_chapter`、`rewrite_chapter`、`read_relations`、`update_relations` 这些 tools 涉及 LLM 调用或较复杂的数据操作，在 MVP 阶段暂不实现，后续迭代补充。

- [ ] **Step 2: 验证导入正常**

Run: `docker exec novelagent-backend-1 python3 -c "from app.agents.agent_tools import AGENT_TOOLS; print(len(AGENT_TOOLS), 'tools loaded')"`

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/agent_tools.py
git commit -m "feat(backend): add agent tools for reading/writing outline, characters, chapters"
```

---

### Task 10: 创建 Agent 图

**Files:**
- Create: `backend/app/agents/agent_graph.py`

- [ ] **Step 1: 创建 agent_graph.py**

使用 LangGraph `create_react_agent` 构建 ReAct 循环：

```python
# backend/app/agents/agent_graph.py

"""AI 搭档 Agent 图定义"""

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

from app.agents.agent_tools import AGENT_TOOLS
from app.services.llm import get_llm_service_from_config
from app.models.model_config import ModelConfig
from app.models.outline import Outline, ChapterOutline
from app.models.character import Character
from app.database import SessionLocal
from app.utils.logger import logger


def build_project_context(project_id: int) -> dict:
    """构建项目上下文，注入 Agent system message"""
    db = SessionLocal()
    try:
        outline = db.query(Outline).filter(Outline.project_id == project_id).first()
        characters = db.query(Character).filter(Character.project_id == project_id).all()
        chapter_outlines = db.query(ChapterOutline).filter(ChapterOutline.project_id == project_id).order_by(ChapterOutline.chapter_number).all()

        return {
            "outline": {
                "title": outline.title if outline else None,
                "summary": outline.summary[:200] if outline and outline.summary else None,
                "confirmed": outline.confirmed if outline else False,
                "plot_points_count": len(outline.plot_points) if outline and outline.plot_points else 0,
            },
            "characters": [
                {"name": c.name, "role": c.role}
                for c in characters[:10]
            ],
            "chapter_outlines": {
                "total": len(chapter_outlines),
                "titles": [f"第{co.chapter_number}章: {co.title}" for co in chapter_outlines[:10]],
            },
        }
    finally:
        db.close()


def _get_llm_from_service(llm_service) -> ChatOpenAI:
    """将 LLMService 转换为 LangChain ChatOpenAI 兼容对象

    复用 LLMService 的 api_key/base_url/model 配置，
    保留 provider 级别的连接信息，但 tool calling 走 LangChain 协议。
    注意：这里不使用 LLMService 的 chat/chat_stream 方法，
    因为 create_react_agent 内部管理 LLM 调用。
    """
    return ChatOpenAI(
        model=llm_service.model,
        api_key=llm_service.api_key,
        base_url=llm_service.base_url,
        temperature=0.7,
    )


def create_agent_graph(model_config_id: int = None, user_id: int = None):
    """创建 Agent 图实例"""
    llm = None

    if model_config_id and user_id:
        db = SessionLocal()
        try:
            config = db.query(ModelConfig).filter(ModelConfig.id == model_config_id).first()
            if config:
                llm_service = get_llm_service_from_config(config, user_id)
                llm = _get_llm_from_service(llm_service)
        except Exception as e:
            logger.warning(f"Failed to get LLM from model config: {e}")
        finally:
            db.close()

    # 如果模型配置获取失败，尝试用户默认设置
    if llm is None and user_id:
        db = SessionLocal()
        try:
            from app.models.settings import UserSettings
            from app.services.llm import get_llm_service
            settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
            if settings:
                llm_service = get_llm_service(settings)
                llm = _get_llm_from_service(llm_service)
        except Exception as e:
            logger.warning(f"Failed to get LLM from user settings: {e}")
        finally:
            db.close()

    if llm is None:
        raise ValueError("无法获取 LLM 配置：请先在设置中配置 API Key")

    graph = create_react_agent(
        model=llm,
        tools=AGENT_TOOLS,
    )
    return graph
```

- [ ] **Step 2: 验证 Agent 图可创建**

Run: `docker exec novelagent-backend-1 python3 -c "from app.agents.agent_graph import create_agent_graph; g = create_agent_graph(); print('Agent graph created:', type(g))"`

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/agent_graph.py
git commit -m "feat(backend): add agent graph with create_react_agent"
```

---

### Task 11: 新增 Agent SSE 事件格式化

**Files:**
- Modify: `backend/app/agents/sse_events.py`

- [ ] **Step 1: 添加 Agent 相关 SSE 事件格式化函数**

在文件末尾添加：

```python
# --- Agent SSE 事件 ---

def format_agent_text(content: str) -> str:
    """格式化 Agent 文本回复流式 chunk"""
    return f"event: agent_text\ndata: {json.dumps({'content': content})}\n\n"


def format_agent_tool_start(tool_name: str, args: dict) -> str:
    """格式化 Agent tool 调用开始事件"""
    return f"event: agent_tool_start\ndata: {json.dumps({'tool': tool_name, 'args': args})}\n\n"


def format_agent_tool_result(tool_name: str, result: dict) -> str:
    """格式化 Agent tool 调用结果事件"""
    return f"event: agent_tool_result\ndata: {json.dumps({'tool': tool_name, 'result': result})}\n\n"


def format_agent_done() -> str:
    """格式化 Agent 本轮完成事件"""
    return f"event: agent_done\ndata: {json.dumps({'message': 'Agent 思考完成'})}\n\n"


def format_ai_update(module: str, summary: str) -> str:
    """格式化 AI 更新通知（前端用于标记「🤖 AI 已更新」）"""
    return f"event: ai_update\ndata: {json.dumps({'module': module, 'summary': summary})}\n\n"
```

- [ ] **Step 2: 验证导入正常**

Run: `docker exec novelagent-backend-1 python3 -c "from app.agents.sse_events import format_agent_text, format_agent_tool_start, format_agent_done; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/sse_events.py
git commit -m "feat(backend): add agent SSE event formatters"
```

---

### Task 12: 创建 Agent API 端点

**Files:**
- Create: `backend/app/api/agent.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 创建 agent.py API 路由**

```python
# backend/app/api/agent.py

"""AI 搭档 Agent API 路由"""

import json
import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.auth import get_current_user
from app.utils.project import get_project_for_user
from app.models.user import User
from app.models.project import Project
from app.agents.agent_graph import create_agent_graph, build_project_context
from app.agents.sse_events import (
    format_agent_text,
    format_agent_tool_start,
    format_agent_tool_result,
    format_agent_done,
    format_ai_update,
    format_error_message,
    format_heartbeat,
)
from app.utils.logger import logger


router = APIRouter()


class AgentChatRequest(BaseModel):
    """Agent 聊天请求"""
    message: str
    model_config_id: Optional[int] = None
    active_tab: Optional[str] = None
    active_menu_item: Optional[str] = None
    # 多轮对话：前端传入历史消息（MVP 阶段由前端管理）
    history: Optional[list[dict]] = None


async def stream_agent_events(graph, messages: list, project_id: int):
    """流式输出 Agent 事件"""
    try:
        async for event in graph.astream_events(
            {"messages": messages},
            config={"configurable": {"thread_id": f"agent-{project_id}"}},
            version="v2",
        ):
            kind = event.get("event", "")

            # LLM 文本输出
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and chunk.content and isinstance(chunk.content, str):
                    yield format_agent_text(chunk.content)

            # Tool 调用开始
            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                tool_input = event.get("data", {}).get("input", {})
                yield format_agent_tool_start(tool_name, tool_input)

            # Tool 调用结束
            elif kind == "on_tool_end":
                tool_name = event.get("name", "")
                tool_output = event.get("data", {}).get("output", {})
                # 判断是否是写操作，发送 ai_update 通知
                write_tools = {"update_outline", "update_character", "create_character", "update_chapter_outline"}
                if tool_name in write_tools:
                    module_map = {
                        "update_outline": "outline",
                        "update_character": "characters",
                        "create_character": "characters",
                        "update_chapter_outline": "chapter_outlines",
                    }
                    module = module_map.get(tool_name, "unknown")
                    yield format_ai_update(module, f"{tool_name} 执行完成")
                # 序列化 tool output
                output_str = json.dumps(tool_output, ensure_ascii=False) if isinstance(tool_output, dict) else str(tool_output)
                yield format_agent_tool_result(tool_name, {"output": output_str[:500]})

        yield format_agent_done()

    except Exception as e:
        logger.error(f"Agent stream error: {e}")
        yield format_error_message(str(e))


@router.post("/{project_id}/agent/chat")
async def agent_chat(
    project_id: int,
    req: AgentChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """与 AI 搭档对话（SSE 流式）"""
    # 验证项目归属
    project = get_project_for_user(project_id, current_user.id, db)

    # 构建项目上下文
    context = build_project_context(project_id)

    # 构建 system message
    system_content = f"""你是一位专业的小说创作搭档。你可以帮助用户修改大纲、角色设定、章节大纲等。

当前项目上下文：
- 大纲：{json.dumps(context.get('outline', {}), ensure_ascii=False)}
- 角色：{json.dumps(context.get('characters', []), ensure_ascii=False)}
- 章节大纲：{json.dumps(context.get('chapter_outlines', {}), ensure_ascii=False)}
- 用户当前查看：{req.active_tab or '未知'}{f' / {req.active_menu_item}' if req.active_menu_item else ''}

请根据用户的需求，调用相应的工具来修改项目内容。修改后简要说明你做了什么。"""

    # 构建消息列表（包含历史）
    messages = [{"role": "system", "content": system_content}]
    if req.history:
        messages.extend(req.history)
    messages.append({"role": "user", "content": req.message})

    # 创建 Agent 图
    graph = create_agent_graph(
        model_config_id=req.model_config_id,
        user_id=current_user.id,
    )

    return StreamingResponse(
        stream_agent_events(graph, messages, project_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 2: 注册路由到 main.py**

在 `backend/app/main.py` 添加：

```python
# 在 import 区域添加
from app.api import agent

# 在 include_router 区域添加（workflow 路由后面）
app.include_router(agent.router, prefix="/api/projects", tags=["agent"])
```

- [ ] **Step 3: 重建后端并验证 API 可达**

Run: `docker compose build --no-cache backend && docker compose up -d backend`

Run: `docker exec novelagent-backend-1 python3 -c "from app.api.agent import router; print('Agent router OK')"`

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/agent.py backend/app/main.py
git commit -m "feat(backend): add agent chat API endpoint with SSE streaming"
```

---

## Phase 3: 前端 Agent 集成

### Task 13: 创建 agentApi.ts 并连接 AI 侧栏

**Files:**
- Create: `frontend/src/lib/agentApi.ts`
- Modify: `frontend/src/components/workbench/AICompanionSidebar.tsx`

- [ ] **Step 1: 创建 agentApi.ts**

```typescript
// frontend/src/lib/agentApi.ts

import { API_BASE_URL } from './api'
import { parseSSEData, parseSSEEventBlock } from './sseParser'

export interface AgentChatCallbacks {
  onAgentText?: (content: string) => void
  onToolStart?: (tool: string, args: Record<string, unknown>) => void
  onToolResult?: (tool: string, result: Record<string, unknown>) => void
  onAiUpdate?: (module: string, summary: string) => void
  onAgentDone?: () => void
  onError?: (error: string) => void
}

export async function sendAgentMessage(
  projectId: number,
  message: string,
  callbacks: AgentChatCallbacks,
  options?: {
    modelConfigId?: number
    activeTab?: string
    activeMenuItem?: string
    history?: Array<{ role: string; content: string }>
    signal?: AbortSignal
  }
): Promise<void> {
  const token = localStorage.getItem('token')
  const response = await fetch(`${API_BASE_URL}/projects/${projectId}/agent/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({
      message,
      model_config_id: options?.modelConfigId,
      active_tab: options?.activeTab,
      active_menu_item: options?.activeMenuItem,
      history: options?.history,
    }),
    signal: options?.signal,
  })

  if (!response.ok) {
    const err = await response.text()
    callbacks.onError?.(err)
    return
  }

  const reader = response.body?.getReader()
  if (!reader) return

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    // 按空行分割 SSE 事件块
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() || ''

    for (const block of blocks) {
      if (!block.trim()) continue
      const event = parseSSEEventBlock(block)
      if (!event?.event || !event.data) continue

      try {
        const data = parseSSEData(event.data)
        switch (event.event) {
          case 'agent_text':
            callbacks.onAgentText?.(data.content)
            break
          case 'agent_tool_start':
            callbacks.onToolStart?.(data.tool, data.args)
            break
          case 'agent_tool_result':
            callbacks.onToolResult?.(data.tool, data.result)
            break
          case 'ai_update':
            callbacks.onAiUpdate?.(data.module, data.summary)
            break
          case 'agent_done':
            callbacks.onAgentDone?.()
            break
          case 'error':
            callbacks.onError?.(data.error)
            break
        }
      } catch { /* ignore parse errors */ }
    }
  }
}
```

- [ ] **Step 2: 更新 AICompanionSidebar.tsx 连接真实 API**

替换 Task 4 中的临时 `handleSend` 函数：

import { useState, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { PanelRightClose, PanelRightOpen } from 'lucide-react'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { AICompanionChat } from './AICompanionChat'
import { AICompanionInput } from './AICompanionInput'
import { sendAgentMessage } from '@/lib/agentApi'

export function AICompanionSidebar()
{
  const { id } = useParams()
  const projectId = parseInt(id || '0')
  const { aiSidebarOpen, toggleAiSidebar, addAiMessage } = useWorkbenchStore()
  const [sending, setSending] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  // 跟踪当前 AI 消息的 action 计数，解决同名 tool 多次调用的匹配问题
  const actionIndexRef = useRef(0)

  // 折叠状态
  if (!aiSidebarOpen)
  {
    return (
      <div className="w-10 bg-slate-950 border-l border-slate-800 flex flex-col items-center pt-3 gap-2">
        <button onClick={toggleAiSidebar} className="p-1.5 text-slate-500 hover:text-slate-300 transition-colors" title="展开 AI 搭档">
          <PanelRightOpen className="h-4 w-4" />
        </button>
        <span className="text-slate-600 text-[10px]" style={{ writingMode: 'vertical-lr' }}>AI 搭档</span>
      </div>
    )
  }

  const handleSend = async (message: string) =>
  {
    // 添加用户消息
    addAiMessage({
      id: crypto.randomUUID(),
      role: 'user',
      content: message,
      timestamp: Date.now(),
    })

    // 创建 AI 消息占位
    const assistantId = crypto.randomUUID()
    actionIndexRef.current = 0
    addAiMessage({
      id: assistantId,
      role: 'assistant',
      content: '',
      actions: [],
      timestamp: Date.now(),
    })

    setSending(true)
    const controller = new AbortController()
    abortRef.current = controller

    const { activeTab, activeMenuItem, aiMessages } = useWorkbenchStore.getState()

    // 构建历史消息（最近 10 轮，排除当前占位消息）
    const history = aiMessages
      .filter((m) => m.id !== assistantId)
      .slice(-20)
      .map((m) => ({ role: m.role, content: m.content }))

    try
    {
      await sendAgentMessage(projectId, message, {
        onAgentText: (content) =>
        {
          useWorkbenchStore.setState((state) => ({
            aiMessages: state.aiMessages.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + content } : m
            ),
          }))
        },
        onToolStart: (tool, args) =>
        {
          const desc = _toolDescription(tool, args)
          const idx = actionIndexRef.current++
          useWorkbenchStore.setState((state) => ({
            aiMessages: state.aiMessages.map((m) =>
              m.id === assistantId
                ? { ...m, actions: [...(m.actions || []), { tool, idx, status: 'running' as const, description: desc }] }
                : m
            ),
          }))
        },
        onToolResult: (tool, result) =>
        {
          // 用 idx 匹配最新的同名 tool 调用，而非 a.tool === tool
          useWorkbenchStore.setState((state) =>
          {
            const msg = state.aiMessages.find((m) => m.id === assistantId)
            if (!msg?.actions) return state
            // 找到该 tool 最后一个 running 的 action
            const actionIdx = [...msg.actions].reverse().findIndex(
              (a) => a.tool === tool && a.status === 'running'
            )
            if (actionIdx === -1) return state
            const realIdx = msg.actions.length - 1 - actionIdx
            return {
              aiMessages: state.aiMessages.map((m) =>
                m.id === assistantId
                  ? { ...m, actions: m.actions?.map((a, i) => i === realIdx ? { ...a, status: 'done' as const } : a) }
                  : m
              ),
            }
          })
        },
        onAiUpdate: (module) =>
        {
          useWorkbenchStore.getState().addAiUpdateMarker(module)
          setTimeout(() =>
          {
            useWorkbenchStore.getState().clearAiUpdateMarker(module)
          }, 5 * 60 * 1000)
        },
        onAgentDone: () =>
        {
          setSending(false)
        },
        onError: (error) =>
        {
          useWorkbenchStore.setState((state) => ({
            aiMessages: state.aiMessages.map((m) =>
              m.id === assistantId ? { ...m, content: m.content || `出错：${error}` } : m
            ),
          }))
          setSending(false)
        },
      }, {
        activeTab,
        activeMenuItem,
        history,
        signal: controller.signal,
      })
    }
    catch (e)
    {
      setSending(false)
    }
  }

  return (
    <div className="w-[340px] bg-slate-950 border-l border-slate-800 flex flex-col shrink-0">
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-200">🤖 AI 搭档</span>
          <span className="text-[9px] px-1.5 py-0.5 bg-green-500/20 text-green-400 rounded">在线</span>
        </div>
        <button onClick={toggleAiSidebar} className="p-1 text-slate-500 hover:text-slate-300 transition-colors" title="折叠 AI 搭档">
          <PanelRightClose className="h-4 w-4" />
        </button>
      </div>
      <AICompanionChat />
      <AICompanionInput onSend={handleSend} disabled={sending} />
    </div>
  )
}

/** 生成 tool 操作的可读描述 */
function _toolDescription(tool: string, args: Record<string, unknown>): string
{
  const map: Record<string, (args: Record<string, unknown>) => string> = {
    read_outline: () => '读取大纲',
    update_outline: () => '修改大纲',
    read_characters: () => '读取角色',
    update_character: (a) => `修改角色「${a.name || ''}」`,
    create_character: (a) => `新增角色「${a.name || ''}」`,
    read_chapter_outlines: () => '读取章节大纲',
    update_chapter_outline: (a) => `修改章节大纲`,
  }
  return (map[tool] || (() => tool))(args)
}
```

- [ ] **Step 3: 验证端到端流程**

（不再需要修改 WorkbenchLayout 传递 projectId — AICompanionSidebar 已通过 useParams 获取）

1. 浏览器打开 http://localhost:3001
2. 进入任意项目工作台
3. 在右侧 AI 侧栏输入消息
4. 验证：用户消息显示 → AI 回复流式显示 → tool 操作卡片显示状态 → 完成标记

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/agentApi.ts frontend/src/components/workbench/AICompanionSidebar.tsx
git commit -m "feat(frontend): connect AI companion sidebar to backend agent API"
```

> 注意：onAiUpdate 逻辑已在 AICompanionSidebar 的 handleSend 中实现（设置 marker + 5 分钟自动清除），不需要在 Task 14 重复添加。

---

### Task 14: 前端接收 ai_update 事件标记

> 注意：aiUpdateMarkers 状态和 addAiUpdateMarker/clearAiUpdateMarker 已在 Task 1 的 store 更新中添加。
> onAiUpdate 回调中的 marker 设置 + 5 分钟自动清除已在 Task 13 的 AICompanionSidebar 中实现。
> 本 Task 只需在各面板中**显示**标记。

**Files:**
- Modify: `frontend/src/components/workbench/creation/OutlinePanel.tsx`
- Modify: `frontend/src/components/workbench/planning/CharacterPanel.tsx`

- [ ] **Step 1: 在 OutlinePanel 中显示 AI 更新标记**

在大纲页面顶部标题栏旁，当 `aiUpdateMarkers.outline` 存在时显示标记：

```tsx
import { useWorkbenchStore } from '@/stores/workbenchStore'

// 组件内部
const aiUpdateMarkers = useWorkbenchStore((s) => s.aiUpdateMarkers)
const outlineUpdated = !!aiUpdateMarkers.outline

// 在标题区域添加
{outlineUpdated && (
  <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 border border-blue-200 animate-pulse">
    🤖 AI 已更新
  </span>
)}
```

- [ ] **Step 2: 在 CharacterPanel 中显示 AI 更新标记**

类似 OutlinePanel，当 `aiUpdateMarkers.characters` 存在时显示标记。

- [ ] **Step 3: 验证 AI 更新标记**

1. 在 AI 侧栏发送消息触发大纲修改
2. 切换到设定 → 大纲标签
3. 看到标题旁「🤖 AI 已更新」标记
4. 5 分钟后标记消失

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workbench/creation/OutlinePanel.tsx frontend/src/components/workbench/planning/CharacterPanel.tsx
git commit -m "feat(frontend): add AI update markers for outline and character panels"
```

---

## Phase 4: 集成验证

### Task 15: 端到端测试和修复

- [ ] **Step 1: 完整流程测试**

浏览器中执行以下测试：

1. 首页 → 进入项目 → 验证 4 个标签页
2. 灵感标签 → 聊天模式正常 → 表单模式正常
3. 设定标签 → 侧边栏 3 项 → 大纲双栏 + 拖拽 → 人物 → 关系
4. 章节大纲标签 → 正常
5. 章节正文标签 → 正常
6. AI 侧栏 → 折叠/展开 → 发送消息 → AI 回复 → tool 操作卡片
7. AI 修改后 → 切换到设定标签 → 看到更新标记

- [ ] **Step 2: 修复发现的问题**

根据测试结果修复 bug。

- [ ] **Step 3: Commit 所有修复**

```bash
git add -A
git commit -m "fix: integration test fixes"
```
