# AI 搭档项目隔离与对话持久化 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 AI 搭档跨项目状态污染和对话刷新丢失两个问题，通过前端项目级 store 隔离 + 后端 DB 持久化 + token-based 上下文截断实现。

**Architecture:** 后端新增 `agent_conversations` / `agent_messages` 两张表，消息保存嵌入 `agent_chat` SSE 端点内部（不新增独立 API）。前端 `workbenchStore` 加 `currentProjectId` 守卫自动清理/加载，`AICompanionSidebar` 进入项目时加载历史。上下文截断复用现有 `estimate_tokens`，从 `model_config.context_window` 读上限。

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + LangGraph (不变) | React 18 + Zustand + TypeScript

---

### Task 1: 创建后端 SQLAlchemy 模型

**Files:**
- Create: `backend/app/models/agent_conversation.py`

- [ ] **Step 1: 创建模型文件**

```python
# backend/app/models/agent_conversation.py
"""AI 搭档会话与消息数据模型"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime,
    ForeignKey, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class AgentConversation(Base):
    """AI 搭档会话 — 每个项目仅一个会话"""

    __tablename__ = "agent_conversations"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    title = Column(String(200), default="")
    message_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship(
        "AgentMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AgentMessage.created_at",
    )
    project = relationship("Project", backref="agent_conversation", uselist=False)


class AgentMessage(Base):
    """AI 搭档消息"""

    __tablename__ = "agent_messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_agent_messages_role",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer,
        ForeignKey("agent_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(10), nullable=False)
    content = Column(Text, nullable=False, default="")
    segments = Column(JSONB, default=list)
    actions = Column(JSONB, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("AgentConversation", back_populates="messages")
```

- [ ] **Step 2: 验证模型可导入**

```bash
docker exec novelagent-backend-1 python -c "from app.models.agent_conversation import AgentConversation, AgentMessage; print('OK')"
```

---

### Task 2: 创建 Alembic 迁移

**Files:**
- Create: `backend/alembic/versions/<hash>_add_agent_conversations.py` (auto-generated)

- [ ] **Step 1: 生成迁移文件**

```bash
docker exec novelagent-backend-1 alembic revision --autogenerate -m "add agent conversations and messages"
```

- [ ] **Step 2: 检查生成的迁移文件**

检查 `backend/alembic/versions/` 下最新文件，确认包含 `agent_conversations` 和 `agent_messages` 两张表的 `create_table` 操作，以及正确的索引和外键。

- [ ] **Step 3: 执行迁移**

```bash
docker exec novelagent-backend-1 alembic upgrade head
```

Expected: 输出 `Running upgrade ... -> <hash>, add agent conversations and messages`

- [ ] **Step 4: 验证表已创建**

```bash
docker exec novelagent-db-1 psql -U novelagent -d novelagent -c "\dt agent_*"
```

Expected: 列出 `agent_conversations` 和 `agent_messages` 两张表

---

### Task 3: 添加 context_window 获取辅助函数

**Files:**
- Modify: `backend/app/agents/agent_context.py` (文件末尾追加)

- [ ] **Step 1: 添加 get_context_window 函数和默认映射**

```python
# 在 backend/app/agents/agent_context.py 末尾追加

# 模型上下文窗口默认映射（context_window 为 NULL 时使用）
_MODEL_CONTEXT_WINDOW_DEFAULTS: dict[str, int] = {
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "claude-3.5-sonnet": 200000,
    "claude-sonnet-4-6": 200000,
    "deepseek-v3": 128000,
    "deepseek-r1": 128000,
    "qwen-plus": 131072,
}

DEFAULT_CONTEXT_WINDOW = 128000


def get_context_window(model_config) -> int:
    """获取模型的上下文窗口大小

    优先级：model_config.context_window > 默认映射 > 128000
    """
    if model_config and model_config.context_window:
        return model_config.context_window

    model_name = (model_config.model_name or "") if model_config else ""
    return _MODEL_CONTEXT_WINDOW_DEFAULTS.get(model_name, DEFAULT_CONTEXT_WINDOW)
```

- [ ] **Step 2: 验证导入**

```bash
docker exec novelagent-backend-1 python -c "from app.agents.agent_context import get_context_window; print(get_context_window(None))"
```

Expected: `128000`

---

### Task 4: 修改 agent_chat + 新增 conversation API 端点

**Files:**
- Modify: `backend/app/api/agent.py`

这是核心改动。分三步：A) 新增辅助函数，B) 新增 2 个端点，C) 改造 agent_chat。

- [ ] **Step 1: 在 agent.py 顶部导入区追加**

在现有 import 后追加（不替换原有 import）：

```python
from app.models.agent_conversation import AgentConversation, AgentMessage
from app.agents.agent_context import get_context_window, estimate_tokens
from app.models.model_config import ModelConfig
```

- [ ] **Step 2: 追加会话辅助函数**（`_release_busy_lock` 函数之后）

```python
def _get_or_create_conversation(db: Session, project_id: int) -> AgentConversation:
    """获取或创建项目会话（每个项目仅一个）"""
    conv = db.query(AgentConversation).filter(
        AgentConversation.project_id == project_id
    ).first()
    if not conv:
        conv = AgentConversation(project_id=project_id)
        db.add(conv)
        db.commit()
        db.refresh(conv)
    return conv


def _save_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
    segments: list | None = None,
    actions: list | None = None,
) -> AgentMessage:
    """保存一条消息（不 commit，由调用方管理事务）"""
    msg = AgentMessage(
        conversation_id=conversation_id,
        role=role,
        content=content or "",
        segments=segments or [],
        actions=actions or [],
    )
    db.add(msg)
    return msg


def _save_user_message(project_id: int, message: str):
    """保存用户消息（独立 Session，fire-and-forget）"""
    db = SessionLocal()
    try:
        conv = _get_or_create_conversation(db, project_id)
        _save_message(db, conv.id, "user", message)
        conv.message_count = (conv.message_count or 0) + 1
        if not conv.title:
            conv.title = message[:50]
        conv.updated_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save user message: {e}")
        db.rollback()
    finally:
        db.close()


def _save_assistant_message(project_id: int, content: str, segments: list, actions: list):
    """保存 assistant 消息（独立 Session，agent_done 后调用）"""
    db = SessionLocal()
    try:
        conv = _get_or_create_conversation(db, project_id)
        _save_message(db, conv.id, "assistant", content, segments, actions)
        conv.message_count = (conv.message_count or 0) + 1
        conv.updated_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save assistant message: {e}")
        db.rollback()
    finally:
        db.close()


def _build_truncated_history(
    history: list[dict],
    history_budget: int,
) -> list[dict]:
    """从最新往前截断 history，不超 history_budget token"""
    if not history or history_budget <= 0:
        return []

    kept: list[dict] = []
    used = 0
    for msg in reversed(history):
        msg_tokens = estimate_tokens(str(msg.get("content", "")))
        if used + msg_tokens > history_budget:
            break
        kept.insert(0, msg)
        used += msg_tokens
    return kept
```

- [ ] **Step 3: 在 router 定义后加入 GET /conversation 端点**

```python
@router.get("/{project_id}/agent/conversation")
async def get_conversation(
    project_id: int,
    limit: int = 50,
    before_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前项目的 AI 搭档会话及消息"""
    get_project_for_user(project_id, current_user.id, db)

    conv = _get_or_create_conversation(db, project_id)

    query = db.query(AgentMessage).filter(
        AgentMessage.conversation_id == conv.id
    )
    if before_id is not None:
        query = query.filter(AgentMessage.id < before_id)
    query = query.order_by(AgentMessage.created_at.desc()).limit(limit)

    messages_raw = query.all()
    # 反转为升序
    messages_raw = list(reversed(messages_raw))

    messages = [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "segments": m.segments or [],
            "actions": m.actions or [],
            "timestamp": int(m.created_at.timestamp() * 1000) if m.created_at else 0,
        }
        for m in messages_raw
    ]

    return {
        "conversation_id": conv.id,
        "title": conv.title,
        "message_count": conv.message_count,
        "messages": messages,
    }
```

- [ ] **Step 4: 加入 DELETE /conversation 端点**

```python
@router.delete("/{project_id}/agent/conversation")
async def clear_conversation(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """清空当前项目的 AI 搭档对话"""
    get_project_for_user(project_id, current_user.id, db)

    conv = db.query(AgentConversation).filter(
        AgentConversation.project_id == project_id
    ).first()
    if conv:
        conv.messages.delete()
        conv.message_count = 0
        conv.title = ""
        conv.updated_at = datetime.utcnow()
        db.commit()

    return {"detail": "对话已清空"}
```

- [ ] **Step 5: 改造 stream_agent_events — 通过 accumulator 累积回复内容**

修改 `stream_agent_events` 函数：加入可选 `accumulator` 参数用于累积完整回复内容（供保存用）。

```python
async def stream_agent_events(
    graph,
    messages: list,
    project_id: int,
    accumulator: dict | None = None,
):
    """流式输出 Agent 事件

    accumulator 为 dict 时，函数会在其中累积 full_content/segments/actions，
    供调用方在流结束后保存到 DB。不传则行为与现有逻辑完全一致。
    """
    write_tools = {
        "update_outline", "update_character", "create_character",
        "update_chapter_outline", "update_relations",
        "generate_chapter_content", "rewrite_chapter",
        "edit_paragraph", "insert_scene", "revise_section", "polish_prose",
        "update_inspiration_brief",
    }
    module_map = {
        "update_outline": "outline",
        "update_character": "characters",
        "create_character": "characters",
        "update_chapter_outline": "chapter_outlines",
        "update_relations": "relations",
        "generate_chapter_content": "writing",
        "rewrite_chapter": "writing",
        "edit_paragraph": "writing",
        "insert_scene": "writing",
        "revise_section": "writing",
        "polish_prose": "writing",
        "update_inspiration_brief": "inspiration",
    }

    try:
        async for event in graph.astream_events(
            {"messages": messages},
            config={"configurable": {"thread_id": f"agent-{project_id}"}},
            version="v2",
        ):
            kind = event.get("event", "")

            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and chunk.content and isinstance(chunk.content, str):
                    if accumulator is not None:
                        accumulator["full"] = accumulator.get("full", "") + chunk.content
                        accumulator.setdefault("segments", []).append(
                            {"type": "agent_text", "content": chunk.content}
                        )
                    yield format_agent_text(chunk.content)

            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                tool_input = event.get("data", {}).get("input", {})
                if accumulator is not None:
                    accumulator.setdefault("actions", []).append({
                        "tool": tool_name,
                        "status": "running",
                        "args": tool_input,
                    })
                yield format_agent_tool_start(tool_name, tool_input)

            elif kind == "on_tool_end":
                tool_name = event.get("name", "")
                tool_output = event.get("data", {}).get("output", {})

                if tool_name in write_tools:
                    module = module_map.get(tool_name, "unknown")
                    yield format_ai_update(module, f"{tool_name} 执行完成")

                output_data = (
                    json.dumps(tool_output, ensure_ascii=False)
                    if isinstance(tool_output, dict)
                    else str(tool_output)
                )
                yield format_agent_tool_result(tool_name, {"output": output_data[:500]})

                # 标记 action 为 done
                if accumulator is not None:
                    actions = accumulator.get("actions", [])
                    for a in reversed(actions):
                        if a["tool"] == tool_name and a.get("status") == "running":
                            a["status"] = "done"
                            a["result"] = (
                                tool_output if isinstance(tool_output, dict)
                                else {"output": str(tool_output)}
                            )
                            break

                # 生成类 tool：发送章节预览事件（同现有逻辑）
                if tool_name in ("generate_chapter_content", "rewrite_chapter") and isinstance(tool_output, dict):
                    if tool_output.get("success"):
                        yield format_agent_chapter_preview({
                            "chapter_number": tool_output.get("chapter_number"),
                            "title": tool_output.get("title", ""),
                            "word_count": tool_output.get("word_count", 0),
                            "preview": tool_output.get("preview", ""),
                            "action": "generated" if tool_name == "generate_chapter_content" else "rewritten",
                        })

                # 审核 tool：发送审核结果事件
                if tool_name == "review_chapter" and isinstance(tool_output, dict):
                    if tool_output.get("success") and tool_output.get("review"):
                        yield format_agent_review(tool_output["review"])

        yield format_agent_done()

    except Exception as e:
        logger.error(f"Agent stream error: {e}")
        yield format_error_message(str(e))
```

- [ ] **Step 6: 改造 agent_chat — 加入消息保存 + context_window 截断 + 流结束后自动保存助理消息**

修改 `agent_chat` 函数中 `_stream_with_cleanup` 部分（其余逻辑同 Step 3-4）：

```python
# ⑧ 流式返回 + 完成时保存 assistant 消息
async def _stream_with_cleanup():
    acc: dict = {}  # 可变容器，stream_agent_events 会往里写
    try:
        async for sse_event in stream_agent_events(graph, messages, project_id, accumulator=acc):
            yield sse_event
        # 流完成后保存 assistant 消息到 DB
        _save_assistant_message(
            project_id,
            content=acc.get("full", ""),
            segments=acc.get("segments", []),
            actions=acc.get("actions", []),
        )
    finally:
        _release_busy_lock(project_id)
        reset_tool_context(context_tokens)

return StreamingResponse(
    _stream_with_cleanup(),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    },
)
```

**agent_chat 其余代码不变**（项目鉴权、并发锁、读取 stage、构建 system prompt、token 截断、创建 Agent 图）。这些逻辑已在 Step 3-4 的基础上直接追加，不需要额外替换。

- [ ] **Step 7: 验证后端 API**

```bash
# 测试 GET conversation (空)
curl -u admin:admin123 http://localhost:8000/api/projects/1/agent/conversation
# 预期: { "conversation_id": N, "messages": [], ... }

# 测试 DELETE conversation
curl -u admin:admin123 -X DELETE http://localhost:8000/api/projects/1/agent/conversation
# 预期: { "detail": "对话已清空" }
```

---

### Task 5: 前端 — ModelConfig 类型加 context_window

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 在 ModelConfig 接口中加入字段**

```typescript
export interface ModelConfig {
  id: number
  name: string
  provider: string
  provider_type: 'single' | 'coding_plan'
  base_url: string
  model_name?: string
  models?: ModelItem[]
  has_api_key: boolean
  is_enabled: boolean
  is_default: boolean
  health_status?: string
  health_latency?: number
  last_health_check?: string
  context_window?: number  // 新增：模型上下文窗口大小
  created_at: string
  updated_at: string
}
```

- [ ] **Step 2: 验证 TypeScript 编译**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: 无新增类型错误（context_window 相关）

---

### Task 6: 前端 — agentApi.ts 加会话 API

**Files:**
- Modify: `frontend/src/lib/agentApi.ts`

- [ ] **Step 1: 追加会话 API 函数**

在 `agentApi.ts` 文件末尾追加：

```typescript
/** 会话响应类型 */
export interface ConversationResponse {
  conversation_id: number
  title: string
  message_count: number
  messages: Array<{
    id: string
    role: 'user' | 'assistant'
    content: string
    segments: Array<{ type: string; content: string; data?: Record<string, unknown> }>
    actions?: Array<{
      tool: string
      status: 'running' | 'done' | 'error'
      description: string
      args?: Record<string, unknown>
      result?: Record<string, unknown>
    }>
    timestamp: number
  }>
}

/**
 * 获取项目会话及消息
 */
export async function fetchConversation(
  projectId: number,
  limit?: number,
  beforeId?: number,
): Promise<ConversationResponse> {
  const { getSessionToken } = await import('./api')
  const API_BASE_URL = import.meta.env.VITE_API_URL || ''
  const token = getSessionToken()

  const params = new URLSearchParams()
  if (limit) params.set('limit', String(limit))
  if (beforeId) params.set('before_id', String(beforeId))

  const query = params.toString()
  const url = `${API_BASE_URL}/api/projects/${projectId}/agent/conversation${query ? '?' + query : ''}`

  const headers: HeadersInit = {}
  if (token) {
    headers['Authorization'] = `Basic ${btoa(`${token}:`)}`
  }

  const res = await fetch(url, { headers, credentials: 'include' })
  if (!res.ok) {
    throw new Error(`Failed to fetch conversation: ${res.status}`)
  }
  return res.json()
}

/**
 * 清空项目会话
 */
export async function deleteConversation(projectId: number): Promise<void> {
  const { getSessionToken } = await import('./api')
  const API_BASE_URL = import.meta.env.VITE_API_URL || ''
  const token = getSessionToken()

  const headers: HeadersInit = {}
  if (token) {
    headers['Authorization'] = `Basic ${btoa(`${token}:`)}`
  }

  const res = await fetch(
    `${API_BASE_URL}/api/projects/${projectId}/agent/conversation`,
    { method: 'DELETE', headers, credentials: 'include' },
  )
  if (!res.ok) {
    throw new Error(`Failed to clear conversation: ${res.status}`)
  }
}
```

---

### Task 7: 前端 — workbenchStore 加项目隔离 + 会话加载

**Files:**
- Modify: `frontend/src/stores/workbenchStore.ts`

- [ ] **Step 1: 在 WorkbenchState 接口中加入新字段和方法签名**

在 `interface WorkbenchState` 中加入：

```typescript
// 项目隔离
currentProjectId: number | null
setCurrentProjectId: (id: number | null) => void

// 会话持久化
loadingMessages: boolean
loadConversation: (projectId: number) => Promise<void>
clearConversation: (projectId: number) => Promise<void>
```

- [ ] **Step 2: 更新 initialState**

```typescript
const initialState = {
  // ... existing
  currentProjectId: null as number | null,
  loadingMessages: false,
  // ... rest unchanged
}
```

- [ ] **Step 3: 实现 setCurrentProjectId**

在 `create` 回调中加入：

```typescript
setCurrentProjectId: (id) => {
  const { currentProjectId } = get()
  if (id !== currentProjectId) {
    set({
      currentProjectId: id,
      aiMessages: [],
      aiUpdateMarkers: {},
      loadingMessages: id ? true : false,
    })
    if (id) {
      // 异步加载，loadConversation 内部调用 set
    }
  }
},
```

- [ ] **Step 4: 实现 loadConversation 和 clearConversation**

```typescript
loadConversation: async (projectId) => {
  try {
    const { fetchConversation } = await import('@/lib/agentApi')
    const data = await fetchConversation(projectId, 50)
    set({
      aiMessages: data.messages.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        segments: m.segments || [],
        actions: m.actions || [],
        timestamp: m.timestamp,
      })),
      loadingMessages: false,
    })
  } catch {
    set({ loadingMessages: false })
  }
},

clearConversation: async (projectId) => {
  try {
    const { deleteConversation } = await import('@/lib/agentApi')
    await deleteConversation(projectId)
    set({ aiMessages: [] })
  } catch {
    // 静默失败
  }
},
```

注意：`setCurrentProjectId` 中的异步加载不能在 set 回调中完成（Zustand 限制）。改为同步触发，异步执行：

```typescript
setCurrentProjectId: (id) => {
  const { currentProjectId } = get()
  if (id !== currentProjectId) {
    set({
      currentProjectId: id,
      aiMessages: [],
      aiUpdateMarkers: {},
      loadingMessages: !!id,
    })
    if (id) {
      // 异步加载放到 microtask
      Promise.resolve().then(() => get().loadConversation(id))
    }
  }
},
```

- [ ] **Step 5: 更新 reset 方法**

```typescript
reset: () => set({ ...initialState }),
```

---

### Task 8: 前端 — AICompanionSidebar 加载历史 + 清空按钮

**Files:**
- Modify: `frontend/src/components/workbench/AICompanionSidebar.tsx`

- [ ] **Step 1: 加入 useEffect 加载历史**

在现有 `useEffect`（加载模型列表）之后、`if (!aiSidebarOpen)` 之前加入：

```typescript
const loadConversation = useWorkbenchStore((s) => s.loadConversation)
const loadingMessages = useWorkbenchStore((s) => s.loadingMessages)

useEffect(() =>
{
  if (projectId)
  {
    loadConversation(projectId)
  }
}, [projectId])  // eslint-disable-line react-hooks/exhaustive-deps
```

- [ ] **Step 2: Header 区加入清空按钮**

在 Header 的 `</button>`（折叠按钮）之前加入：

```tsx
<button
  onClick={async () =>
  {
    if (confirm('确定清空当前对话记录？'))
    {
      await useWorkbenchStore.getState().clearConversation(projectId)
    }
  }}
  className="p-1 text-gray-400 hover:text-red-500 transition-colors"
  title="清空对话"
>
  <Trash2 className="h-3.5 w-3.5" />
</button>
```

需要在 import 中加入 `Trash2`：

```typescript
import { PanelRightClose, PanelRightOpen, ChevronDown, Trash2 } from 'lucide-react'
```

- [ ] **Step 3: handleSend 中 history 来源改为 store**

当前 `handleSend` 中的 `history` 构建已经是来自 `aiMessages`，不需要改动。但需要确保 `aiMessages` 在加载完成后包含历史记录。

---

### Task 9: 前端 — ProjectWorkbench 调用 setCurrentProjectId

**Files:**
- Modify: `frontend/src/pages/ProjectWorkbench.tsx`

- [ ] **Step 1: 加入 useEffect**

```typescript
import { useEffect } from 'react'

// 在组件内，projectId 常量定义之后
const setCurrentProjectId = useWorkbenchStore((s) => s.setCurrentProjectId)

useEffect(() =>
{
  if (projectId)
  {
    setCurrentProjectId(projectId)
  }
}, [projectId, setCurrentProjectId])
```

---

### Task 10: 端到端验证

- [ ] **Step 1: 重启后端服务**

```bash
docker compose restart backend
```

- [ ] **Step 2: 验证项目隔离**

1. 打开项目 A → 在 AI 搭档中发消息 "项目A测试"
2. 导航到项目 B → AI 搭档对话框应为空（加载新项目历史或无历史）
3. 导航回项目 A → AI 搭档应加载之前的消息

- [ ] **Step 3: 验证持久化**

1. 在项目 A 发消息 → 确认收到回复
2. 刷新页面 → 对话仍存在

- [ ] **Step 4: 验证清空**

1. 点击清空按钮 → 确认清空
2. 刷新 → 确认仍为空

- [ ] **Step 5: 运行现有测试确保无回归**

```bash
docker exec novelagent-backend-1 pytest -v
cd frontend && npm run test:run
```

---

## 架构决策说明

1. **消息保存嵌入 agent_chat 而非独立 API**：避免前端在 agent_done 后再次网络请求失败导致消息丢失。后端在流开始前保存用户消息、流结束后保存 assistant 回复，保证原子性。

2. **context_window 从 model_config 读取**：`model_config.context_window` 字段已存在（model_config.py:44），用户可在设置页配置。NULL 时回退到默认映射表。

3. **单会话模型强制**：`agent_conversations.project_id` 有 unique 约束，保证每个项目仅一个会话。未来扩展到多会话时只需去掉 unique 约束 + 加 API 参数。

4. **LangGraph 框架不改动**：`create_agent_graph`、`astream_events`、tool 调用链路全部保持不变。改动在 API 层和 store 层。

5. **history 截断位置在后端**：前端仍传最近 20 条的 role+content，但后端根据 token budget 进一步截断后才送入 LLM。前端不需要感知上下文窗口。
