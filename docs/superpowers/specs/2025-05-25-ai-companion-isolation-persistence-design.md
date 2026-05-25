# AI 搭档项目隔离与对话持久化 — 设计文档

## 元信息

- 日期：2025-05-25
- 状态：待审查
- 版本：v1

## 问题

1. AI 搭档跨项目共享状态，切换项目不清空消息
2. 对话记录仅存内存，刷新丢失

## 根因

- `workbenchStore.aiMessages` 全局共享，无项目 ID 隔离
- `ProjectWorkbench` 切换项目时不清理
- 无任何持久化（localStorage / DB 皆无）

## 设计

### 1. 数据模型

新建两张表：

```sql
CREATE TABLE agent_conversations (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(200) DEFAULT '',
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE agent_messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES agent_conversations(id) ON DELETE CASCADE,
    role VARCHAR(10) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL DEFAULT '',
    segments JSONB DEFAULT '[]',
    actions JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_agent_messages_conv ON agent_messages(conversation_id, created_at);
CREATE UNIQUE INDEX idx_agent_conversations_project ON agent_conversations(project_id);
```

每个项目只能有一个会话（单会话模型），通过 unique index 保证。

### 2. API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/projects/{id}/agent/conversation` | GET | 获取会话 + 消息。不存在则自动创建。`?limit=50&before_id=N` 游标翻页 |
| `/api/projects/{id}/agent/conversation` | DELETE | 清空会话的所有消息（不删 conversation 记录） |

消息保存不通过独立 API — 由后端在 `agent_chat` 内部自动完成：
- 请求到达时 → 保存用户消息
- agent_done 后 → 保存 assistant 回复（segments + actions）
- 即使前端断开，消息也不丢失

### 3. 上下文管理与消息持久化

**发送流程：**

```
用户发消息
  │
  ├─ 后端：立即保存用户消息到 DB（失败不阻塞请求）
  │
  ├─ 后端拼装 messages 数组发给 LLM：
  │   ① build_project_context(max_tokens=12000) → 项目内容
  │   ② + 行为准则 + 页面上下文 → 完整 system prompt
  │   ③ system_used = estimate_tokens(system_prompt)
  │   ④ 读取 model_config.context_window，NULL 时查默认映射
  │   ⑤ history_budget = context_window × 0.7 - system_used
  │   ⑥ 从 history（前端传）最新往前累加 token，≤ history_budget 的都带上
  │   ⑦ messages = [system, ...截断后的 history, 当前 user]
  │
  ├─ 送入 LLM，SSE 流式返回（同现有逻辑）
  │
  └─ agent_done 后：保存 assistant 消息到 DB（segments + actions）
```

**加载流程：**

```
前端进入项目 → GET /conversation（不存在则自动创建）
  → 返回最近 50 条消息（created_at ASC）
  → 前端 setState 替换 aiMessages
  → 用户发新消息时 history 从 aiMessages 构造传给后端
```

**上下文窗口默认映射（model_config.context_window = NULL 时）：**

| 模型 | 窗口 |
|------|------|
| gpt-4o | 128000 |
| gpt-4o-mini | 128000 |
| claude-3.5-sonnet | 200000 |
| deepseek-v3 | 128000 |
| deepseek-r1 | 128000 |
| qwen-plus | 131072 |
| 其他未知 | 128000 |

### 4. 前端 Store 改动

`workbenchStore`：

```typescript
// 新增字段
currentProjectId: number | null

// 新增方法
setCurrentProjectId: (id) => {
  // id 变化时自动清空 + 加载新项目历史
  if (id !== currentProjectId) {
    clearAiMessages()
    if (id) loadConversation(id)
  }
  currentProjectId = id
}

loadConversation: async (projectId) => {
  const { messages } = await agentApi.fetchConversation(projectId)
  set({ aiMessages: messages })
}

clearConversation: async (projectId) => {
  await agentApi.clearConversation(projectId)
  set({ aiMessages: [] })
}
```

`agentApi.ts` 新增三个函数：

```typescript
fetchConversation(projectId, limit?, beforeId?)  // GET
deleteConversation(projectId)                       // DELETE
```

### 5. 前端类型修复

`ModelConfig` 加 `context_window`：

```typescript
export interface ModelConfig {
  // ... existing fields
  context_window?: number  // 新增
}
```

## 改动范围

### 后端

| 文件 | 改动 |
|------|------|
| `backend/app/models/agent_conversation.py` | **新建** — AgentConversation + AgentMessage 两个 SQLAlchemy model |
| `backend/app/api/agent.py` | 2 个新端点 + `agent_chat` 增加消息自动保存 + context_window 截断 |
| `backend/app/agents/agent_context.py` | 新增 `get_context_window` 导出函数 |
| Alembic migration | **新建** — 建表 |

### 前端

| 文件 | 改动 |
|------|------|
| `frontend/src/stores/workbenchStore.ts` | currentProjectId + loadConversation + clearConversation |
| `frontend/src/lib/agentApi.ts` | fetchConversation + deleteConversation |
| `frontend/src/components/workbench/AICompanionSidebar.tsx` | useEffect 加载历史 + 清空按钮 + history 来源改为 store |
| `frontend/src/pages/ProjectWorkbench.tsx` | useEffect 调用 setCurrentProjectId |
| `frontend/src/types/index.ts` | ModelConfig 加 context_window |

### 不改动

| 文件 | 原因 |
|------|------|
| `AICompanionChat.tsx` | 消息渲染逻辑不变 |
| `AICompanionInput.tsx` | 输入逻辑不变 |
| `agent_graph.py` | Agent 图逻辑不变 |
| `build_project_context` | 已有 BudgetTracker，不变 |

## 错误处理

| 场景 | 处理 |
|------|------|
| 保存用户消息失败 | 静默失败，不阻塞请求 |
| 保存 assistant 消息失败 | `logger.error` 记录，不向用户暴露 |
| 加载历史消息失败 | `aiMessages = []`，用户看到空对话 |
| context_window 为 NULL 且模型名未知 | 使用 128000 |
| 并发锁 | 维持现有 5 分钟 busy lock |

## 测试要点

1. 切换项目后清空旧消息 + 加载新项目历史
2. 发消息后刷新页面，对话仍存在
3. 清空对话后 DB 记录被删除，刷新后为空
4. 长对话 token 截断不报错
5. context_window 从模型配置正确读取
6. 未配置 context_window 的模型使用默认映射

## 不在范围内

- 上下文摘要压缩（v2 预留）
- 多会话支持
- 消息编辑/删除单条
- 对话导出
