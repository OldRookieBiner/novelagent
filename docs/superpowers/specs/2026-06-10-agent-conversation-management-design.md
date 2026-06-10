# Agent 多会话管理设计

## 背景

当前 Agent 侧边栏每个项目仅支持一个会话，用户无法隔离不同话题的讨论、在上下文过长时清理历史、或探索不同创意方向而不影响已有对话。需要新增多会话管理能力。

## 需求决策

| 决策项 | 结论 |
|--------|------|
| 动机 | 话题隔离 + 上下文清理 + 实验探索 |
| 会话关系 | 消息独立，共享知识库（大纲、人物、世界观等） |
| 数量限制 | 软限制 20 条，超出拒绝创建并提示 |
| 历史传递 | Agent 仅接收当前激活会话的对话历史 |
| UI 布局 | Header 区域加「📋历史」+「＋新会话」按钮，历史弹窗管理切换/删除/重命名 |
| 新建行为 | 当前会话自动保存，新会话立即激活 |
| 标题规则 | 首条用户消息前 20 字，用户可手动重命名（最长 50 字） |
| 生成中切换 | 禁止，等待回复完成或终止后才可操作 |
| 消息加载 | 分页加载，最近 50 条，向上滚动加载更多 |

## 数据模型变更

### AgentConversation 表

- **移除 `project_id` 的 unique 约束** — 允许同一项目创建多个会话
- **新增 `is_active` 布尔字段** — 标记当前激活会话，每个项目最多一条为 true
- **标题规则** — `title` 默认取首条用户消息前 20 字，用户可手动重命名（最长 50 字）
- **软限制** — 后端在创建会话时检查数量，超过 20 条返回提示

### AgentMessage 表

无任何改动。现有 `conversation_id` 外键天然指向不同的会话记录。

### Project 模型 relationship 变更

- 保持 `agent_conversation` 名称不变（不改名），仅将 `uselist` 改为 `True`。原因：AgentConversation 中的 `back_populates="agent_conversation"` 必须与 Project 侧 relationship 名字匹配

- `agent_conversation`（单数）重命名为 `agent_conversations`（复数），`uselist` 改为 `True`

### Alembic 迁移

- 移除 `agent_conversations_project_id_key` unique constraint
- 新增 `agent_conversations.is_active` 列（默认 false）
- 将现有记录的 `is_active` 设为 true（每个项目现有的一条会话自动成为活跃会话）

## 后端 API 变更

### 现有端点改动

| 端点 | 变更 |
|------|------|
| `GET /{project_id}/agent/conversation` | 新增可选 `conversation_id` query param。不传时返回当前激活会话的消息；传入时返回指定会话的消息（用于切换后显式加载） |
| `DELETE /{project_id}/agent/conversation` | 改为 `DELETE /{project_id}/agent/conversations/{conversation_id}`，不可删除当前激活会话 |
| `POST /{project_id}/agent/chat` | 向当前激活会话发送消息，内部函数改为 `_get_active_conversation`。LangGraph thread_id 改为 `f"agent-{project_id}-{conversation_id}"` 避免跨会话 checkpoint 串扰 |

### 新增端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/{project_id}/agent/conversations` | GET | 列出项目所有会话（用于历史弹窗） |
| `/{project_id}/agent/conversations` | POST | 新建会话。当前活跃会话 is_active 置 false，新会话置 true。需获取项目 busy lock 防止并发。超过 20 条返回 400 |
| `/{project_id}/agent/conversations/{conversation_id}` | PUT | 重命名会话，更新 title 字段。title 最长 50 字，Pydantic 校验 |
| `/{project_id}/agent/conversations/{conversation_id}/activate` | POST | 切换会话。需获取项目 busy lock。当前活跃会话 is_active 置 false，目标会话置 true。同一事务中原子执行 |
| `/{project_id}/agent/conversations/{conversation_id}` | DELETE | 删除指定会话及其消息（cascade）。不可删除当前激活会话。需获取项目 busy lock 防止并发 |

### 内部函数改动

- `_get_or_create_conversation` → `_get_active_conversation`：查询 `is_active=True` 的会话，找不到则创建
- `_save_user_message` / `_save_assistant_message`：使用自身 `SessionLocal()` 创建的 session 调用 `_get_active_conversation`，确保在同一 session 中操作
- `stream_agent_events`：thread_id 参数改为 `f"agent-{project_id}-{conversation_id}"`，需从 chat 端点传入 conversation_id

## LangGraph Checkpoint 管理

- **thread_id 格式**：`agent-{project_id}-{conversation_id}`，按会话隔离
- **删除会话时清理 checkpoint**：当前 LangGraph Agent 未配置 checkpointer（create_react_agent 未传入），因此删除会话时无法清理 checkpoint。如后续添加 checkpointer，需在 DELETE 端点中补充清理逻辑
- **新建会话**：无需特殊处理，LangGraph 会在首次 astream_events 时自动创建 checkpoint

## 并发安全

- **新建/激活/删除会话**：需要获取项目 busy lock（复用现有 `_acquire_busy_lock` / `_release_busy_lock`），防止在 Agent 正在生成时切换会话导致消息写入错误的 conversation
- **is_active 更新原子性**：在同一事务中先 `UPDATE ... SET is_active = False WHERE project_id = X` 再 `UPDATE target SET is_active = True`，无需 `SELECT FOR UPDATE`，因为 busy lock 保证了同一项目不会有两个并发请求修改 is_active

## 前端变更

### workbenchStore

- 新增 `activeConversationId: number | null` — 当前激活会话 ID
- `setCurrentProjectId` 切换项目时重置 `activeConversationId`
- `isAgentSending` 已有，UI 层根据此状态禁用操作按钮

### AgentChatPanel

- **Header 区域**：阶段标签右侧新增「📋历史」和「＋新会话」按钮，历史在左、新会话在右
- **新会话按钮**：调用 `POST /conversations`，成功后清空消息列表、更新 `activeConversationId`
- **历史按钮**：打开 `ConversationHistoryDialog` 弹窗
- **生成中禁用**：`isAgentSending=true` 时两个按钮禁用，tooltip 提示"请等待回复完成"

### ConversationHistoryDialog（新组件）

- **会话列表**：调用 `GET /conversations` 获取，每条显示标题 + 消息数 + 相对时间
- **当前会话**：高亮背景 + "当前"标签，右侧只有 ✏️ 重命名按钮（不可删除自己）
- **历史会话**：右侧有 ✏️ 重命名 + 🗑 删除按钮
- **切换**：点击标题调用 `POST /activate`，成功后用 `GET /conversation?conversation_id=X` 显式加载指定会话消息、更新 store
- **重命名**：点击 ✏️ 后标题变为输入框，右侧出现 ✓ 确认和 ✕ 取消，确认调用 `PUT /conversations/{id}`
- **删除**：点击 🗑 弹出 ConfirmDialog 二次确认，确认后调用 `DELETE /conversations/{id}`，成功刷新列表
- **分页加载**：切换会话时加载最近 50 条消息，向上滚动触发 `before_id` 分页加载
- **错误提示**：后端返回 400/404 时在弹窗内显示错误信息（toast 或 inline）

### agentApi.ts 新增

- `createConversation(projectId)` — POST 新建会话
- `fetchConversations(projectId)` — GET 会话列表
- `activateConversation(projectId, conversationId)` — POST 切换会话
- `renameConversation(projectId, conversationId, title)` — PUT 重命名
- `deleteConversation(projectId, conversationId)` — DELETE 删除（路径参数 `/{conversation_id}`）
- `fetchConversation` 修改：新增可选 `conversationId` 参数，传时加 `?conversation_id=X`
- `sendAgentMessage` 无需修改：后端 `POST /chat` 通过 `_get_active_conversation` 自动获取当前激活会话，前端无需显式传 conversation_id

## 错误处理与边界情况

1. **生成中操作** — `isAgentSending=true` 时新建/切换/删除按钮禁用。后端通过 busy lock 二次防护
2. **删除当前会话** — 前端隐藏删除按钮，后端校验返回 400
3. **会话数量超限** — 后端创建时检查 >= 20 条，返回 400 + 提示
4. **重命名过长** — Pydantic `Field(max_length=50)` 校验，超长返回 422
5. **重命名为空** — 前端输入框不允许提交空标题，确认按钮禁用；后端 `Field(min_length=1)` 校验
6. **切换到不存在/已删除的会话** — 后端返回 404，前端回退到上一个活跃会话
7. **并发切换/新建** — 通过 busy lock 保证同一项目同一时间只有一个会话管理操作
8. **项目首次使用** — 无会话时发送第一条消息自动创建（保持现有行为）
9. **删除会话的 checkpoint 清理** — 在 DELETE 端点中同步清理 LangGraph checkpoint
