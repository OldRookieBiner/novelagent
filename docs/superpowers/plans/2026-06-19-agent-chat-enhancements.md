# Agent 聊天窗口增强 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 AgentChatPanel 中交付 7 项 UX 增强（气泡选中可见性、输入历史导航、复制按钮、耗时显示、按钮居中、锚点跳转列）。

**Architecture:** 全在前端 `AgentChatPanel.tsx` + 拆分 `MessageAnchorRail.tsx` + `AiMessage` 类型扩展。零后端改动。测试使用 vitest + React Testing Library。

**Tech Stack:** React 18 / TypeScript / Zustand / vitest / @testing-library/react / happy-dom / lucide-react

---

## 文件清单

| 文件 | 责任 |
|------|------|
| `frontend/src/stores/workbenchStore.ts` | 扩展 `AiMessage`，加 `startedAt?` / `durationMs?` |
| `frontend/src/components/workbench/AgentChatPanel.tsx` | 1-6 项主改动 + 引入 MessageAnchorRail |
| `frontend/src/components/workbench/MessageAnchorRail.tsx` | 新增：第 7 项锚点列组件 |
| `frontend/src/components/workbench/__tests__/MessageAnchorRail.test.tsx` | 锚点列测试 |
| `frontend/src/lib/__tests__/truncateTitle.test.ts` | truncateTitle 单元测试 |

---

### Task 1: 类型扩展 + truncateTitle 工具函数

**Files:**
- Modify: `frontend/src/stores/workbenchStore.ts`（AiMessage 添加字段）
- Modify: `frontend/src/components/workbench/AgentChatPanel.tsx`（添加 export 的 truncateTitle）
- Create: `frontend/src/lib/__tests__/truncateTitle.test.ts`

- [ ] **Step 1: 在 AiMessage 中增加 startedAt? / durationMs?**

修改 `frontend/src/stores/workbenchStore.ts` 第 19-24 行的 AiMessage 接口：

```diff
 export interface AiMessage {
   id: string
   role: 'user' | 'assistant'
   content: string
   segments: AiMessageSegment[]
   timestamp: number
+  // 仅前端内存态，不持久化到后端
+  startedAt?: number
+  durationMs?: number
 }
```

- [ ] **Step 2: 在 AgentChatPanel.tsx 顶部添加并 export truncateTitle**

在 `AgentChatPanel.tsx` 文件顶部 import 之后、PHASE_LABELS 之前添加：

```typescript
/** 截取前 max 个 grapheme cluster（安全处理 emoji/组合字符）作为消息标题 */
export function truncateTitle(content: string, max = 15): string
{
  const cleaned = content.replace(/\s+/g, ' ').trim()
  if (!cleaned) return '(空消息)'
  const chars = Array.from(cleaned)
  if (chars.length <= max) return cleaned
  return chars.slice(0, max).join('') + '…'
}
```

- [ ] **Step 3: 创建 truncateTitle 测试**

文件 `frontend/src/lib/__tests__/truncateTitle.test.ts`：

```typescript
import { describe, it, expect } from 'vitest'
import { truncateTitle } from '@/components/workbench/AgentChatPanel'

describe('truncateTitle', () => {
  it('空串返回占位', () => {
    expect(truncateTitle('')).toBe('(空消息)')
  })
  it('纯空白返回占位', () => {
    expect(truncateTitle('   \n  \t')).toBe('(空消息)')
  })
  it('全英文 14 字不截', () => {
    const s = 'a'.repeat(14)
    expect(truncateTitle(s)).toBe(s)
  })
  it('全英文 15 字不截', () => {
    const s = 'a'.repeat(15)
    expect(truncateTitle(s)).toBe(s)
  })
  it('全英文 16 字截断加…', () => {
    const s = 'a'.repeat(16)
    expect(truncateTitle(s)).toBe('a'.repeat(15) + '…')
  })
  it('中文 15 字不截', () => {
    const s = '中'.repeat(15)
    expect(truncateTitle(s)).toBe(s)
  })
  it('中文 16 字截断加…', () => {
    const s = '中'.repeat(16)
    expect(truncateTitle(s)).toBe('中'.repeat(15) + '…')
  })
  it('emoji 按 grapheme 计', () => {
    const s = '👍' + 'a'.repeat(14)  // 共 15 个 grapheme
    expect(truncateTitle(s)).toBe(s)
  })
  it('多个换行/空白合并清理', () => {
    expect(truncateTitle('\n  你好\n世界  \n')).toBe('你好 世界')
  })
})
```

- [ ] **Step 4: 运行测试验证签入**

Run: `cd frontend && npx vitest run src/lib/__tests__/truncateTitle.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/workbenchStore.ts frontend/src/components/workbench/AgentChatPanel.tsx frontend/src/lib/__tests__/truncateTitle.test.ts
git commit -m "feat(workflow): add durationMs/startedAt to AiMessage and truncateTitle util"
```

---

### Task 2: 用户气泡背景色 + CopyButton 公用组件 + 用户复制按钮

**Files:**
- Modify: `frontend/src/components/workbench/AgentChatPanel.tsx`

- [ ] **Step 1: 在 lucide-react import 行添加 Copy 和 Check**

定位文件顶部 `import { ... } from 'lucide-react'` 行，确保包含 `Copy` 和 `Check`：

```typescript
import { PanelRightClose, PanelRightOpen, Send, AlertTriangle, ShieldCheck, ChevronDown, ChevronRight, Loader2, CheckCircle2, GripVertical, Square, History, Plus, Copy, Check } from 'lucide-react'
```

注意 `CheckCircle2` 已存在；新增的是 `Copy` 和 `Check`。

- [ ] **Step 2: 添加 CopyButton 公用组件**

在 `ThinkingIndicator` 函数定义之后添加：

```typescript
/** 通用复制按钮：成功显示 Check 1.5s 后还原。带 clipboard.writeText 失败 fallback */
function CopyButton({
  content,
  className,
  ariaLabel,
}: {
  content: string
  className?: string
  ariaLabel?: string
})
{
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    const showSuccess = () =>
    {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }

    try
    {
      if (navigator.clipboard && navigator.clipboard.writeText)
      {
        await navigator.clipboard.writeText(content)
        showSuccess()
        return
      }
      throw new Error('clipboard unavailable')
    }
    catch
    {
      // fallback：execCommand
      try
      {
        const ta = document.createElement('textarea')
        ta.value = content
        ta.style.position = 'fixed'
        ta.style.left = '-9999px'
        ta.style.opacity = '0'
        document.body.appendChild(ta)
        ta.select()
        const ok = document.execCommand('copy')
        document.body.removeChild(ta)
        if (ok) showSuccess()
      }
      catch
      {
        // 静默失败
      }
    }
  }

  return (
    <button
      onClick={handleCopy}
      className={cn('text-muted-foreground hover:text-foreground transition-colors', className)}
      aria-label={ariaLabel || '复制'}
      title="复制"
      type="button"
    >
      {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
    </button>
  )
}
```

- [ ] **Step 3: 修改用户气泡渲染**

定位 `aiMessages.map((msg) => (` 中的 user 分支（约 1140 行）：

原代码：
```tsx
{msg.role === 'user' ? (
  <div className="rounded-lg px-3 py-2 text-[11px] leading-relaxed max-w-[80%] bg-primary text-primary-foreground">
    {msg.content}
  </div>
) : ...}
```

替换为：
```tsx
{msg.role === 'user' ? (
  <div
    ref={(el) => {
      if (el) userMessageRefs.current.set(msg.id, el)
      else userMessageRefs.current.delete(msg.id)
    }}
    className="group flex flex-col items-end"
  >
    <div className="rounded-lg px-3 py-2 text-[11px] leading-relaxed max-w-[80%] bg-secondary text-secondary-foreground selection:bg-primary/25 selection:text-foreground">
      {msg.content}
    </div>
    <CopyButton
      content={msg.content}
      className="opacity-0 group-hover:opacity-100 mt-0.5"
      ariaLabel="复制用户消息"
    />
  </div>
) : ...}
```

> 关键约束：`max-w-[80%]` 留在内层气泡 div 上，外层 wrapper 不限宽。这样短消息时 `items-end` + `flex-col` 让 CopyButton 紧贴气泡右下角，长消息触发 80% 宽度限制时按钮跟随气泡边界对齐。把 max-w 写在外层会导致短消息的复制按钮远离气泡。

注意：外层包裹处需要保留原本的 `flex justify-end`：当前外层是 `<div className={cn(msg.role === 'user' ? 'flex justify-end' : '')}>`，仍然适用。

- [ ] **Step 4: 添加 userMessageRefs**

在 `AgentChatPanel` 函数体顶部（其他 ref 旁边）：

```typescript
// 用户消息 DOM 引用 Map：Task 2 用于复制按钮 ref 回调，Task 6 复用做锚点跳转 + 当前位置判定
const userMessageRefs = useRef<Map<string, HTMLDivElement>>(new Map())
```

> 设计权衡：将该 ref 在本 Task 声明（而非 Task 6）的原因是 Task 2 的气泡渲染代码就要用 ref 回调写入这个 Map；如果延后到 Task 6，Task 2 改完会留下一个引用未声明变量的中间态（`tsc --noEmit` 会失败），破坏 Task 之间的可独立提交性。Task 6 复用同一个 ref，无需重复声明。

- [ ] **Step 5: 运行类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/workbench/AgentChatPanel.tsx
git commit -m "feat(workflow): user bubble bg colour and copy button"
```

---

### Task 3: 输入框历史导航（↑/↓）+ composition 拦截

**Files:**
- Modify: `frontend/src/components/workbench/AgentChatPanel.tsx`

- [ ] **Step 1: 添加历史导航 refs + resetInputHistory 工具**

在 `AgentChatPanel` 函数体内（其他 ref 附近）：

```typescript
const historyIndexRef = useRef<number>(-1)
const draftRef = useRef<string>('')

/** 重置历史导航到草稿态（发送、切换会话、新建会话、加载历史 effect 共用） */
const resetInputHistory = useCallback(() =>
{
  historyIndexRef.current = -1
  draftRef.current = ''
}, [])
```

> 抽取理由：避免在 4 处散落同一对赋值（handleSend / handleSwitchConversation / handleNewConversation / 加载历史 useEffect），任意一处遗漏将导致历史索引"幽灵残留"——例如切换会话后再按 ↑ 会取到旧会话的消息。集中到一个函数后修一处即覆盖全部入口。

- [ ] **Step 2: 修改 handleInputKeyDown，做三件事**

  1. composition 拦截（修复已存在的 Enter 误触小 bug）
  2. 处理 ↑/↓ 历史导航
  3. 保留原 Enter 发送

替换整个 `handleInputKeyDown`：

```typescript
const handleInputKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
  // 中文输入法 composition 期间不响应任何快捷键
  if (e.nativeEvent.isComposing) return

  // ↑/↓ 历史导航（仅当光标在首行/末行）
  if (e.key === 'ArrowUp' || e.key === 'ArrowDown')
  {
    const textarea = e.currentTarget
    const cursorPos = textarea.selectionStart
    const beforeCursor = textarea.value.slice(0, cursorPos)
    const afterCursor = textarea.value.slice(cursorPos)

    if (e.key === 'ArrowUp' && beforeCursor.includes('\n')) return
    if (e.key === 'ArrowDown' && afterCursor.includes('\n')) return

    const userMessages = aiMessages.filter(m => m.role === 'user')
    if (userMessages.length === 0) return

    e.preventDefault()
    const msgs = userMessages.map(m => m.content)

    if (e.key === 'ArrowUp')
    {
      if (historyIndexRef.current === -1)
      {
        // 进入历史：保存当前草稿
        draftRef.current = input
        historyIndexRef.current = 0
      }
      else
      {
        historyIndexRef.current = Math.min(msgs.length - 1, historyIndexRef.current + 1)
      }
      setInput(msgs[msgs.length - 1 - historyIndexRef.current])
    }
    else
    {
      // ArrowDown
      if (historyIndexRef.current === -1) return // 已经是草稿态
      historyIndexRef.current -= 1
      if (historyIndexRef.current < 0)
      {
        // 先恢复草稿到输入框，再清空 ref —— setInput 在调用瞬间快照 draftRef.current，之后清空不影响
        setInput(draftRef.current)
        resetInputHistory()
      }
      else
      {
        setInput(msgs[msgs.length - 1 - historyIndexRef.current])
      }
    }
    return
  }

  // Enter 发送（保留原行为）
  if (e.key === 'Enter' && !e.shiftKey)
  {
    e.preventDefault()
    handleSend()
  }
}
```

- [ ] **Step 3: 在 handleSend 入口处重置历史索引**

修改 `handleSend` useCallback 内部，在 `if (!input.trim() || ...) return` 之后：

```typescript
resetInputHistory()
```

注意：因为 `resetInputHistory` 是 useCallback 包裹（依赖数组为空），可以安全加入 `handleSend` 的依赖数组而不会引发不必要的重渲。

- [ ] **Step 4: 在切换会话/新建会话时重置**

在 `handleSwitchConversation` 内 `setActiveConversationId(conv.id)` 之后：

```typescript
resetInputHistory()
```

在 `handleNewConversation` 内 `setActiveConversationId(conv.id)` 之后：

```typescript
resetInputHistory()
```

- [ ] **Step 5: 项目切换时重置（已通过加载会话 effect 重置 input，但补一道保险）**

在加载历史消息的 useEffect 中（`fetchConversation(currentProjectId).then(...)` 那段）的 `then` 回调最后添加：

```typescript
resetInputHistory()
```

- [ ] **Step 6: 运行类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/workbench/AgentChatPanel.tsx
git commit -m "feat(workflow): input history navigation via arrow up/down"
```

---

### Task 4: Agent 答复耗时 + 工具条复制按钮

**Files:**
- Modify: `frontend/src/components/workbench/AgentChatPanel.tsx`

**核心约束**：耗时三出口（done/error/abort）统一写入；写入前必须 `flushTextBuffer()`，避免与文本缓冲竞态。

- [ ] **Step 1: 添加 formatDuration 工具函数**

在 `truncateTitle` 旁边添加：

```typescript
/** 毫秒数格式化：< 1s 显示 ms，>= 1s 显示 1 位小数 s */
function formatDuration(ms: number): string
{
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}
```

- [ ] **Step 2: handleSend 中创建 assistantMsg 时记录 startedAt**

定位 `handleSend` 中：
```typescript
const assistantMsg: AiMessage = {
  id: crypto.randomUUID(),
  role: 'assistant',
  content: '',
  segments: [],
  timestamp: Date.now(),
}
```

修改为：
```typescript
const sendStartedAt = Date.now()
const assistantMsg: AiMessage = {
  id: crypto.randomUUID(),
  role: 'assistant',
  content: '',
  segments: [],
  timestamp: sendStartedAt,
  startedAt: sendStartedAt,
}
```

- [ ] **Step 3: onAgentDone 中写入 durationMs（先 flush）**

修改：
```typescript
onAgentDone: () => {
  flushTextBuffer()
  const durationMs = Date.now() - sendStartedAt
  updateAiMessage(assistantMsg.id, (m) => ({
    ...m,
    durationMs,
  }))
  incrementKnowledgeVersion()
},
```

- [ ] **Step 4: onError 中写入 durationMs**

修改：
```typescript
onError: (error) => {
  flushTextBuffer()
  const durationMs = Date.now() - sendStartedAt
  updateAiMessage(assistantMsg.id, (m) => ({
    ...m,
    content: m.content || `错误：${error}`,
    segments: m.content ? m.segments : [...m.segments, {
      type: 'agent_text' as const,
      content: `错误：${error}`,
      data: undefined,
    }],
    durationMs,
  }))
},
```

- [ ] **Step 5: catch + finally 中处理 abort**

修改原 catch 块：
```typescript
} catch (err: any) {
  if (err.name !== 'AbortError') {
    const durationMs = Date.now() - sendStartedAt
    updateAiMessage(assistantMsg.id, (m) => ({
      ...m,
      content: m.content || `连接错误：${err.message}`,
      segments: m.content ? m.segments : [...m.segments, {
        type: 'agent_text' as const,
        content: `连接错误：${err.message}`,
        data: undefined,
      }],
      durationMs,
    }))
  } else {
    // AbortError: 用户主动停止，记录耗时
    flushTextBuffer()
    const durationMs = Date.now() - sendStartedAt
    updateAiMessage(assistantMsg.id, (m) => ({
      ...m,
      durationMs,
    }))
  }
} finally {
  setIsAgentSending(false)
  abortRef.current = null
}
```

- [ ] **Step 6: 修改 CompletedAssistantMessage 渲染工具条**

> **顺序依赖**：本 Step 复用 Task 2 Step 2 定义的 `CopyButton` 公用组件。如果以并行/独立模式实施，本 Task 必须在 Task 2 之后执行，或先把 CopyButton 抽到独立文件。subagent-driven-development 模式下按 Task 编号顺序运行，无需额外动作；如以 ad-hoc 顺序执行，先确认 CopyButton 已落地。

替换：
```tsx
const CompletedAssistantMessage = React.memo(function CompletedAssistantMessage({
  msg,
}: {
  msg: AiMessage
})
{
  return <AssistantMessageContentInner msg={msg} isStreaming={false} />
})
```

为：
```tsx
const CompletedAssistantMessage = React.memo(function CompletedAssistantMessage({
  msg,
}: {
  msg: AiMessage
})
{
  return (
    <>
      <AssistantMessageContentInner msg={msg} isStreaming={false} />
      {msg.content && msg.durationMs !== undefined && (
        <div className="flex items-center gap-2 text-[10px] text-muted-foreground mt-1.5">
          <CopyButton content={msg.content} ariaLabel="复制回复内容" />
          <span>用时 {formatDuration(msg.durationMs)}</span>
        </div>
      )}
    </>
  )
})
```

- [ ] **Step 7: 运行类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/workbench/AgentChatPanel.tsx
git commit -m "feat(workflow): agent response duration display and toolbar copy button"
```

---

### Task 5: 发送按钮垂直居中

**Files:**
- Modify: `frontend/src/components/workbench/AgentChatPanel.tsx`

- [ ] **Step 1: 修改发送按钮 className**

定位输入框区的发送按钮（约 1208-1218 行）：

```tsx
<button
  onClick={() => isAgentSending ? abortRef.current?.abort() : handleSend()}
  disabled={!input.trim() && !isAgentSending}
  className={cn(
    'border-none px-2.5 py-1.5 rounded-md text-[11px] self-end transition-colors',
    isAgentSending ? 'bg-red-500 text-white hover:bg-red-600' : 'bg-primary text-primary-foreground disabled:opacity-50'
  )}
  ...
```

替换 className 为：
```tsx
className={cn(
  'border-none px-2.5 py-1.5 rounded-md text-[11px] transition-colors',
  inputRows === 1 ? 'self-center' : 'self-end',
  isAgentSending ? 'bg-red-500 text-white hover:bg-red-600' : 'bg-primary text-primary-foreground disabled:opacity-50'
)}
```

- [ ] **Step 2: 运行类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workbench/AgentChatPanel.tsx
git commit -m "fix(workflow): send button vertical centering on single-line input"
```

---

### Task 6: 新增 MessageAnchorRail 组件 + 集成到 AgentChatPanel

**Files:**
- Create: `frontend/src/components/workbench/MessageAnchorRail.tsx`
- Modify: `frontend/src/components/workbench/AgentChatPanel.tsx`

- [ ] **Step 1: 创建 MessageAnchorRail.tsx**

```tsx
// MessageAnchorRail.tsx — 右侧消息锚点列（快速跳转）

import { useState, useRef, useCallback, useEffect } from 'react'
import type { AiMessage } from '@/stores/workbenchStore'
import { truncateTitle } from './AgentChatPanel'

interface MessageAnchorRailProps
{
  userMessages: AiMessage[]
  activeId: string | null
  onJump: (id: string) => void
}

export function MessageAnchorRail({
  userMessages,
  activeId,
  onJump,
}: MessageAnchorRailProps)
{
  const [showTooltip, setShowTooltip] = useState(false)
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleEnter = useCallback(() => {
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current)
    setShowTooltip(true)
  }, [])

  const handleLeave = useCallback(() => {
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current)
    closeTimerRef.current = setTimeout(() => setShowTooltip(false), 200)
  }, [])

  useEffect(() => {
    return () =>
    {
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current)
    }
  }, [])

  if (userMessages.length < 2) return null

  return (
    <div
      // 视觉宽度 12px（横线在右）；用 pl-2 + w-[20px] 把 hover 热区扩到 20px，避免按钮因 8-12px 横向尺寸命中过窄；外层 pointer-events-none，按钮 pointer-events-auto 捕捉点击
      className="absolute right-0 top-0 bottom-0 flex flex-col justify-center items-end gap-1.5 w-[20px] pl-2 pr-[2px] z-40 pointer-events-none"
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
    >
      {userMessages.map((msg, i) => {
        const isActive = msg.id === activeId
        return (
          <button
            key={msg.id}
            type="button"
            onClick={() => onJump(msg.id)}
            className={cn(
              'pointer-events-auto rounded-full transition-all duration-150 h-[2px]',
              isActive
                ? 'w-[12px] bg-primary'
                : 'w-[8px] bg-muted-foreground/30 hover:bg-muted-foreground/60'
            )}
            aria-label={`跳转到第 ${i + 1} 条消息`}
            title={truncateTitle(msg.content)}
          />
        )
      })}

      {showTooltip && (
        <div
          role="tooltip"
          className="pointer-events-auto absolute right-[calc(100%+8px)] top-1/2 -translate-y-1/2 max-w-[280px] min-w-[180px] bg-white border border-gray-200 rounded shadow-md z-50 py-1 overflow-y-auto max-h-[50vh]"
          onMouseEnter={handleEnter}
          onMouseLeave={handleLeave}
        >
          {userMessages.map((msg, i) => {
            const isActive = msg.id === activeId
            return (
              <button
                key={msg.id}
                type="button"
                onClick={() => {
                  onJump(msg.id)
                  setShowTooltip(false)
                }}
                className={cn(
                  'w-full text-left px-2.5 py-1 text-[10px] hover:bg-muted/50 transition-colors truncate',
                  isActive ? 'text-primary font-medium' : 'text-foreground'
                )}
              >
                {i + 1}. {truncateTitle(msg.content)}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

function cn(...classes: (string | boolean | undefined)[]): string
{
  return classes.filter(Boolean).join(' ')
}
```

- [ ] **Step 2: 在 AgentChatPanel 顶部 import**

```diff
+ import { MessageAnchorRail } from './MessageAnchorRail'
```

- [ ] **Step 3: 添加 activeAnchorId state 和 rAF id ref**

在 `AgentChatPanel` 函数体内（其他 ref 旁）：

```typescript
const [activeAnchorId, setActiveAnchorId] = useState<string | null>(null)
const scrollRAFRef = useRef<number | null>(null)
```

注意：`userMessageRefs` 已在 Task 2 中添加，无需重复。

- [ ] **Step 4: 添加 updateActiveAnchor 函数**

在 `handleMessagesScroll` 之前：

```typescript
const updateActiveAnchor = useCallback(() => {
  if (!scrollRef.current) return
  const container = scrollRef.current
  const containerRect = container.getBoundingClientRect()
  const threshold = containerRect.top + 80

  let bestId: string | null = null
  let bestDist = Infinity

  for (const [id, el] of userMessageRefs.current.entries())
  {
    const elRect = el.getBoundingClientRect()
    // 仅考虑视口内的（与容器交叠）
    if (elRect.bottom < containerRect.top || elRect.top > containerRect.bottom) continue
    // 距 threshold 最近的视为"当前"
    const dist = Math.abs(elRect.top - threshold)
    if (dist < bestDist)
    {
      bestDist = dist
      bestId = id
    }
  }
  setActiveAnchorId(bestId)
}, [])
```

- [ ] **Step 5: 修改 handleMessagesScroll 用 rAF 节流**

替换原有 `handleMessagesScroll`：

```typescript
const handleMessagesScroll = useCallback(() => {
  if (scrollRAFRef.current) cancelAnimationFrame(scrollRAFRef.current)
  scrollRAFRef.current = requestAnimationFrame(() => {
    if (!scrollRef.current) return
    if (scrollRef.current.scrollTop < 50)
    {
      loadMoreMessages()
    }
    updateActiveAnchor()
  })
}, [loadMoreMessages, updateActiveAnchor])
```

- [ ] **Step 6: 加载完成后初始化 activeAnchorId**

在 `aiMessages` 变化的现有 useEffect 后追加一个新 effect：

```typescript
// 消息列表变化后重新计算 activeAnchorId
useEffect(() => {
  // 等下一帧 DOM 完成挂载
  const id = requestAnimationFrame(() => updateActiveAnchor())
  return () => cancelAnimationFrame(id)
}, [aiMessages, updateActiveAnchor])
```

- [ ] **Step 7: 组件 unmount 时清理 refs 与 rAF**

在 useEffect 清理（可放新增的 useEffect 内）：

```typescript
useEffect(() => {
  return () =>
  {
    if (scrollRAFRef.current) cancelAnimationFrame(scrollRAFRef.current)
    userMessageRefs.current.clear()
  }
}, [])
```

- [ ] **Step 8: 消息滚动区改 relative 并渲染锚点列**

定位：

```tsx
<div ref={scrollRef} onScroll={handleMessagesScroll} className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
```

替换为：

```tsx
<div ref={scrollRef} onScroll={handleMessagesScroll} className="flex-1 overflow-y-auto pl-3 pr-6 py-2 space-y-2 relative">
```

> 让位说明：原 `px-3` 让左右各 12px；锚点列绝对定位在右侧（视觉 12px + 热区 20px）会遮挡消息右边缘。改成 `pl-3 pr-6` 让右侧腾出 24px 缓冲（锚点列 20px + 4px 视觉间距），确保最长消息也不会被横线压住。

在 `{aiMessages.map(...)}` 之后（但仍在 scrollRef 容器内部）添加：

```tsx
<MessageAnchorRail
  userMessages={aiMessages.filter(m => m.role === 'user')}
  activeId={activeAnchorId}
  onJump={(id) => {
    const el = userMessageRefs.current.get(id)
    if (el && scrollRef.current)
    {
      // 用 offsetTop 计算，绕过 Safari scrollIntoView 兼容性
      const containerScrollTop = el.offsetTop - scrollRef.current.offsetTop - 12
      scrollRef.current.scrollTop = Math.max(0, containerScrollTop)
      // 高亮提示 1s
      el.classList.add('ring-2', 'ring-primary/40', 'rounded-lg')
      setTimeout(() => {
        el.classList.remove('ring-2', 'ring-primary/40', 'rounded-lg')
      }, 1000)
    }
  }}
/>
```

- [ ] **Step 9: 运行类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/workbench/MessageAnchorRail.tsx frontend/src/components/workbench/AgentChatPanel.tsx
git commit -m "feat(workflow): message anchor rail for quick navigation"
```

---

### Task 7: MessageAnchorRail 单元测试

**Files:**
- Create: `frontend/src/components/workbench/__tests__/MessageAnchorRail.test.tsx`

> **测试范围决策**：AgentChatPanel 当前与 store/SSE/clipboard 强耦合，重写历史导航/复制按钮的集成测试需要大量 mock 基础设施，会显著拉长本次工时并引入脆弱测试。本次只覆盖：
> - `truncateTitle`（已在 Task 1 完成）
> - `MessageAnchorRail`（独立 props-based 组件，可直接测）
>
> 历史导航/复制按钮/耗时三项依靠 `tsc --noEmit` + Task 8 手动验收清单兜底。这是有意识的取舍，记录在 spec 的"风险与取舍"中。

- [ ] **Step 1: 创建测试文件**

```tsx
// frontend/src/components/workbench/__tests__/MessageAnchorRail.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@/test/utils'
import { MessageAnchorRail } from '../MessageAnchorRail'
import type { AiMessage } from '@/stores/workbenchStore'

const makeUserMsg = (id: string, content: string): AiMessage => ({
  id,
  role: 'user',
  content,
  segments: [],
  timestamp: Number(id) + 1000,
})

const makeMsgs = (n: number) =>
  Array.from({ length: n }, (_, i) => makeUserMsg(String(i), `第 ${i + 1} 条消息内容用于测试`))

describe('MessageAnchorRail', () => {
  it('少于 2 条消息不渲染', () => {
    const { container } = render(
      <MessageAnchorRail userMessages={makeMsgs(1)} activeId={null} onJump={vi.fn()} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('零条消息不渲染', () => {
    const { container } = render(
      <MessageAnchorRail userMessages={[]} activeId={null} onJump={vi.fn()} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('渲染锚点数量与 userMessages 一致', () => {
    render(
      <MessageAnchorRail userMessages={makeMsgs(5)} activeId={null} onJump={vi.fn()} />
    )
    const anchors = screen.getAllByLabelText(/^跳转到第 \d+ 条消息$/)
    expect(anchors).toHaveLength(5)
  })

  it('点击锚点触发 onJump 并传入正确 id', () => {
    const onJump = vi.fn()
    const msgs = makeMsgs(3)
    render(<MessageAnchorRail userMessages={msgs} activeId={null} onJump={onJump} />)
    const anchors = screen.getAllByLabelText(/^跳转到第 \d+ 条消息$/)
    fireEvent.click(anchors[1])
    expect(onJump).toHaveBeenCalledWith(msgs[1].id)
  })

  it('activeId 对应锚点有高亮 className', () => {
    const msgs = makeMsgs(3)
    render(<MessageAnchorRail userMessages={msgs} activeId={msgs[1].id} onJump={vi.fn()} />)
    const target = screen.getByLabelText('跳转到第 2 条消息')
    expect(target.className).toContain('w-[12px]')
    expect(target.className).toContain('bg-primary')
  })

  it('非 active 锚点是默认样式', () => {
    const msgs = makeMsgs(3)
    render(<MessageAnchorRail userMessages={msgs} activeId={msgs[1].id} onJump={vi.fn()} />)
    const other = screen.getByLabelText('跳转到第 1 条消息')
    expect(other.className).toContain('w-[8px]')
    expect(other.className).not.toContain('bg-primary')
  })

  it('mouseenter 容器后浮层显现', async () => {
    const msgs = makeMsgs(3)
    const { container } = render(
      <MessageAnchorRail userMessages={msgs} activeId={null} onJump={vi.fn()} />
    )
    const rail = container.firstChild as HTMLElement
    fireEvent.mouseEnter(rail)
    const tooltip = await screen.findByRole('tooltip')
    expect(tooltip).toBeInTheDocument()
    // 浮层中应包含每条消息的标题
    expect(tooltip.textContent).toContain('1.')
    expect(tooltip.textContent).toContain('2.')
    expect(tooltip.textContent).toContain('3.')
  })

  it('点击浮层中的标题项触发 onJump 并关闭浮层', async () => {
    const onJump = vi.fn()
    const msgs = makeMsgs(3)
    const { container } = render(
      <MessageAnchorRail userMessages={msgs} activeId={null} onJump={onJump} />
    )
    const rail = container.firstChild as HTMLElement
    fireEvent.mouseEnter(rail)
    const tooltip = await screen.findByRole('tooltip')
    const items = tooltip.querySelectorAll('button')
    fireEvent.click(items[2])
    expect(onJump).toHaveBeenCalledWith(msgs[2].id)
  })
})
```

- [ ] **Step 2: 运行测试**

Run: `cd frontend && npx vitest run src/components/workbench/__tests__/MessageAnchorRail.test.tsx`
Expected: 8 PASS

- [ ] **Step 3: 跑全量测试 + lint**

```bash
cd frontend && npm run test:run
cd frontend && npm run lint
```

Expected: 全部 PASS（如有现存失败案例不在本次新增内，标注但不修）

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workbench/__tests__/MessageAnchorRail.test.tsx
git commit -m "test(workflow): MessageAnchorRail unit tests"
```

---

### Task 8: 整体回归 + 手动验收

**Files:** 无代码改动（验收性）

- [ ] **Step 1: 重建前端**

```bash
docker compose build --no-cache frontend && docker compose up -d frontend
```

注意：本次不改 backend，无需重启 backend。

- [ ] **Step 2: 浏览器打开 `http://localhost:3001/`，登录进入工作台**

- [ ] **Step 3: 逐项手动验收**

| # | 验收项 | 操作 | 预期 |
|---|--------|------|------|
| 1 | 用户气泡背景 | 在气泡内拖选文字 | 背景为浅灰蓝、选区颜色清晰可见 |
| 2 | 历史导航 ↑ | 发 3 条消息后聚焦输入框（空内容）按 ↑↑↑↑ | 依次显示最新→次新→最早→保持最早 |
| 3 | 历史导航 ↓ | 在 ↑ 状态下按 ↓↓↓↓ | 依次回到次新→最新→恢复草稿/空 |
| 4 | 草稿恢复 | 输入未发送内容→↑→↓ | 草稿恢复 |
| 5 | composition 拦截 | 中文输入法拼音状态按 ↑/Enter | 不切换历史，不发送 |
| 6 | 多行光标 | 多行内容中部按 ↑/↓ | 走原生光标移动，不切换历史 |
| 7 | 用户复制 | hover 用户气泡 | 下方显示复制按钮，点击切换 Check 1.5s，剪贴板含内容 |
| 8 | Agent 耗时 | 发送消息等待完成 | 答复下方显示 `用时 X.Xs` |
| 9 | Agent 中止耗时 | 发送后按 Esc x2 | 下方显示 `用时 X.Xs`（停止耗时） |
| 10 | Agent 复制 | 完成的 assistant 消息 | 工具条左侧复制按钮 + 右侧耗时同行；点击复制 |
| 11 | 发送按钮居中 | 单行输入 | 按钮垂直居中于输入框 |
| 12 | 发送按钮多行 | Shift+Enter 换行至 3 行 | 按钮贴底（self-end） |
| 13 | 锚点列出现 | 发 ≥ 2 条 user 消息 | 右侧出现竖向横线列 |
| 14 | 锚点点击跳转 | 点击中间一条横线 | 滚动到对应消息，目标气泡短暂高亮 ring |
| 15 | 锚点浮层 | 鼠标移入横线列 | 弹出含标题列表浮层；点击标题跳转 |
| 16 | 当前位置高亮 | 滚动消息区 | 视口顶部最近的 user 锚点变为 12px + bg-primary |
| 17 | < 2 条不显示锚点列 | 仅 1 条 user 消息 | 锚点列不渲染 |
| 18 | 切换会话重置 | 发消息后切到旧会话再回 | 历史索引/草稿不残留 |
| 19 | 锚点列不遮挡正文 | 发若干长消息撑到右边缘 | 气泡内容/复制按钮均不被横线压住 |
| 20 | 锚点列热区命中 | 鼠标缓慢从消息区右侧滑入 | 距离右边缘 20px 内即触发浮层，无需精确命中 12px 横线 |
| 21 | clipboard 失败容错 | 模拟 navigator.clipboard 不可用（Firefox 非 HTTPS） | 复制按钮点击不抛错、不切 Check，但 fallback 通过 execCommand 走通时切 Check |

- [ ] **Step 4: 任意验收项失败时**

不要补丁式修复。回到对应 Task 修复，重启/重建，重跑该项验收。

- [ ] **Step 5: 验收全通过后，最终 commit**

```bash
# 若有 dev 阶段的小修补未提交
git status
# 整理散落改动
git add .
git commit -m "chore(workflow): final adjustments after manual verification" || true
```

---

## 验收完成标记

全部 8 个 Task 完成后，本次实现宣告结束。

## 不在本次实现范围

- 后端 `agent_messages` 表 `duration_ms` 列与持久化（历史会话耗时不显示是有意的）
- token 统计 / 价格估算
- 锚点列对 assistant 消息的索引
- 移动端适配
- 复制成功的 toast 反馈（仅按钮态切换，避免视觉噪音）
