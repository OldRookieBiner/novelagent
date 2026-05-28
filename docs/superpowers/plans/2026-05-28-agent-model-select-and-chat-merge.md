# 智能体模型选择 & 聊天窗口合并 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 合并写作页面两个聊天窗口为统一的 Agent 面板，并为 Agent 添加模型选择功能，同时调整标签页顺序对齐创作流程。

**Architecture:** 前端改动为主。先补齐 agentApi.ts 的事件处理缺陷（impact_assessment/warning），再删除 InspirationChat、增强 AgentChatPanel（模型选择器、阶段感知、重构为 agentApi），调整 TabNavigation 顺序，WritingTab 增加阶段引导卡片。后端无变更。

**Tech Stack:** React 18, TypeScript, Zustand, agentApi.ts (SSE), shadcn/ui

---

## File Structure

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `frontend/src/lib/agentApi.ts` | 补齐 impact_assessment/warning 事件回调 |
| 修改 | `frontend/src/components/workbench/TabNavigation.tsx` | 标签顺序：知识库→结构→写作→追踪 |
| 修改 | `frontend/src/stores/workbenchStore.ts` | 默认 activeTab 改为 knowledge |
| 修改 | `frontend/src/components/workbench/creation/WritingTab.tsx` | 移除 InspirationChat，加阶段引导卡片 |
| 删除 | `frontend/src/components/workbench/creation/InspirationChat.tsx` | 不再需要 |
| 修改 | `frontend/src/components/workbench/creation/index.ts` | 移除 InspirationChat 导出 |
| 修改 | `frontend/src/components/workbench/AgentChatPanel.tsx` | 模型选择器、阶段标签、重构为 agentApi、空状态文案 |
| 不变 | 后端 | 无变更 |

---

### Task 1: 补齐 agentApi.ts 事件处理

**根因：** `sendAgentMessage` 缺少 `impact_assessment` 和 `warning` 两个 SSE 事件类型的处理。当前 AgentChatPanel 直接 fetch 时手动处理了这两个事件，如果直接重构为 agentApi 而不补齐，影响评估和预警功能会丢失。

**Files:**
- Modify: `frontend/src/lib/agentApi.ts`

- [ ] **Step 1: 在 AgentChatCallbacks 接口增加 impact 和 warning 回调**

在 `AgentChatCallbacks` 接口中添加：

```ts
export interface AgentChatCallbacks {
  onAgentText?: (content: string) => void
  onToolStart?: (tool: string, args: Record<string, unknown>) => void
  onToolResult?: (tool: string, result: Record<string, unknown>) => void
  onImpactAssessment?: (data: Record<string, unknown>) => void
  onWarning?: (data: Record<string, unknown>) => void
  onAiUpdate?: (module: string, summary: string) => void
  onChapterPreview?: (data: Record<string, unknown>) => void
  onReview?: (data: Record<string, unknown>) => void
  onAgentDone?: () => void
  onError?: (error: string) => void
}
```

- [ ] **Step 2: 在 sendAgentMessage 的 switch 中添加事件分发**

在 `switch (type)` 块中，`case 'agent_review'` 之后、`case 'agent_done'` 之前，添加：

```ts
        case 'impact_assessment':
          callbacks.onImpactAssessment?.(payload)
          break
        case 'warning':
          callbacks.onWarning?.(payload)
          break
```

- [ ] **Step 3: 验证编译**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/agentApi.ts
git commit -m "fix(frontend): agentApi 补齐 impact_assessment 和 warning 事件处理"
```

---

### Task 2: 标签页重排

**Files:**
- Modify: `frontend/src/components/workbench/TabNavigation.tsx`
- Modify: `frontend/src/stores/workbenchStore.ts`

- [ ] **Step 1: 修改 TabNavigation.tsx 标签顺序**

将 `TABS` 数组顺序从 `writing, knowledge, structure, tracking` 改为 `knowledge, structure, writing, tracking`：

```tsx
const TABS: { key: WorkbenchTab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: 'knowledge', label: '知识库', icon: BookOpen },
  { key: 'structure', label: '结构', icon: GitBranch },
  { key: 'writing', label: '写作', icon: Sparkles },
  { key: 'tracking', label: '追踪', icon: BarChart3 },
]
```

- [ ] **Step 2: 修改 workbenchStore.ts 默认 activeTab**

将 store 中 `activeTab` 默认值从 `'writing'` 改为 `'knowledge'`：

```ts
activeTab: 'knowledge',
```

- [ ] **Step 3: 验证**

启动前端，确认标签顺序为知识库→结构→写作→追踪，默认激活知识库标签。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workbench/TabNavigation.tsx frontend/src/stores/workbenchStore.ts
git commit -m "refactor(frontend): 标签页顺序对齐创作流程 知识库→结构→写作→追踪"
```

---

### Task 3: 删除 InspirationChat，WritingTab 统一渲染

**Files:**
- Delete: `frontend/src/components/workbench/creation/InspirationChat.tsx`
- Modify: `frontend/src/components/workbench/creation/WritingTab.tsx`
- Modify: `frontend/src/components/workbench/creation/index.ts`

- [ ] **Step 1: 修改 index.ts 移除 InspirationChat 导出**

将 `frontend/src/components/workbench/creation/index.ts` 中的 `export { InspirationChat } from './InspirationChat'` 行删除。

修改后：

```ts
export { OutlinePanel } from './OutlinePanel'
export { ChapterOutlinePanel } from './ChapterOutlinePanel'
export { WritingPanel } from './WritingPanel'
export { AIAssistantPanel } from './AIAssistantPanel'
export { WritingTab } from './WritingTab'
export { ChapterNodePanel } from './ChapterNodePanel'
export type { ChapterNode } from './ChapterNodePanel'
```

- [ ] **Step 2: 删除 InspirationChat.tsx**

```bash
rm frontend/src/components/workbench/creation/InspirationChat.tsx
```

- [ ] **Step 3: 重写 WritingTab.tsx**

移除 InspirationChat 引用和孵化阶段分支，添加阶段引导卡片：

```tsx
// WritingTab.tsx — 写作标签页主组件

import { useState } from 'react'
import { Info, X } from 'lucide-react'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { WritingPanel } from './WritingPanel'

interface WritingTabProps {
  projectId: number
}

const PHASE_GUIDANCE: Record<string, { message: string; show: boolean }> = {
  incubation: {
    message: '当前处于创意孵化阶段，请先在右侧智能体中完善知识库，完成后切换到结构设计阶段',
    show: true,
  },
  structure: {
    message: '请完成结构设计后再开始写作，你可以在右侧智能体中讨论情节安排',
    show: true,
  },
  writing: { message: '', show: false },
  revision: { message: '', show: false },
}

export function WritingTab({ projectId }: WritingTabProps) {
  const phase = useWorkbenchStore((s) => s.phase)
  const [dismissed, setDismissed] = useState(false)
  const guidance = PHASE_GUIDANCE[phase]

  return (
    <div className="flex flex-col h-full">
      {guidance.show && !dismissed && (
        <div className="mx-6 mt-4 flex items-start gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-xs text-blue-800">
          <Info className="h-4 w-4 shrink-0 mt-0.5" />
          <span className="flex-1">{guidance.message}</span>
          <button
            onClick={() => setDismissed(true)}
            className="shrink-0 text-blue-400 hover:text-blue-600"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
      <WritingPanel projectId={projectId} />
    </div>
  )
}
```

- [ ] **Step 4: 验证编译**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

确认无类型错误，无 InspirationChat 相关引用报错。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/workbench/creation/
git commit -m "refactor(frontend): 移除 InspirationChat，写作标签统一渲染 WritingPanel + 阶段引导"
```

---

### Task 4: AgentChatPanel 重构 — 使用 agentApi + 模型选择器 + 阶段感知

**Files:**
- Modify: `frontend/src/components/workbench/AgentChatPanel.tsx`

这是最大的改动。将 AgentChatPanel 从直接 fetch 手动解析 SSE 重构为使用 `sendAgentMessage`，并增加模型选择器和阶段感知。

**关键修复点：**
- 通过 agentApi 的 `onImpactAssessment`/`onWarning` 回调维持影响评估和预警功能
- 模型选择器使用 `useEffect` + `mousedown` 事件监听实现 click-outside 关闭
- 组件卸载时清理事件监听，防止内存泄漏

- [ ] **Step 1: 重写 AgentChatPanel.tsx**

```tsx
// AgentChatPanel.tsx — Right panel: AI creation agent chat

import { useState, useRef, useEffect, useCallback } from 'react'
import { PanelRightClose, PanelRightOpen, Send, AlertTriangle, ShieldCheck, ChevronDown } from 'lucide-react'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { sendAgentMessage } from '@/lib/agentApi'
import { modelConfigsApi } from '@/lib/api'
import type { AiMessage, ImpactReport, AgentWarning } from '@/stores/workbenchStore'
import type { ModelConfig } from '@/types'

const PHASE_LABELS: Record<string, string> = {
  incubation: '创意孵化',
  structure: '结构设计',
  writing: '写作中',
  revision: '修订中',
}

const PHASE_EMPTY_HINTS: Record<string, string> = {
  incubation: '描述你的小说创意，智能体将帮你完善世界观、角色和风格',
  structure: '和智能体讨论情节安排和结构设计',
  writing: '和智能体讨论你的创作想法',
  revision: '和智能体讨论修订方向',
}

interface ModelOption {
  id: number
  name: string
  isDefault: boolean
}

export function AgentChatPanel() {
  const {
    currentProjectId,
    aiSidebarOpen,
    toggleAiSidebar,
    aiMessages,
    addAiMessage,
    pendingImpacts,
    addPendingImpact,
    removePendingImpact,
    agentWarnings,
    addAgentWarning,
    isAgentSending,
    setIsAgentSending,
  } = useWorkbenchStore()

  const phase = useWorkbenchStore((s) => s.phase)

  const [input, setInput] = useState('')
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([])
  const [selectedModelId, setSelectedModelId] = useState<number | null>(null)
  const [modelSelectorOpen, setModelSelectorOpen] = useState(false)
  const [modelsLoaded, setModelsLoaded] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const modelSelectorRef = useRef<HTMLDivElement>(null)

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [aiMessages, pendingImpacts])

  // 加载模型配置列表（仅一次）
  useEffect(() => {
    if (modelsLoaded) return
    modelConfigsApi.list().then((res) => {
      const enabled = res.models
        .filter((m: ModelConfig) => m.is_enabled)
        .map((m: ModelConfig) => ({
          id: m.id,
          name: m.name,
          isDefault: m.is_default,
        }))
      setModelOptions(enabled)
      const defaultModel = enabled.find((m: ModelOption) => m.isDefault)
      if (defaultModel) {
        setSelectedModelId(defaultModel.id)
      }
      setModelsLoaded(true)
    }).catch(() => {
      setModelsLoaded(true)
    })
  }, [modelsLoaded])

  // 模型选择器 click-outside 关闭
  useEffect(() => {
    if (!modelSelectorOpen) return
    const handleClickOutside = (e: MouseEvent) => {
      if (modelSelectorRef.current && !modelSelectorRef.current.contains(e.target as Node)) {
        setModelSelectorOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [modelSelectorOpen])

  // SSE chat handler — 使用 agentApi
  const handleSend = useCallback(async () => {
    if (!input.trim() || !currentProjectId || isAgentSending) return

    const userMsg: AiMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
      segments: [],
      timestamp: Date.now(),
    }
    addAiMessage(userMsg)
    const messageText = input.trim()
    setInput('')
    setIsAgentSending(true)

    const assistantMsg: AiMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      segments: [],
      timestamp: Date.now(),
    }
    addAiMessage(assistantMsg)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      await sendAgentMessage(
        currentProjectId,
        messageText,
        {
          onAgentText: (content) => {
            assistantMsg.content += content
          },
          onToolStart: (tool, args) => {
            assistantMsg.segments.push({
              type: 'tool_start' as any,
              content: `调用 ${tool}...`,
              data: { tool, args },
            })
          },
          onToolResult: (tool, result) => {
            assistantMsg.segments.push({
              type: 'tool_result' as any,
              content: `${tool} 完成`,
              data: { tool, result },
            })
          },
          onImpactAssessment: (data) => {
            addPendingImpact(data as ImpactReport)
          },
          onWarning: (data) => {
            addAgentWarning(data as AgentWarning)
          },
          onAgentDone: () => {},
          onError: (error) => {
            assistantMsg.content = assistantMsg.content || `错误：${error}`
          },
        },
        {
          modelConfigId: selectedModelId ?? undefined,
          signal: controller.signal,
        }
      )
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        assistantMsg.content = assistantMsg.content || `连接错误：${err.message}`
      }
    } finally {
      setIsAgentSending(false)
      abortRef.current = null
    }
  }, [input, currentProjectId, isAgentSending, selectedModelId, addAiMessage, addPendingImpact, addAgentWarning, setIsAgentSending])

  const handleImpactDecision = async (changeId: number, decision: string) => {
    if (!currentProjectId) return

    try {
      const res = await fetch(`/api/projects/${currentProjectId}/agent/impact-decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ change_id: changeId, decision }),
      })

      if (res.ok) {
        removePendingImpact(changeId)
      }
    } catch {
      // 静默失败
    }
  }

  // 折叠状态
  if (!aiSidebarOpen) {
    return (
      <div className="w-10 bg-white border-l border-gray-200 flex flex-col items-center pt-3 gap-2">
        <button
          onClick={toggleAiSidebar}
          className="p-1.5 text-gray-400 hover:text-gray-600 transition-colors"
          title="展开智能体"
        >
          <PanelRightOpen className="h-4 w-4" />
        </button>
        {agentWarnings.length > 0 && (
          <div className="relative">
            <AlertTriangle className="h-3 w-3 text-amber-500" />
            <span className="absolute -top-1 -right-1 w-2 h-2 bg-amber-500 rounded-full" />
          </div>
        )}
        <span className="text-gray-400 text-[10px]" style={{ writingMode: 'vertical-lr' }}>
          智能体
        </span>
      </div>
    )
  }

  const selectedModelName = selectedModelId
    ? modelOptions.find(m => m.id === selectedModelId)?.name
    : '默认模型'

  return (
    <div className="w-[300px] bg-white border-l border-gray-200 flex flex-col flex-shrink-0">
      {/* Header */}
      <div className="px-3 py-2.5 border-b border-gray-100 flex items-center gap-2">
        <span>✦ 智能体</span>
        <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
          {PHASE_LABELS[phase] || '未知'}
        </span>
        <div className={`w-1.5 h-1.5 rounded-full ml-auto ${isAgentSending ? 'bg-amber-500 animate-pulse' : 'bg-green-500'}`} />
        <button
          onClick={toggleAiSidebar}
          className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
        >
          <PanelRightClose className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* 模型选择器 */}
      <div className="px-3 py-1.5 border-b border-gray-50" ref={modelSelectorRef}>
        <div className="relative">
          <button
            onClick={() => setModelSelectorOpen(!modelSelectorOpen)}
            className="w-full flex items-center justify-between gap-1 rounded border border-gray-200 px-2 py-1 text-[10px] text-foreground hover:border-gray-300 transition-colors"
          >
            <span className="truncate">{selectedModelName}</span>
            <ChevronDown className="h-3 w-3 shrink-0 text-gray-400" />
          </button>
          {modelSelectorOpen && (
            <div className="absolute left-0 right-0 top-full mt-0.5 bg-white border border-gray-200 rounded shadow-sm z-10 max-h-40 overflow-y-auto">
              <button
                onClick={() => { setSelectedModelId(null); setModelSelectorOpen(false) }}
                className={cn(
                  'w-full text-left px-2 py-1.5 text-[10px] hover:bg-muted/50',
                  !selectedModelId && 'text-primary font-medium'
                )}
              >
                默认模型
              </button>
              {modelOptions.map(m => (
                <button
                  key={m.id}
                  onClick={() => { setSelectedModelId(m.id); setModelSelectorOpen(false) }}
                  className={cn(
                    'w-full text-left px-2 py-1.5 text-[10px] hover:bg-muted/50',
                    selectedModelId === m.id && 'text-primary font-medium'
                  )}
                >
                  {m.name}
                  {m.isDefault && <span className="ml-1 text-muted-foreground">(默认)</span>}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Warnings */}
      {agentWarnings.length > 0 && (
        <div className="px-3 py-1.5 bg-amber-50 border-b border-amber-100">
          {agentWarnings.slice(-2).map((w, i) => (
            <div key={i} className="flex items-start gap-1.5 text-[10px] text-amber-700 mb-1">
              <AlertTriangle className="h-3 w-3 shrink-0 mt-0.5" />
              <span>{w.message}</span>
            </div>
          ))}
        </div>
      )}

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
        {aiMessages.length === 0 && (
          <div className="text-center text-muted-foreground text-xs py-8">
            {PHASE_EMPTY_HINTS[phase] || '和智能体讨论你的创作想法'}
          </div>
        )}
        {aiMessages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              'rounded-lg px-3 py-2 text-[11px] leading-relaxed',
              msg.role === 'assistant'
                ? 'bg-primary/5 text-foreground'
                : 'bg-primary text-primary-foreground ml-10'
            )}
          >
            {msg.content || (msg.role === 'assistant' && isAgentSending ? '...' : '')}
            {msg.segments.filter(s => s.type === 'tool_result').map((s, i) => (
              <div key={i} className="mt-1 text-[10px] text-muted-foreground border-t border-gray-100 pt-1">
                {s.content}
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Impact Assessment Cards */}
      {pendingImpacts.length > 0 && (
        <div className="px-3 py-2 border-t border-gray-100 space-y-2">
          {pendingImpacts.map((report) => (
            <div key={report.change_id} className="bg-gray-50 rounded-lg p-2 text-[10px]">
              <div className="flex items-center gap-1.5 mb-1">
                <ShieldCheck className="h-3 w-3 text-gray-500" />
                <span className="font-medium">影响评估</span>
                <span className={cn(
                  'px-1.5 py-0.5 rounded text-[9px] font-medium',
                  report.impact_level === 'severe' ? 'bg-red-100 text-red-700' :
                  report.impact_level === 'moderate' ? 'bg-orange-100 text-orange-700' :
                  report.impact_level === 'minor' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-green-100 text-green-700'
                )}>
                  {report.impact_label}
                </span>
              </div>
              <div className="text-muted-foreground mb-1.5">
                影响 {report.affected_chapters} 章 / {report.affected_paragraphs} 段
              </div>
              {report.detail && (
                <div className="text-muted-foreground mb-1.5 text-[9px]">{report.detail}</div>
              )}
              <div className="flex gap-1.5">
                <button
                  onClick={() => handleImpactDecision(report.change_id, 'proceed')}
                  className="px-2 py-1 bg-primary text-primary-foreground rounded text-[9px]"
                >
                  按原方案修改
                </button>
                <button
                  onClick={() => handleImpactDecision(report.change_id, 'abandon')}
                  className="px-2 py-1 bg-gray-200 text-gray-700 rounded text-[9px]"
                >
                  放弃
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="px-3 py-2 border-t border-gray-100">
        <div className="flex gap-1.5">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            className="flex-1 border border-gray-200 rounded-md px-2.5 py-1.5 text-[11px] outline-none focus:border-primary"
            placeholder={isAgentSending ? '思考中...' : '输入消息...'}
            disabled={isAgentSending}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isAgentSending}
            className="bg-primary text-primary-foreground border-none px-2.5 py-1.5 rounded-md text-[11px] disabled:opacity-50"
          >
            <Send className="h-3 w-3" />
          </button>
        </div>
      </div>
    </div>
  )
}

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(' ')
}
```

- [ ] **Step 2: 验证编译**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

确认无类型错误。

- [ ] **Step 3: 验证功能**

启动前端，确认：
- AgentChatPanel 顶部显示阶段标签
- 模型选择器下拉正常，可选择不同模型
- 点击选择器外部区域自动关闭下拉
- 发送消息时 model_config_id 正确传递
- 空状态文案按阶段变化
- 影响评估卡片正常显示
- 预警消息正常显示

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workbench/AgentChatPanel.tsx
git commit -m "feat(frontend): AgentChatPanel 增加模型选择器、阶段标签，重构为 agentApi"
```

---

## Self-Review

**1. Spec coverage:**
- 标签页重排 ✅ Task 2
- 写作标签阶段引导 ✅ Task 3
- 删除 InspirationChat ✅ Task 3
- AgentChatPanel 模型选择器 ✅ Task 4
- AgentChatPanel 阶段标签 ✅ Task 4
- AgentChatPanel 空状态文案 ✅ Task 4
- AgentChatPanel 重构为 agentApi ✅ Task 4
- agentApi 补齐事件处理 ✅ Task 1（新增，修复根因缺陷）

**2. Placeholder scan:** 无 TBD/TODO/模糊描述。

**3. Type consistency:**
- `ModelConfig` 类型来自 `@/types` ✅
- `sendAgentMessage` 接口来自 `@/lib/agentApi` ✅
- `AiMessage`/`ImpactReport`/`AgentWarning` 来自 workbenchStore ✅
- `onImpactAssessment`/`onWarning` 回调在 Task 1 中定义，Task 4 中使用 ✅
- `modelConfigsApi.list()` 返回 `ModelConfigListResponse`（含 `models: ModelConfig[]`）✅

**4. 根因修复确认：**
- agentApi.ts 缺失事件处理 → Task 1 在源头补齐，而非在 AgentChatPanel 中 workaround ✅
- 模型选择器 click-outside → useEffect + mousedown 监听 + 组件卸载清理 ✅
- InspirationChat 删除 → index.ts 导出同步清理 ✅
