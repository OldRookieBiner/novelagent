# NovelAgent 全栈优化批次 1 — 修正后实施方案

> 经过三轮审查修正：修复原计划的 8 处缺陷，补充 3 处遗漏，确保根因修复而非补丁。
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 实施 8 项针对性优化：卷 API 注册、对话历史分页、多会话面板集成、初始化进度增强、Agent 工具进度反馈、统一错误处理、SSE 渲染性能、SSE 连接健壮性。

**Architecture:** 每个任务独立，可单独实施。所有变更遵循既有模式（FastAPI 路由注册、React 组件组合、Zustand store 更新、SSE 事件流）。无新依赖。

**Tech Stack:** Python/FastAPI (backend), React/TypeScript/Zustand (frontend), LangGraph SSE streaming

---

## File Structure

| File | Responsibility | Task |
|------|---------------|------|
| `backend/app/main.py` | 路由注册 + 启动清理 | 1, 15 |
| `backend/app/agents/sse_events.py` | SSE 事件格式化 | 11 |
| `backend/app/api/agent.py` | Agent 聊天/会话端点 | 11, 15 |
| `backend/app/agents/tools/assist/report_progress.py` | 新建：进度报告工具 | 11 |
| `backend/app/agents/tools/registry.py` | 工具注册表 | 11 |
| `backend/app/agents/prompts.py` | Agent 系统提示 | 11 |
| `frontend/src/components/workbench/AgentChatPanel.tsx` | Agent 聊天面板 | 2, 3, 11, 14 |
| `frontend/src/lib/agentApi.ts` | Agent API 客户端 | 11 |
| `frontend/src/stores/workbenchStore.ts` | 工作台状态 | 11 |
| `frontend/src/components/common/CreateProjectDialog.tsx` | 项目创建 | 4 |
| `frontend/src/lib/api.ts` | REST API 客户端 | 13 |
| `frontend/src/components/workbench/knowledge/KnowledgeTab.tsx` | 知识库标签页 | 13 |

---

### Task 1: Register Volumes API Route

**Files:**
- Modify: `backend/app/main.py`

- [x] **Step 1: Add volumes router import**

在 `backend/app/main.py` 顶部 import 区域（约第 20 行附近，与其他 api import 一起）：

```python
from app.api.volumes import router as volumes_router
```

- [x] **Step 2: Register the router**

在 `app.include_router(agent.router, ...)` 之后（约第 144 行）添加：

```python
app.include_router(volumes_router, prefix="/api/projects", tags=["volumes"])
```

- [x] **Step 3: Verify & commit**

```bash
docker compose restart backend
# 测试: curl http://localhost:8000/api/projects/1/volumes 应返回 [] 而非 404
git add backend/app/main.py
git commit -m "fix(api): register volumes router to fix 404 on volume/arc endpoints"
```

---

### Task 2: Conversation History Pagination — Scroll-to-Load

**Files:**
- Modify: `frontend/src/components/workbench/AgentChatPanel.tsx`

**原计划缺陷**: `aiMessages` 变化时触发的自动滚动到底部 `useEffect` 会在加载历史消息后把用户拉回底部，抵消滚动位置恢复逻辑。修正：添加 `skipAutoScrollRef` 标记位。

- [x] **Step 1: Add refs for scroll management**

在 `AgentChatPanel` 组件的 ref 声明区域添加：

```typescript
const skipAutoScrollRef = useRef(false)
const isLoadingMoreRef = useRef(false)
const prevScrollHeightRef = useRef(0)  // 加载历史消息时保存旧 scrollHeight
```

- [x] **Step 2: Add `loadMoreMessages` callback**

在加载聊天记录的 `useEffect` 之后添加：

```typescript
// 加载更多历史消息（向上滚动时触发）
const loadMoreMessages = useCallback(async () => {
  if (!currentProjectId || aiMessages.length === 0) return
  if (isLoadingMoreRef.current) return  // 防止重复请求
  const oldestId = aiMessages[0]?.id
  if (!oldestId) return

  isLoadingMoreRef.current = true
  prevScrollHeightRef.current = scrollRef.current?.scrollHeight ?? 0

  try
  {
    const res = await fetchConversation(currentProjectId, undefined, 30, parseInt(oldestId))
    if (res.messages.length === 0) return

    const older: AiMessage[] = res.messages.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      segments: (m.segments || []).map((s) => ({
        type: (s.type as any) || "agent_text",
        content: s.content || "",
        data: s.data,
      })),
      timestamp: m.timestamp,
    }))

    // 去重后前置
    const existingIds = new Set(aiMessages.map((m) => m.id))
    const newMessages = older.filter((m) => !existingIds.has(m.id))
    if (newMessages.length > 0)
    {
      skipAutoScrollRef.current = true
      setAiMessages([...newMessages, ...aiMessages])
    }
  }
  catch
  {
    // 静默失败
  }
  finally
  {
    isLoadingMoreRef.current = false
  }
}, [currentProjectId, aiMessages, setAiMessages])
```

- [x] **Step 3: Modify auto-scroll useEffect**

替换现有的自动滚动 effect：

```typescript
// 自动滚动到底部（加载历史消息时恢复位置而非滚底）
useEffect(() => {
  if (skipAutoScrollRef.current)
  {
    skipAutoScrollRef.current = false
    // React 已完成重渲染，此时 DOM 已更新，可以安全恢复滚动位置
    if (scrollRef.current && prevScrollHeightRef.current > 0)
    {
      const newScrollHeight = scrollRef.current.scrollHeight
      scrollRef.current.scrollTop = newScrollHeight - prevScrollHeightRef.current
      prevScrollHeightRef.current = 0
    }
    return
  }
  if (scrollRef.current)
  {
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }
}, [aiMessages, pendingImpacts])
```

- [x] **Step 4: Add scroll-to-top detection**

在消息容器 `<div ref={scrollRef}>` 添加 `onScroll` handler：

```typescript
const handleMessagesScroll = useCallback(() => {
  if (!scrollRef.current) return
  if (scrollRef.current.scrollTop < 50)
  {
    loadMoreMessages()
  }
}, [loadMoreMessages])
```

更新消息容器 div：

```tsx
<div
  ref={scrollRef}
  onScroll={handleMessagesScroll}
  className="flex-1 overflow-y-auto px-3 py-2 space-y-2"
>
```

- [x] **Step 5: Verify & commit**

```bash
docker compose restart frontend
# 测试: 打开有多条消息的项目，滚动到顶部，验证历史消息加载且不跳到底部
git add frontend/src/components/workbench/AgentChatPanel.tsx
git commit -m "feat(frontend): add scroll-to-load pagination for agent conversation history"
```

---

### Task 3: Multi-Session Panel Integration

**Files:**
- Modify: `frontend/src/components/workbench/AgentChatPanel.tsx`
- Modify: `frontend/src/stores/workbenchStore.ts`（如需同步 activeConversationId）

**原计划缺陷**: `handleSwitchConversation` 中调用了 `activateConversation`，但 `ConversationHistoryDialog.handleActivate` 已经调用过，导致重复请求和 busy lock 冲突。修正：回调只做 fetchConversation + 状态更新。

- [x] **Step 1: Import dependencies**

在 `AgentChatPanel.tsx` 顶部 import 区域添加（检查是否已存在）：

```typescript
import { History, Plus } from 'lucide-react'
import { ConversationHistoryDialog } from './ConversationHistoryDialog'
import { createConversation, fetchConversation } from '@/lib/agentApi'
```

- [x] **Step 2: Add conversation dialog state and store binding**

在 `AgentChatPanel` 组件内添加：

```typescript
const [showConversationHistory, setShowConversationHistory] = useState(false)
const { activeConversationId, setActiveConversationId } = useWorkbenchStore()
```

注意：`activeConversationId` 和 `setActiveConversationId` 已在 `workbenchStore` 中定义，需从 store 解构。检查现有解构是否已包含，未包含则添加。

- [x] **Step 3: Add conversation switch/create handlers**

**关键：`handleSwitchConversation` 不调用 `activateConversation`**，因为 `ConversationHistoryDialog` 内部已完成激活操作。

```typescript
// 切换会话（对话框已完成 activate，此处只加载消息）
const handleSwitchConversation = useCallback(async (conv: { id: number }) => {
  if (!currentProjectId) return
  setActiveConversationId(conv.id)
  try
  {
    const res = await fetchConversation(currentProjectId, conv.id)
    const loaded: AiMessage[] = res.messages.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      segments: (m.segments || []).map((s) => ({
        type: (s.type as any) || "agent_text",
        content: s.content || "",
        data: s.data,
      })),
      timestamp: m.timestamp,
    }))
    setAiMessages(loaded)
  }
  catch
  {
    // 会话切换失败，保持当前消息
  }
}, [currentProjectId, setActiveConversationId, setAiMessages])

// 新建会话
const handleNewConversation = useCallback(async () => {
  if (!currentProjectId || isAgentSending) return
  try
  {
    const conv = await createConversation(currentProjectId)
    setActiveConversationId(conv.id)
    setAiMessages([])
  }
  catch (err: any)
  {
    // 可能 busy lock 冲突或其他错误
  }
}, [currentProjectId, isAgentSending, setActiveConversationId, setAiMessages])
```

- [x] **Step 4: Add buttons to panel Header**

在 Header 区域（阶段徽章与状态点之间）添加：

```tsx
<button
  onClick={handleNewConversation}
  disabled={isAgentSending}
  className="p-1 text-gray-400 hover:text-gray-600 transition-colors disabled:opacity-30"
  title="新建会话"
>
  <Plus className="h-3.5 w-3.5" />
</button>
<button
  onClick={() => setShowConversationHistory(true)}
  className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
  title="会话历史"
>
  <History className="h-3.5 w-3.5" />
</button>
```

- [x] **Step 5: Add ConversationHistoryDialog**

在组件末尾（关闭 `</div>` 之前）添加：

```tsx
<ConversationHistoryDialog
  open={showConversationHistory}
  onOpenChange={setShowConversationHistory}
  onSwitchConversation={handleSwitchConversation}
  isAgentSending={isAgentSending}
/>
```

- [x] **Step 6: Verify & commit**

```bash
docker compose restart frontend
# 测试: 点击「会话历史」查看列表、新建会话、切换会话
git add frontend/src/components/workbench/AgentChatPanel.tsx frontend/src/stores/workbenchStore.ts
git commit -m "feat(frontend): integrate multi-session management into agent chat panel"
```

---

### Task 4: Init Progress Enhancement — Per-Step Error Display

**Files:**
- Modify: `frontend/src/components/common/CreateProjectDialog.tsx`

**原计划缺陷**:
1. `init:error` 的 `data.stage` 值 `"llm_init"` 没有映射，不应报错
2. 出错步骤仍显示 `○`（未开始），应标记为已尝试
3. `init:done` 携带 `status: "partial"` 时无区分

- [x] **Step 1: Extend StageState interface**

```typescript
interface StageState
{
  concept: boolean
  seed: boolean
  name: boolean
  world: boolean
  characters: boolean
  outline: boolean
  style: boolean
  errors: Record<string, string>  // 步骤 key → 错误消息
}
```

更新所有 `setStage` 初始值添加 `errors: {}`。

- [x] **Step 2: Handle `init:error` events**

在 `onEvent` handler 中添加（在 `init:cancelled` 之前）：

```typescript
else if (type === 'init:error')
{
  const stageName = data.stage as string
  const errorMsg = data.error as string
  const stageKeyMap: Record<string, string | null> = {
    story_seed: 'seed',
    novel_name: 'name',
    world_setting: 'world',
    characters: 'characters',
    outline: 'outline',
    style: 'style',
    llm_init: null,  // LLM 初始化错误，不映射到创作步骤
  }
  const key = stageKeyMap[stageName]
  if (key)
  {
    // 标记步骤为已尝试 + 记录错误
    setStage(s => ({ ...s, [key]: true, errors: { ...s.errors, [key]: errorMsg } }))
  }
}
```

- [x] **Step 3: Handle `init:done` partial status**

修改 `init:done` 处理：

```typescript
else if (type === 'init:done')
{
  if (data.status === 'partial')
  {
    setError('部分步骤失败，项目已创建但可能不完整')
  }
  setProgress(100)
}
```

- [x] **Step 4: Render error indicators in stage list**

替换现有的 stages 渲染区域：

```tsx
{stages.map((s) => {
  const hasError = stage.errors[s.key]
  return (
    <div
      key={s.key}
      className={`flex items-center text-sm ${
        hasError ? 'text-red-500' :
        s.done ? 'text-gray-500' :
        (stage as any)[s.key] ? 'text-indigo-600 font-medium' :
        'text-gray-300'
      }`}
    >
      <span className={`w-5 h-5 rounded-full border-2 border-current flex items-center justify-center mr-2 text-xs ${
        hasError ? 'bg-red-50' : ''
      }`}>
        {hasError ? '✗' : s.done ? '✓' : (stage as any)[s.key] ? '●' : '○'}
      </span>
      <span className="flex-1">{s.label}</span>
      {hasError && (
        <span className="text-[10px] text-red-400 truncate max-w-[120px]" title={hasError}>
          失败
        </span>
      )}
    </div>
  )
})}
```

- [x] **Step 5: Verify & commit**

```bash
docker compose restart frontend
# 测试: 用无效模型配置创建项目，验证失败步骤红色标识
git add frontend/src/components/common/CreateProjectDialog.tsx
git commit -m "feat(frontend): show per-step init error indicators in project creation dialog"
```

---

### Task 11: Agent Tool Progress Feedback

**Files:**
- Create: `backend/app/agents/tools/assist/report_progress.py`
- Modify: `backend/app/agents/tools/registry.py`
- Modify: `backend/app/agents/sse_events.py`
- Modify: `backend/app/api/agent.py`
- Modify: `backend/app/agents/prompts.py`
- Modify: `frontend/src/stores/workbenchStore.ts`
- Modify: `frontend/src/lib/agentApi.ts`
- Modify: `frontend/src/components/workbench/AgentChatPanel.tsx`

**原计划缺陷**: `report_progress` 工具的 `on_tool_end` 也会被正常处理为 `agent_tool_result` 事件，前端会渲染多余的「报告进度 完成」行。修正：在 `stream_agent_events` 中对 `report_progress` 跳过常规处理，只发 `agent_progress` 事件。

- [x] **Step 1: Create report_progress tool**

新建 `backend/app/agents/tools/assist/report_progress.py`：

```python
"""报告进度的辅助工具"""

from langchain_core.tools import tool


@tool
def report_progress(message: str, percent: int = 0) -> dict:
    """Report current progress to the user. Use this when performing long operations
    like writing a chapter or generating a large outline, to keep the user informed.

    Args:
        message: Human-readable progress description (e.g., '正在写第3章正文...')
        percent: Progress percentage 0-100
    """
    return {"progress_message": message, "progress_percent": percent}
```

- [x] **Step 2: Register in registry.py and update __init__.py**

在 `backend/app/agents/tools/registry.py` 添加导入：

```python
from app.agents.tools.assist.report_progress import report_progress
```

将 `report_progress` 添加到 `INCUBATION_TOOLS`、`STRUCTURE_TOOLS`、`WRITING_TOOLS` 列表中（放在 `progress_report` 旁边即可）。

在 `backend/app/agents/tools/assist/__init__.py` 中添加导出（保持一致性）：

```python
from .report_progress import report_progress
```

并更新模块 docstring 中的工具数量（4 → 5）。

- [x] **Step 3: Add format_agent_progress to sse_events.py**

在 `backend/app/agents/sse_events.py` 中添加：

```python
def format_agent_progress(tool_name: str, data: dict) -> str:
    """格式化 Agent 工具进度事件"""
    payload = {"tool": tool_name, **data}
    return f"event: agent_progress\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
```

- [x] **Step 4: Handle report_progress in stream_agent_events**

在 `backend/app/api/agent.py` 中修改 `stream_agent_events` 函数：

1. 添加导入：

```python
from app.agents.sse_events import format_agent_progress
```

2. 在 `on_tool_start` 块中，用 `if/else` 替换原有逻辑：

原代码：
```python
elif kind == "on_tool_start":
    tool_name = event.get("name", "")
    tool_input = event.get("data", {}).get("input", {})
    if accumulator is not None:
        accumulator.setdefault("actions", []).append({...})
        accumulator.setdefault("segments", []).append({...})
    yield format_agent_tool_start(tool_name, tool_input)
```

替换为：
```python
elif kind == "on_tool_start":
    tool_name = event.get("name", "")
    tool_input = event.get("data", {}).get("input", {})
    # 进度报告工具：不记录到 accumulator actions，不发 tool_start，只发 progress
    if tool_name == "report_progress":
        if accumulator is not None:
            accumulator.setdefault("segments", []).append({
                "type": "progress",
                "content": str(tool_input.get("message", "")),
                "data": {"percent": tool_input.get("percent", 0)},
            })
        yield format_agent_progress(tool_name, tool_input)
    else:
        if accumulator is not None:
            accumulator.setdefault("actions", []).append({
                "tool": tool_name,
                "status": "running",
                "args": tool_input,
            })
            accumulator.setdefault("segments", []).append({
                "type": "tool_start",
                "content": tool_name,
                "data": {"tool": tool_name},
            })
        yield format_agent_tool_start(tool_name, tool_input)
```

注意：`async for event in graph.astream_events(...)` 中不能使用 `continue`，必须用 `if/else` 分支控制流程。

3. 在 `on_tool_end` 块中，用 `if/else` 替换原有逻辑：

原代码：
```python
elif kind == "on_tool_end":
    tool_name = event.get("name", "")
    tool_output = event.get("data", {}).get("output", {})
    output_str = json.dumps(tool_output, ensure_ascii=False) if isinstance(tool_output, dict) else str(tool_output)
    yield format_agent_tool_result(tool_name, {"output": output_str[:800]})
    if accumulator is not None:
        # ... actions update ...
        accumulator.setdefault("segments", []).append({...})
    # Impact / Warning checks...
```

替换为（在获取 `tool_output` 之后插入判断，其余代码不变）：
```python
elif kind == "on_tool_end":
    tool_name = event.get("name", "")
    tool_output = event.get("data", {}).get("output", {})

    # 进度报告工具：只发 progress 事件，跳过 tool_result / actions
    if tool_name == "report_progress" and isinstance(tool_output, dict):
        yield format_agent_progress(tool_name, tool_output)
        if accumulator is not None:
            accumulator.setdefault("segments", []).append({
                "type": "progress",
                "content": str(tool_output.get("progress_message", "")),
                "data": {"percent": tool_output.get("progress_percent", 0)},
            })
    else:
        # 原有逻辑不变
        output_str = json.dumps(tool_output, ensure_ascii=False) if isinstance(tool_output, dict) else str(tool_output)
        yield format_agent_tool_result(tool_name, {"output": output_str[:800]})
        if accumulator is not None:
            actions = accumulator.get("actions", [])
            for a in reversed(actions):
                if a["tool"] == tool_name and a.get("status") == "running":
                    a["status"] = "done"
                    a["result"] = tool_output if isinstance(tool_output, dict) else {"output": str(tool_output)}
                    break
            accumulator.setdefault("segments", []).append({
                "type": "tool_result",
                "content": tool_name,
                "data": {"tool": tool_name},
            })
        if tool_name in IMPACT_TOOLS and isinstance(tool_output, dict):
            if tool_output.get("change_id"):
                yield format_impact_assessment(tool_output)
        if tool_name in WARNING_TOOLS and isinstance(tool_output, dict):
            if tool_output.get("warning"):
                yield format_warning(tool_name, {"message": tool_output["warning"]})
```

- [x] **Step 5: Add progress segment type to frontend store**

在 `frontend/src/stores/workbenchStore.ts` 中修改 `AiMessageSegment` 类型：

```typescript
export interface AiMessageSegment {
  type: 'agent_text' | 'chunk' | 'review' | 'chapter_preview' | 'warning' | 'tool_start' | 'tool_result' | 'progress'
  content: string
  data?: Record<string, unknown>
}
```

- [x] **Step 6: Handle agent_progress in frontend agentApi.ts**

在 `AgentChatCallbacks` 接口添加：

```typescript
onAgentProgress?: (data: { progress_message: string; progress_percent: number }) => void
```

在 `sendAgentMessage` 的 `switch` 语句中添加：

```typescript
case 'agent_progress':
  callbacks.onAgentProgress?.(payload as { progress_message: string; progress_percent: number })
  break
```

- [x] **Step 7: Handle progress in AgentChatPanel.tsx handleSend**

在 `handleSend` 的 callbacks 中添加（注意：非文本事件前先 flush 文本缓冲 — 见 Task 14）：

```typescript
onAgentProgress: (data) => {
  updateAiMessage(assistantMsg.id, (m) => ({
    ...m,
    segments: [
      ...m.segments.filter(s => s.type !== 'progress'),
      {
        type: 'progress' as const,
        content: data.progress_message,
        data: { percent: data.progress_percent },
      },
    ],
  }))
},
```

- [x] **Step 8: Render progress segment in AssistantMessageContent**

在 `AssistantMessageContent` 的段渲染逻辑中，`tool_result` 处理之后添加：

```tsx
if (seg.type === 'progress')
{
  const percent = (seg.data?.percent as number) || 0
  return (
    <div key={`prog-${i}`} className="mt-1.5 flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
        <div className="h-full bg-blue-400 rounded-full transition-all" style={{ width: `${percent}%` }} />
      </div>
      <span className="text-[10px] text-muted-foreground shrink-0">{seg.content}</span>
    </div>
  )
}
```

- [x] **Step 9: Add hint in agent system prompt**

在 `backend/app/agents/prompts.py` 的 `AGENT_SYSTEM_PROMPT` 中，写作阶段相关说明区域添加：

```
- 长时间操作（生成章节内容、生成世界观等）时，先调用 report_progress 告诉用户当前进度，再执行实际工具
```

- [x] **Step 10: Update TOOL_LABELS in AgentChatPanel**

在 `AgentChatPanel.tsx` 的 `TOOL_LABELS` 映射中添加：

```typescript
report_progress: '报告进度',
```

- [x] **Step 11: Verify & commit**

```bash
docker compose restart backend
docker compose restart frontend
# 测试: 让 Agent 执行章节生成，验证进度条出现，无多余「报告进度 完成」行
git add backend/app/agents/tools/assist/report_progress.py backend/app/agents/tools/registry.py backend/app/agents/sse_events.py backend/app/api/agent.py backend/app/agents/prompts.py frontend/src/stores/workbenchStore.ts frontend/src/lib/agentApi.ts frontend/src/components/workbench/AgentChatPanel.tsx
git commit -m "feat: add report_progress tool for agent operation progress feedback"
```

---

### Task 13: Unified Error Handling

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/workbench/knowledge/KnowledgeTab.tsx`

无修正，与原计划一致。

- [x] **Step 1: Add centralized error toast helper**

在 `frontend/src/lib/api.ts` 末尾（API 对象之前）添加：

```typescript
/**
 * 统一业务错误处理：对非 401 错误弹出 toast
 * 用于 try/catch 中替代静默 catch
 */
export function handleApiError(err: unknown, context?: string): void
{
  if (err instanceof Error)
  {
    // 401 已在 request() 中处理，此处不重复
    if (err.message.includes('HTTP 401')) return
    console.error(`[${context || 'API'}]`, err.message)
    // 使用动态导入避免循环依赖
    import('sonner').then(({ toast }) => {
      toast.error(context ? `${context}：${err.message}` : err.message)
    })
  }
  else
  {
    console.error(`[${context || 'API'}]`, err)
  }
}
```

- [x] **Step 2: Replace console.error in KnowledgeTab**

在 `KnowledgeTab.tsx` 中：

1. 添加导入：

```typescript
import { handleApiError } from '@/lib/api'
```

2. 找到 `loadKnowledge` catch 中的 `console.error('Failed to load knowledge:', err)`，替换为：

```typescript
handleApiError(err, '加载知识库')
```

- [x] **Step 3: Verify & commit**

```bash
docker compose restart frontend
# 测试: 断网后加载知识库，验证错误 toast 提示
git add frontend/src/lib/api.ts frontend/src/components/workbench/knowledge/KnowledgeTab.tsx
git commit -m "fix(frontend): add centralized error handler and replace silent catches with user feedback"
```

---

### Task 14: SSE Rendering Performance — Debounce + Streaming/Completed Split

**Files:**
- Modify: `frontend/src/components/workbench/AgentChatPanel.tsx`

**原计划缺陷**:
1. `React.memo` 对正在流式接收的消息无效（segments 每次新建数组导致 memo 浅比较永远不等）
2. 防抖缓冲区在新消息发送时被覆盖，可能丢失未刷新文本
3. 防抖期间非文本事件（`onToolStart` 等）到来时文本仍在缓冲，导致段顺序错乱

**修正**: 防抖只合并文本 chunk，非文本事件到来时先 flush；拆分流式/已完成渲染路径。

- [x] **Step 1: Add text buffer ref and flush function**

在 `AgentChatPanel` 组件的 ref 声明区域添加：

```typescript
// SSE 文本缓冲 — 合并高频 chunk 后统一更新
const textBufferRef = useRef<{
  id: string
  chunks: string[]
  timer: ReturnType<typeof setTimeout> | null
}>({ id: '', chunks: [], timer: null })

const flushTextBuffer = useCallback(() => {
  const buf = textBufferRef.current
  if (!buf.chunks.length) return

  const combined = buf.chunks.join('')
  buf.chunks = []
  buf.timer = null

  updateAiMessage(buf.id, (m) => ({
    ...m,
    content: m.content + combined,
    segments: [...m.segments, {
      type: 'agent_text' as const,
      content: combined,
      data: undefined,
    }],
  }))
}, [updateAiMessage])
```

- [x] **Step 2: Replace direct onAgentText with buffered update**

在 `handleSend` 的 `onAgentText` 回调中，替换现有实现：

```typescript
onAgentText: (content) => {
  const buf = textBufferRef.current
  buf.id = assistantMsg.id
  buf.chunks.push(content)
  if (buf.timer) clearTimeout(buf.timer)
  buf.timer = setTimeout(flushTextBuffer, 50)
},
```

- [x] **Step 3: Flush before non-text events**

在 `onToolStart`、`onToolResult`、`onAgentProgress`（Task 11）回调的开头添加：

```typescript
flushTextBuffer()
```

这确保非文本段和文本段的顺序正确。

- [x] **Step 4: Flush on done/error and at start of new send**

在 `onAgentDone` 回调中：

```typescript
onAgentDone: () => {
  flushTextBuffer()
  incrementKnowledgeVersion()
},
```

在 `onError` 回调中：

```typescript
onError: (error) => {
  flushTextBuffer()
  updateAiMessage(assistantMsg.id, (m) => ({
    ...m,
    content: m.content || `错误：${error}`,
    segments: m.content ? m.segments : [...m.segments, {
      type: 'agent_text' as const,
      content: `错误：${error}`,
      data: undefined,
    }],
  }))
},
```

在 `handleSend` 函数开头（创建 `userMsg` 之前）添加：

```typescript
// 确保上一条消息的文本缓冲已刷新
flushTextBuffer()
```

- [x] **Step 5: Split streaming/completed message rendering**

将 `AssistantMessageContent` 拆为内部实现 + 两个外壳：

**前置：** 文件顶部 import 需添加 `React`：

```typescript
import React, { useState, useRef, useEffect, useCallback } from 'react'
```

（替换原有的 `import { useState, useRef, useEffect, useCallback } from 'react'`）

```typescript
/** 内部实现：共享渲染逻辑 */
function AssistantMessageContentInner({
  msg,
  isStreaming,
}: {
  msg: AiMessage
  isStreaming: boolean
})
{
  // ... 现有的 AssistantMessageContent 全部逻辑 ...
}

/** 已完成消息 — React.memo 有效（props 稳定） */
const CompletedAssistantMessage = React.memo(function CompletedAssistantMessage({
  msg,
}: {
  msg: AiMessage
})
{
  return <AssistantMessageContentInner msg={msg} isStreaming={false} />
})

/** 流式中消息 — 不 memo */
function StreamingAssistantMessage({ msg }: { msg: AiMessage })
{
  return <AssistantMessageContentInner msg={msg} isStreaming={true} />
}
```

将原有的 `AssistantMessageContent` 调用替换为条件渲染：

```tsx
{aiMessages.map((msg) => (
  <div
    key={msg.id}
    className={cn(
      msg.role === 'user' ? 'flex justify-end' : ''
    )}
  >
    {msg.role === 'user' ? (
      <div className="rounded-lg px-3 py-2 text-[11px] leading-relaxed max-w-[80%] bg-primary text-primary-foreground">
        {msg.content}
      </div>
    ) : (
      <div className="text-[11px] leading-relaxed text-foreground">
        {msg.id === lastAssistantId && isAgentSending ? (
          <StreamingAssistantMessage msg={msg} />
        ) : (
          <CompletedAssistantMessage msg={msg} />
        )}
      </div>
    )}
  </div>
))}
```

- [x] **Step 6: Verify & commit**

```bash
docker compose restart frontend
# 测试: 发送长 Agent 请求，验证流式文本平滑，工具调用和文本段顺序正确
git add frontend/src/components/workbench/AgentChatPanel.tsx
git commit -m "perf(frontend): debounce SSE text updates and split streaming/completed message rendering"
```

---

### Task 15: SSE Connection Robustness — Busy Lock Guarantee

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/agent.py`

**原计划缺陷**:
1. `stream_agent_events` 内部已有 `try/except` 捕获所有异常并 yield `format_error_message`，异常不会传播到 `_stream_with_cleanup`。因此外部的 `except` 块几乎不会被触发
2. 客户端断开时，`_save_assistant_message` 在 `try` 块内（`async for` 之后），不会执行 — 部分内容丢失

**修正**: 将 `_save_assistant_message` 移入 `finally` 块。

- [x] **Step 1: Add stale lock cleanup on startup**

在 `backend/app/main.py` 的 `lifespan` 函数中，`create_default_user()` 之后、`yield` 之前添加：

需要先添加导入（在文件顶部 import 区域）：

```python
from app.database import SessionLocal
from app.models.project import Project
```

然后在 lifespan 中添加：

```python
# 释放启动时残留的 busy lock（进程崩溃后不会走 finally）
_startup_db = SessionLocal()
try:
    stale = _startup_db.query(Project).filter(Project.is_busy == True).all()
    for p in stale:
        p.is_busy = False
        p.busy_since = None
        p.busy_by = None
        logger.info(f"Released stale busy lock for project {p.id}")
    _startup_db.commit()
finally:
    _startup_db.close()
```

- [x] **Step 2: Move _save_assistant_message into finally block**

在 `backend/app/api/agent.py` 中修改 `_stream_with_cleanup`：

```python
async def _stream_with_cleanup():
    acc: dict = {}
    try:
        async for event in stream_agent_events(
            graph, messages, project_id, conv.id, accumulator=acc
        ):
            yield event
    finally:
        # 无论正常完成还是中断，都尝试保存已有内容
        if acc.get("full") or acc.get("segments"):
            try:
                _save_assistant_message(
                    project_id,
                    content=acc.get("full", ""),
                    segments=acc.get("segments", []),
                    actions=acc.get("actions", []),
                )
            except Exception as e:
                logger.error(f"Failed to save assistant message: {e}")
        _release_busy_lock(project_id)
        reset_tool_context(context_tokens)
```

关键改动：
- `_save_assistant_message` 从 `try` 块移到 `finally` 块
- 加 `try/except` 保护，避免保存失败影响 lock 释放
- 正常完成时，`acc` 有内容，保存一次（与原来效果相同）
- 中断时，`acc` 可能已有部分内容，也会保存

- [x] **Step 3: Verify & commit**

```bash
docker compose restart backend
# 测试: 启动后端后检查日志有无 stale lock 释放；中断 Agent 流后检查消息是否保存
git add backend/app/main.py backend/app/api/agent.py
git commit -m "fix(backend): release stale busy locks on startup and save partial content on stream interruption"
```

---

## Test Plan

| Task | 验证方式 |
|------|---------|
| 1 | `curl http://localhost:8000/api/projects/1/volumes` 返回 `[]` 而非 404 |
| 2 | 长对话向上滚动加载历史消息，不跳到底部 |
| 3 | 切换会话、新建会话，消息正确加载且无重复 API 调用 |
| 4 | 无效模型配置创建项目，失败步骤红色标识 + partial 提示 |
| 11 | Agent 长操作时进度条出现，无多余「报告进度 完成」行 |
| 13 | 知识库加载失败时 toast 提示 |
| 14 | 长回复流式输出平滑，工具调用和文本段顺序正确 |
| 15 | 重启后端残留 lock 被清理；中断 Agent 流部分内容已保存 |
| 全量 | `docker exec novelagent-backend-1 pytest -v` + `cd frontend && npm run test:run && npm run lint` |

---

## 修正汇总

| 原计划缺陷 | 根因 | 修正方式 |
|-----------|------|---------|
| 任务2: 加载历史后自动滚动到底部 | aiMessages useEffect 无条件滚底 | 添加 skipAutoScrollRef 标记 |
| 任务2: 滚动恢复时 DOM 尚未更新 | finally 中 requestAnimationFrame 在 React 重渲染前执行 | 改用 prevScrollHeightRef + useEffect 中恢复 |
| 任务3: 重复 activateConversation 调用 | 对话框已处理激活，回调又调一次 | 回调只做 fetchConversation + 状态更新 |
| 任务4: 缺少 llm_init 映射 | 映射表不完整 | 映射为 null 静默忽略 |
| 任务4: 出错步骤仍显示未开始 | 未设置 stage[key]=true | error 处理中同时标记为已尝试 |
| 任务4: partial 完成无提示 | init:done 不检查 status | 检测 partial 显示提示 |
| 任务4: keyof StageState 类型变宽 | 添加 errors 字段后 keyof 包含 'errors' | 用 (stage as any)[s.key] 替代 |
| 任务11: report_progress 产生多余 tool_result | 未在 stream 中特殊处理 | 用 if/else 分支跳过常规处理，只发 progress 事件 |
| 任务11: Step 4 中 continue 语法错误 | async for 中不能用 continue | 改为 if/else 结构 |
| 任务11: 缺少 __init__.py 更新 | assist/__init__.py 未导出新工具 | 添加 report_progress 导出 |
| 任务14: React.memo 需要 React 导入 | 文件只导入命名导出，未导入 React | 添加 import React |
| 任务14: React.memo 对流式消息无效 | segments 每次新建数组导致 memo 失效 | 拆分流式/已完成渲染路径 |
| 任务14: 防抖与工具事件顺序错乱 | 非文本事件到来时文本仍在缓冲 | 非文本事件前先 flush |
| 任务15: 部分内容丢失 | _save_assistant_message 在 try 块中 | 移到 finally 块 |
| 任务15: SessionLocal 别名不必要 | main.py 中无同名导入冲突 | 去掉 as StartupSession 别名 |

## Assumptions

- 所有任务独立，可按任意顺序实施，建议按任务编号顺序
- 每个任务完成后执行 `docker compose restart backend/frontend`，确认功能后再提交
- Allman 大括号、中文注释、lucide-react 图标 — 遵循项目既有风格
- Task 11 的 `report_progress` 工具不修改现有工具，只新增辅助工具 + 提示词引导
- Task 14 的 50ms 防抖间隔足够小，用户不会感知延迟
- Task 15 的启动清理只在 app 启动时执行一次，不影响运行时性能
