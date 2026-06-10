# Agent 多会话管理实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\) syntax for tracking.

**Goal:** 为 Agent 侧边栏增加多会话管理能力——新建会话、历史会话列表、切换/重命名/删除会话。

**Architecture:** 在现有 AgentConversation 模型上移除 project_id unique 约束并新增 is_active 字段，后端新增会话 CRUD + 激活端点，前端在 AgentChatPanel Header 加两个按钮并新建 ConversationHistoryDialog 组件。

**Tech Stack:** SQLAlchemy + Alembic + FastAPI (后端), React + shadcn/ui Dialog + Zustand (前端)

---

## 文件结构

| 操作 | 文件 | 职责 |
|------|------|------|
| Create | \`backend/alembic/versions/xxxx_remove_unique_add_is_active.py\` | 数据库迁移 |
| Modify | \`backend/app/models/agent_conversation.py\` | 模型变更：移除 unique，新增 is_active |
| Modify | \`backend/app/models/project.py:agent_conversations\` | relationship 重命名为复数 + uselist=True |
| Modify | \`backend/app/api/agent.py\` | 核心后端改动：新端点 + 内部函数重写 + thread_id 隔离 |
| Modify | \`backend/app/agents/checkpointer.py\` | checkpoint 清理函数（删除会话时调用） |
| Modify | \`frontend/src/lib/agentApi.ts\` | 新增 5 个 API 函数 + 修改现有函数签名 |
| Modify | \`frontend/src/stores/workbenchStore.ts\` | 新增 activeConversationId 状态 |
| Modify | \`frontend/src/components/workbench/AgentChatPanel.tsx\` | Header 按钮集成 |
| Create | \`frontend/src/components/workbench/ConversationHistoryDialog.tsx\` | 会话历史弹窗组件 |

### Task 1: 数据库迁移 — 移除 unique 约束 + 新增 is_active 字段

**Files:**
- Modify: `backend/app/models/agent_conversation.py`
- Modify: `backend/app/models/project.py`
- Create: `backend/alembic/versions/xxxx_remove_unique_add_is_active.py`（通过 alembic revision 生成）

- [ ] **Step 1: 修改 AgentConversation 模型**

在 `backend/app/models/agent_conversation.py` 中：
- 移除 `project_id` 列的 `unique=True`
- 新增 `is_active` 列：`Column(Boolean, default=False, server_default=text('false'))`

```python
# agent_conversation.py 变更
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, CheckConstraint, JSON, Boolean, text

project_id = Column(
    Integer,
    ForeignKey('projects.id', ondelete='CASCADE'),
    nullable=False,
    # 移除 unique=True
)
is_active = Column(Boolean, default=False, server_default=text('false'))
```

- [ ] **Step 2: 修改 Project 模型的 relationship**

在 `backend/app/models/project.py` 中，保持 relationship 名称为 `agent_conversation`，仅将 `uselist` 改为 `True`：

```python
agent_conversation = relationship(
    "AgentConversation", back_populates="project", uselist=True, cascade="all, delete-orphan"
)
```

注意：不改名是因为 AgentConversation 中的 `back_populates="agent_conversation"` 必须与这个 relationship 的名字匹配。

- [ ] **Step 3: 生成 Alembic 迁移脚本**

```bash
cd /Users/biner/Dev/novelagent && docker exec novelagent-backend-1 alembic revision -m "remove_unique_project_id_add_is_active" --autogenerate
```

- [ ] **Step 4: 编辑迁移脚本**

确认 upgrade 包含以下操作（autogenerate 可能遗漏部分，需手动检查）：

```python
def upgrade() -> None:
    # 1. 移除 unique constraint（约束名已通过数据库确认）
    op.drop_constraint('agent_conversations_project_id_key', 'agent_conversations', type_='unique')
    
    # 2. 新增 is_active 列（先允许 NULL 以便回填）
    op.add_column('agent_conversations', sa.Column('is_active', sa.Boolean(), nullable=True))
    
    # 3. 回填现有数据
    op.execute("UPDATE agent_conversations SET is_active = true")
    
    # 4. 设置 NOT NULL + server default
    op.alter_column('agent_conversations', 'is_active', nullable=False, server_default=sa.text('false'))

def downgrade() -> None:
    op.alter_column('agent_conversations', 'is_active', nullable=True, server_default=None)
    op.drop_column('agent_conversations', 'is_active')
    op.create_unique_constraint('agent_conversations_project_id_key', 'agent_conversations', ['project_id'])
```

- [ ] **Step 5: 执行迁移验证**

```bash
docker exec novelagent-backend-1 alembic upgrade head
```

预期：迁移成功，现有会话的 `is_active` 均为 `true`。

- [ ] **Step 6: 提交**

```bash
git add backend/app/models/agent_conversation.py backend/app/models/project.py backend/alembic/versions/
git commit -m "db(agent): remove unique constraint on project_id, add is_active field"
```

### Task 2: 后端 — 内部函数重写 + 新增 API 端点

**Files:**
- Modify: `backend/app/api/agent.py`
- Modify: `backend/app/agents/checkpointer.py`（如需新增 checkpoint 清理函数）

- [ ] **Step 1: 重写 `_get_or_create_conversation` 为 `_get_active_conversation`**

替换原有函数。新函数查询 `is_active=True` 的会话，找不到则创建：

```python
def _get_active_conversation(db: Session, project_id: int) -> AgentConversation:
    """获取项目当前激活的会话，不存在则创建"""
    conv = db.query(AgentConversation).filter(
        AgentConversation.project_id == project_id,
        AgentConversation.is_active == True,
    ).first()
    if not conv:
        conv = AgentConversation(project_id=project_id, is_active=True)
        db.add(conv)
        db.commit()
        db.refresh(conv)
    return conv
```

- [ ] **Step 2: 更新 `_save_user_message` 和 `_save_assistant_message`**

这两个函数内部使用 `db = SessionLocal()` 创建独立 session，`_get_active_conversation` 必须使用这个 session（而非 FastAPI 注入的 session），确保在同一事务中操作。同时将标题截取从 50 字改为 20 字：

```python
def _save_user_message(project_id: int, message: str):
    db = SessionLocal()
    committed = False
    try:
        conv = _get_active_conversation(db, project_id)  # 使用同一 session
        msg = AgentMessage(
            conversation_id=conv.id,
            role="user",
            content=message or "",
        )
        db.add(msg)
        conv.message_count = (conv.message_count or 0) + 1
        if not conv.title:
            conv.title = message[:20]  # 标题取前 20 字
        conv.updated_at = datetime.utcnow()
        db.commit()
        committed = True
    except Exception as e:
        logger.error(f"Failed to save user message: {e}")
    finally:
        if not committed:
            try:
                db.rollback()
            except Exception:
                pass
        try:
            db.close()
        except Exception:
            pass
```

`_save_assistant_message` 同理，仅将 `_get_or_create_conversation` 替换为 `_get_active_conversation`。

- [ ] **Step 3: 新增 Pydantic schema**

```python
from pydantic import BaseModel, Field

class ConversationRenameRequest(BaseModel):
    """重命名会话请求"""
    title: str = Field(min_length=1, max_length=50, description="会话标题")
```

- [ ] **Step 4: 修改 `GET /{project_id}/agent/conversation` 端点**

新增可选 `conversation_id` query param，用于切换会话后显式加载指定会话的消息：

```python
@router.get("/{project_id}/agent/conversation")
async def get_conversation(
    project_id: int,
    conversation_id: Optional[int] = None,
    limit: int = 50,
    before_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取指定会话或当前激活会话的消息。"""
    get_project_for_user(project_id, current_user.id, db)

    if conversation_id:
        conv = db.query(AgentConversation).filter(
            AgentConversation.id == conversation_id,
            AgentConversation.project_id == project_id,
        ).first()
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在")
    else:
        conv = _get_active_conversation(db, project_id)

    query = db.query(AgentMessage).filter(
        AgentMessage.conversation_id == conv.id
    )
    if before_id is not None:
        query = query.filter(AgentMessage.id < before_id)
    query = query.order_by(AgentMessage.created_at.desc()).limit(limit)

    messages_raw = list(reversed(query.all()))
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

- [ ] **Step 5: 新增 `GET /{project_id}/agent/conversations` 端点**

```python
@router.get("/{project_id}/agent/conversations")
async def list_conversations(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出项目所有会话"""
    get_project_for_user(project_id, current_user.id, db)
    convs = db.query(AgentConversation).filter(
        AgentConversation.project_id == project_id
    ).order_by(AgentConversation.updated_at.desc()).all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "message_count": c.message_count,
            "is_active": c.is_active,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in convs
    ]
```

- [ ] **Step 6: 新增 `POST /{project_id}/agent/conversations` 端点**

需要获取 busy lock 防止并发问题：

```python
@router.post("/{project_id}/agent/conversations")
async def create_conversation(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """新建会话"""
    project = get_project_for_user(project_id, current_user.id, db)

    # 获取 busy lock 防止并发
    if not _acquire_busy_lock(db, project_id, "conversation"):
        raise HTTPException(status_code=409, detail="项目正在被使用，请稍后再试")

    try:
        # 软限制检查
        count = db.query(AgentConversation).filter(
            AgentConversation.project_id == project_id
        ).count()
        if count >= 20:
            raise HTTPException(status_code=400, detail="会话数量已达上限（20条），请删除旧会话后再创建")

        # 将当前活跃会话置为非活跃
        db.query(AgentConversation).filter(
            AgentConversation.project_id == project_id,
            AgentConversation.is_active == True,
        ).update({"is_active": False})

        # 创建新会话
        conv = AgentConversation(project_id=project_id, is_active=True, title="")
        db.add(conv)
        db.commit()
        db.refresh(conv)

        return {
            "id": conv.id,
            "title": conv.title,
            "message_count": conv.message_count,
            "is_active": conv.is_active,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _release_busy_lock(project_id)
```

- [ ] **Step 7: 新增 `PUT /{project_id}/agent/conversations/{conversation_id}` 端点**

```python
@router.put("/{project_id}/agent/conversations/{conversation_id}")
async def rename_conversation(
    project_id: int,
    conversation_id: int,
    req: ConversationRenameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重命名会话"""
    get_project_for_user(project_id, current_user.id, db)
    conv = db.query(AgentConversation).filter(
        AgentConversation.id == conversation_id,
        AgentConversation.project_id == project_id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    conv.title = req.title  # Pydantic 已校验 min_length=1, max_length=50
    conv.updated_at = datetime.utcnow()
    db.commit()
    return {
        "id": conv.id,
        "title": conv.title,
        "message_count": conv.message_count,
        "is_active": conv.is_active,
    }
```

- [ ] **Step 8: 新增 `POST /{project_id}/agent/conversations/{conversation_id}/activate` 端点**

需要获取 busy lock 防止并发和 Agent 正在生成时切换：

```python
@router.post("/{project_id}/agent/conversations/{conversation_id}/activate")
async def activate_conversation(
    project_id: int,
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """切换到指定会话"""
    project = get_project_for_user(project_id, current_user.id, db)

    # 获取 busy lock
    if not _acquire_busy_lock(db, project_id, "conversation"):
        raise HTTPException(status_code=409, detail="项目正在被使用，请稍后再试")

    try:
        target = db.query(AgentConversation).filter(
            AgentConversation.id == conversation_id,
            AgentConversation.project_id == project_id,
        ).first()
        if not target:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 同一事务中：先取消当前活跃，再激活目标
        db.query(AgentConversation).filter(
            AgentConversation.project_id == project_id,
            AgentConversation.is_active == True,
        ).update({"is_active": False})
        target.is_active = True
        db.commit()

        return {
            "id": target.id,
            "title": target.title,
            "message_count": target.message_count,
            "is_active": target.is_active,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _release_busy_lock(project_id)
```

- [ ] **Step 9: 新增 `DELETE /{project_id}/agent/conversations/{conversation_id}` 端点**

使用路径参数（与 PUT/activate 一致），并清理 LangGraph checkpoint：

```python
@router.delete("/{project_id}/agent/conversations/{conversation_id}")
async def delete_conversation(
    project_id: int,
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除指定会话"""
    project = get_project_for_user(project_id, current_user.id, db)
    
    # 获取 busy lock 防止并发和 Agent 正在生成时删除
    if not _acquire_busy_lock(db, project_id, "conversation"):
        raise HTTPException(status_code=409, detail="项目正在被使用，请稍后再试")
    
    try:
        conv = db.query(AgentConversation).filter(
            AgentConversation.id == conversation_id,
            AgentConversation.project_id == project_id,
        ).first()
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在")
        if conv.is_active:
            raise HTTPException(status_code=400, detail="无法删除当前激活的会话")

        # 删除 DB 记录（cascade 会删除关联消息）
        db.delete(conv)
        db.commit()

        return {"detail": "会话已删除"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _release_busy_lock(project_id)
```

- [ ] **Step 10: 修改 `POST /{project_id}/agent/chat` 端点 — thread_id 隔离**

将 conversation_id 传入 `stream_agent_events` 用于 thread_id 隔离：

```python
# 在 agent_chat 函数中
conv = _get_active_conversation(db, project_id)  # 替换 _get_or_create_conversation

# ... 构建 messages 等 ...

async def _stream_with_cleanup():
    acc: dict = {}
    try:
        async for event in stream_agent_events(
            graph, messages, project_id, conv.id, accumulator=acc  # 新增 conv.id 参数
        ):
            yield event
        _save_assistant_message(
            project_id,
            content=acc.get("full", ""),
            segments=acc.get("segments", []),
            actions=acc.get("actions", []),
        )
    finally:
        _release_busy_lock(project_id)
        reset_tool_context(context_tokens)
```

- [ ] **Step 11: 修改 `stream_agent_events` 函数签名和 thread_id**

```python
async def stream_agent_events(
    graph,
    messages: list,
    project_id: int,
    conversation_id: int,  # 新增参数
    accumulator: dict | None = None,
):
    """Stream Agent events with cognitive tools."""
    try:
        async for event in graph.astream_events(
            {"messages": messages},
            config={"configurable": {"thread_id": f"agent-{project_id}-{conversation_id}"}},
            version="v2",
        ):
            # ... 原有逻辑不变 ...
```

- [ ] **Step 12: 删除旧的 `_get_or_create_conversation` 函数和旧 DELETE 端点**

确认所有引用已替换后，删除 `_get_or_create_conversation` 函数。旧的 `DELETE /{project_id}/agent/conversation`（清空消息语义）已被新的 `DELETE /{project_id}/agent/conversations/{conversation_id}` 替代。

- [ ] **Step 13: 提交**

```bash
git add backend/app/api/agent.py
git commit -m "api(agent): add multi-conversation CRUD, busy lock, thread_id isolation"
```

### Task 3: 前端 — agentApi.ts 新增 API 函数

**Files:**
- Modify: `frontend/src/lib/agentApi.ts`

- [ ] **Step 1: 新增会话列表响应类型**

```typescript
/** 会话列表项 */
export interface ConversationItem {
  id: number
  title: string
  message_count: number
  is_active: boolean
  created_at: string | null
  updated_at: string | null
}
```

- [ ] **Step 2: 修改 `fetchConversation` — 新增可选 conversationId 参数**

```typescript
/** 获取项目会话及消息 */
export async function fetchConversation(
  projectId: number,
  conversationId?: number,
  limit?: number,
  beforeId?: number,
): Promise<ConversationResponse> {
  const { getSessionToken } = await import('./api')
  const API_BASE_URL = import.meta.env.VITE_API_URL || ''
  const token = getSessionToken()

  const params = new URLSearchParams()
  if (conversationId) params.set('conversation_id', String(conversationId))
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
```

- [ ] **Step 3: 修改 `deleteConversation` — 使用路径参数**

```typescript
/** 删除指定会话 */
export async function deleteConversation(projectId: number, conversationId: number): Promise<void> {
  const { getSessionToken } = await import('./api')
  const API_BASE_URL = import.meta.env.VITE_API_URL || ''
  const token = getSessionToken()

  const headers: HeadersInit = {}
  if (token) {
    headers['Authorization'] = `Basic ${btoa(`${token}:`)}`
  }

  const res = await fetch(
    `${API_BASE_URL}/api/projects/${projectId}/agent/conversations/${conversationId}`,
    { method: 'DELETE', headers, credentials: 'include' },
  )
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Failed to delete conversation: ${res.status}`)
  }
}
```

- [ ] **Step 4: 新增 `fetchConversations` 函数**

```typescript
/** 获取项目所有会话列表 */
export async function fetchConversations(projectId: number): Promise<ConversationItem[]> {
  const { getSessionToken } = await import('./api')
  const API_BASE_URL = import.meta.env.VITE_API_URL || ''
  const token = getSessionToken()

  const headers: HeadersInit = {}
  if (token) {
    headers['Authorization'] = `Basic ${btoa(`${token}:`)}`
  }

  const res = await fetch(
    `${API_BASE_URL}/api/projects/${projectId}/agent/conversations`,
    { headers, credentials: 'include' },
  )
  if (!res.ok) {
    throw new Error(`Failed to fetch conversations: ${res.status}`)
  }
  return res.json()
}
```

- [ ] **Step 5: 新增 `createConversation` 函数**

```typescript
/** 新建会话 */
export async function createConversation(projectId: number): Promise<ConversationItem> {
  const { getSessionToken } = await import('./api')
  const API_BASE_URL = import.meta.env.VITE_API_URL || ''
  const token = getSessionToken()

  const headers: HeadersInit = { 'Content-Type': 'application/json' }
  if (token) {
    headers['Authorization'] = `Basic ${btoa(`${token}:`)}`
  }

  const res = await fetch(
    `${API_BASE_URL}/api/projects/${projectId}/agent/conversations`,
    { method: 'POST', headers, credentials: 'include' },
  )
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Failed to create conversation: ${res.status}`)
  }
  return res.json()
}
```

- [ ] **Step 6: 新增 `activateConversation` 函数**

```typescript
/** 切换到指定会话 */
export async function activateConversation(projectId: number, conversationId: number): Promise<ConversationItem> {
  const { getSessionToken } = await import('./api')
  const API_BASE_URL = import.meta.env.VITE_API_URL || ''
  const token = getSessionToken()

  const headers: HeadersInit = { 'Content-Type': 'application/json' }
  if (token) {
    headers['Authorization'] = `Basic ${btoa(`${token}:`)}`
  }

  const res = await fetch(
    `${API_BASE_URL}/api/projects/${projectId}/agent/conversations/${conversationId}/activate`,
    { method: 'POST', headers, credentials: 'include' },
  )
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Failed to activate conversation: ${res.status}`)
  }
  return res.json()
}
```

- [ ] **Step 7: 新增 `renameConversation` 函数**

```typescript
/** 重命名会话 */
export async function renameConversation(projectId: number, conversationId: number, title: string): Promise<ConversationItem> {
  const { getSessionToken } = await import('./api')
  const API_BASE_URL = import.meta.env.VITE_API_URL || ''
  const token = getSessionToken()

  const headers: HeadersInit = { 'Content-Type': 'application/json' }
  if (token) {
    headers['Authorization'] = `Basic ${btoa(`${token}:`)}`
  }

  const res = await fetch(
    `${API_BASE_URL}/api/projects/${projectId}/agent/conversations/${conversationId}`,
    {
      method: 'PUT',
      headers,
      credentials: 'include',
      body: JSON.stringify({ title }),
    },
  )
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Failed to rename conversation: ${res.status}`)
  }
  return res.json()
}
```

- [ ] **Step 8: 提交**

```bash
git add frontend/src/lib/agentApi.ts
git commit -m "frontend(agent): add multi-conversation API functions with path params"
```

### Task 4: 前端 — workbenchStore 新增 activeConversationId

**Files:**
- Modify: `frontend/src/stores/workbenchStore.ts`

- [ ] **Step 1: 新增状态字段和方法**

在 `WorkbenchState` 接口中新增：

```typescript
activeConversationId: number | null
setActiveConversationId: (id: number | null) => void
```

在 store 实现中新增：

```typescript
activeConversationId: null,
setActiveConversationId: (id) => set({ activeConversationId: id }),
```

- [ ] **Step 2: 修改 `setCurrentProjectId` 重置逻辑**

确保切换项目时也重置 `activeConversationId`：

```typescript
setCurrentProjectId: (id) => set({
  currentProjectId: id,
  aiMessages: [],
  pendingImpacts: [],
  agentWarnings: [],
  knowledgeVersion: 0,
  activeConversationId: null,
}),
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/stores/workbenchStore.ts
git commit -m "frontend(store): add activeConversationId state for multi-conversation"
```

---

### Task 5: 前端 — ConversationHistoryDialog 组件

**Files:**
- Create: `frontend/src/components/workbench/ConversationHistoryDialog.tsx`

- [ ] **Step 1: 创建 ConversationHistoryDialog 组件**

使用 shadcn/ui 的 `Dialog` 组件。关键设计：

```tsx
import { useState, useEffect, useCallback } from 'react'
import { Pencil, Trash2, Check, X } from 'lucide-react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import { fetchConversations, activateConversation, renameConversation, deleteConversation } from '@/lib/agentApi'
import type { ConversationItem } from '@/lib/agentApi'
import ConfirmDialog from '@/components/common/ConfirmDialog'
import { useWorkbenchStore } from '@/stores/workbenchStore'

interface ConversationHistoryDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSwitchConversation: (conversation: ConversationItem) => void
  isAgentSending: boolean
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin}分钟前`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour}小时前`
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 7) return `${diffDay}天前`
  return `${Math.floor(diffDay / 7)}周前`
}

export function ConversationHistoryDialog({
  open, onOpenChange, onSwitchConversation, isAgentSending,
}: ConversationHistoryDialogProps) {
  const currentProjectId = useWorkbenchStore((s) => s.currentProjectId)
  const [conversations, setConversations] = useState<ConversationItem[]>([])
  const [loading, setLoading] = useState(false)
  const [renamingId, setRenamingId] = useState<number | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<ConversationItem | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadConversations = useCallback(async () => {
    if (!currentProjectId) return
    setLoading(true)
    setError(null)
    try {
      const list = await fetchConversations(currentProjectId)
      setConversations(list)
    } catch {
      setError('加载失败')
    } finally {
      setLoading(false)
    }
  }, [currentProjectId])

  useEffect(() => {
    if (open) loadConversations()
  }, [open, loadConversations])

  const handleActivate = async (conv: ConversationItem) => {
    if (conv.is_active || !currentProjectId || isAgentSending) return
    try {
      const updated = await activateConversation(currentProjectId, conv.id)
      onSwitchConversation(updated)
      await loadConversations()
    } catch (err: any) {
      setError(err.message || '切换失败')
    }
  }

  const handleRenameConfirm = async () => {
    if (!renamingId || !renameValue.trim() || !currentProjectId) return
    try {
      await renameConversation(currentProjectId, renamingId, renameValue.trim())
      setRenamingId(null)
      await loadConversations()
    } catch (err: any) {
      setError(err.message || '重命名失败')
    }
  }

  const handleRenameStart = (conv: ConversationItem) => {
    setRenamingId(conv.id)
    setRenameValue(conv.title)
  }

  const handleRenameCancel = () => {
    setRenamingId(null)
    setRenameValue('')
  }

  const handleDeleteConfirm = async () => {
    if (!deleteTarget || !currentProjectId) return
    setDeleting(true)
    try {
      await deleteConversation(currentProjectId, deleteTarget.id)
      setDeleteTarget(null)
      await loadConversations()
    } catch (err: any) {
      setError(err.message || '删除失败')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[380px]">
          <DialogHeader>
            <DialogTitle>会话历史</DialogTitle>
          </DialogHeader>
          {error && (
            <div className="text-xs text-red-500 px-3">{error}</div>
          )}
          <div className="max-h-[400px] overflow-y-auto py-2">
            {loading && conversations.length === 0 && (
              <div className="text-center text-muted-foreground text-xs py-6">加载中...</div>
            )}
            {!loading && conversations.length === 0 && (
              <div className="text-center text-muted-foreground text-xs py-6">暂无会话</div>
            )}
            {conversations.map((conv) => (
              <div
                key={conv.id}
                className={`flex items-center gap-2 px-3 py-2 mx-1 rounded-md mb-0.5 ${
                  conv.is_active ? 'bg-primary/5' : 'hover:bg-muted/50'
                }`}
              >
                <div className="flex-1 min-w-0">
                  {renamingId === conv.id ? (
                    <div className="flex items-center gap-1">
                      <input
                        type="text"
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && renameValue.trim()) handleRenameConfirm()
                          if (e.key === 'Escape') handleRenameCancel()
                        }}
                        className="flex-1 text-[11px] border border-primary rounded px-1.5 py-0.5 outline-none"
                        autoFocus
                        maxLength={50}
                      />
                      <button
                        onClick={handleRenameConfirm}
                        disabled={!renameValue.trim()}
                        className="p-0.5 text-primary hover:text-primary/80 disabled:opacity-40"
                      >
                        <Check className="h-3.5 w-3.5" />
                      </button>
                      <button onClick={handleRenameCancel} className="p-0.5 text-muted-foreground hover:text-foreground">
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ) : (
                    <div
                      className={`text-[11px] cursor-pointer truncate ${
                        conv.is_active ? 'font-medium text-primary' : 'text-foreground'
                      } ${isAgentSending && !conv.is_active ? 'opacity-50 pointer-events-none' : ''}`}
                      onClick={() => handleActivate(conv)}
                    >
                      {conv.title || '未命名会话'}
                    </div>
                  )}
                  <div className="text-[9px] text-muted-foreground mt-0.5">
                    {conv.message_count}条消息 · {formatRelativeTime(conv.updated_at || conv.created_at)}
                  </div>
                </div>
                {conv.is_active && renamingId !== conv.id && (
                  <span className="text-[9px] text-primary bg-primary/10 px-1.5 py-0.5 rounded shrink-0">当前</span>
                )}
                {renamingId !== conv.id && (
                  <button
                    onClick={() => handleRenameStart(conv)}
                    className="p-1 text-muted-foreground hover:text-foreground shrink-0"
                    title="重命名"
                  >
                    <Pencil className="h-3 w-3" />
                  </button>
                )}
                {!conv.is_active && renamingId !== conv.id && (
                  <button
                    onClick={() => setDeleteTarget(conv)}
                    className="p-1 text-muted-foreground/50 hover:text-red-500 shrink-0"
                    title="删除"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deleteTarget}
        title="删除会话"
        message={`确定要删除「${deleteTarget?.title || '未命名会话'}」吗？删除后无法恢复。`}
        confirmText="删除"
        variant="danger"
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
        loading={deleting}
      />
    </>
  )
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/workbench/ConversationHistoryDialog.tsx
git commit -m "frontend(agent): add ConversationHistoryDialog with error handling"
```

---

### Task 6: 前端 — AgentChatPanel 集成会话管理

**Files:**
- Modify: `frontend/src/components/workbench/AgentChatPanel.tsx`

- [ ] **Step 1: 新增 import**

```tsx
import { ConversationHistoryDialog } from './ConversationHistoryDialog'
import { createConversation, fetchConversation } from '@/lib/agentApi'
import type { ConversationItem } from '@/lib/agentApi'
import { History, Plus } from 'lucide-react'
```

- [ ] **Step 2: 新增组件状态和处理函数**

在 AgentChatPanel 组件中新增：

```tsx
const [historyOpen, setHistoryOpen] = useState(false)
const { activeConversationId, setActiveConversationId } = useWorkbenchStore()

const handleNewConversation = async () => {
  if (!currentProjectId || isAgentSending) return
  try {
    const conv = await createConversation(currentProjectId)
    setActiveConversationId(conv.id)
    setAiMessages([])
  } catch (err: any) {
    // 超限等错误，显示 inline 提示
    console.error('创建会话失败:', err.message)
  }
}

const handleSwitchConversation = async (conv: ConversationItem) => {
  if (!currentProjectId) return
  setActiveConversationId(conv.id)
  try {
    // 使用 conversation_id 显式加载指定会话消息
    const res = await fetchConversation(currentProjectId, conv.id)
    const loaded: AiMessage[] = res.messages.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      segments: (m.segments || []).map((s: any) => {
        const segType = s.type || 'agent_text'
        if (segType === 'tool_start' || segType === 'tool_result') {
          const toolName = (s.data?.tool as string) || s.content || ''
          const label = TOOL_LABELS[toolName] || toolName
          return {
            type: segType,
            content: segType === 'tool_start' ? `${label}...` : `${label} 完成`,
            data: s.data,
          }
        }
        return { type: segType, content: s.content || '', data: s.data }
      }),
      timestamp: m.timestamp,
    }))
    setAiMessages(loaded)
  } catch {
    setAiMessages([])
  }
  setHistoryOpen(false)
}
```

- [ ] **Step 3: 在 Header 区域添加「历史」和「新会话」按钮**

找到 Header 的 `<div className="px-3 py-2.5 border-b border-gray-100 flex items-center gap-2">` 部分，在阶段标签之后、状态指示器之前插入：

```tsx
<button
  onClick={() => setHistoryOpen(true)}
  disabled={isAgentSending}
  className={cn(
    'flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] transition-colors',
    isAgentSending
      ? 'text-muted-foreground/40 cursor-not-allowed'
      : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
  )}
  title={isAgentSending ? '请等待回复完成' : '会话历史'}
>
  <History className="h-3 w-3" />
  <span>历史</span>
</button>
<button
  onClick={handleNewConversation}
  disabled={isAgentSending}
  className={cn(
    'flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] transition-colors',
    isAgentSending
      ? 'text-primary/40 cursor-not-allowed'
      : 'text-primary hover:bg-primary/10'
  )}
  title={isAgentSending ? '请等待回复完成' : '新建会话'}
>
  <Plus className="h-3 w-3" />
  <span>新会话</span>
</button>
```

- [ ] **Step 4: 在组件 JSX 末尾添加 ConversationHistoryDialog**

在 `AgentChatPanel` 的 return 最外层添加：

```tsx
<ConversationHistoryDialog
  open={historyOpen}
  onOpenChange={setHistoryOpen}
  onSwitchConversation={handleSwitchConversation}
  isAgentSending={isAgentSending}
/>
```

- [ ] **Step 5: 修改会话加载逻辑，同步 activeConversationId**

在现有的 `useEffect` 中加载后端聊天记录的地方，加载成功后同步 `activeConversationId`：

```tsx
// 在 fetchConversation(currentProjectId).then((res) => { ... }) 内部
setActiveConversationId(Number(res.conversation_id))
```

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/workbench/AgentChatPanel.tsx
git commit -m "frontend(agent): integrate conversation management buttons and history dialog"
```

---

### Task 7: 端到端验证

**Files:** 无新文件

- [ ] **Step 1: 重建后端并启动**

```bash
cd /Users/biner/Dev/novelagent && docker compose build --no-cache backend && docker compose up -d backend
```

- [ ] **Step 2: 执行数据库迁移**

```bash
docker exec novelagent-backend-1 alembic upgrade head
```

验证：现有会话的 `is_active` 应为 `true`。

- [ ] **Step 3: 验证后端 API**

手动测试以下场景：
- `GET /conversations` — 列出会话
- `POST /conversations` — 新建会话，确认旧会话 `is_active` 变为 false
- `PUT /conversations/{id}` — 重命名，传空标题应返回 422，传超长标题应返回 422
- `POST /conversations/{id}/activate` — 切换会话
- `DELETE /conversations/{id}` — 删除非活跃会话
- `DELETE /conversations/{active_id}` — 应返回 400
- `POST /chat` — 确认消息写入当前活跃会话，thread_id 包含 conversation_id
- 连续创建 20 条会话后再创建，应返回 400

- [ ] **Step 4: 重建前端并启动**

```bash
cd /Users/biner/Dev/novelagent && docker compose build --no-cache frontend && docker compose up -d frontend
```

- [ ] **Step 5: 前端功能验证**

- Agent 侧边栏 Header 显示「历史」和「新会话」按钮
- 点击「新会话」，消息列表清空、新建成功
- 在新会话中发送消息，标题自动生成（前20字）
- 点击「历史」，弹窗显示会话列表
- 点击旧会话切换，消息正确加载
- 重命名会话（空标题时确认按钮禁用）
- 删除非当前会话，二次确认弹窗出现
- 生成中「历史」和「新会话」按钮禁用
- 切换会话后发送消息，确认 thread_id 隔离（不同会话的 Agent 上下文不串扰）

- [ ] **Step 6: 最终提交**

如有修复则提交，否则跳过。
