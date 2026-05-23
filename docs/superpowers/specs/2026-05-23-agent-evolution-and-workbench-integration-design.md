# Agent 模式深化 + 工作台融合设计

> 日期：2026-05-23
> 状态：草案
> 范围：补全 Agent tools + Agent 深度融入工作台 + 交互体验优化
> 前置：feature/ai-companion-workbench-redesign 基础框架

---

## 1. 架构决策

### Agent 为主，Workflow 降级

Agent tools 是核心代码路径。Workflow 模式不再维护独立的 LangGraph 节点代码，改为"预设的 tool 调用序列"编排。

```
当前：                          目标：
LangGraph 节点（独立实现）  →   services/ 共享能力层
Agent tools（独立实现）     →   tools 是核心，workflow 是编排
两套代码各自维护              →   单一代码路径
```

共享能力层（services/）是唯一实现。Agent tools 调 services，Workflow 模式编排 tool 序列。

---

## 2. 补全 Agent Tools

### 新增 5 个 tools

| Tool | 类型 | 说明 |
|------|------|------|
| `read_relations` | 读 | 读取项目人物关系，返回关系列表 |
| `update_relations` | 写 | 修改人物关系（类型、信任度、状态、方向） |
| `generate_chapter_content` | 生成（流式） | 生成章节正文，在聊天中流式输出，同时写 DB |
| `review_chapter` | 审核（轻量） | 审核章节，返回结构化结果，在聊天中展示为卡片 |
| `rewrite_chapter` | 生成（流式） | 根据审核意见重写章节，在聊天中流式输出 |

### 生成类 tool 的 SSE 流式方案

`generate_chapter_content` 和 `rewrite_chapter` 输出完整章节（3000+ 字），需要流式展示在 AI 聊天中。

**技术机制：** ReAct agent 的 tool 是同步函数，无法直接 yield SSE 事件。解决方案：
- 在 `AgentChatRequest` 请求进入时，创建一个 `asyncio.Queue` 作为 side channel
- 将该 queue 注入到 tool 的上下文（通过 state 或闭包）
- Tool 内部调用 LLM 流式生成时，每个 chunk 同时 push 到 queue
- SSE 端点用 `asyncio.wait` 同时监听 agent astream 和 side channel queue，将两者的事件交织发送

**SSE 事件设计：**
- `agent_text` — Agent 的文本回复（LLM 思考输出，已有事件）
- `chunk` — 章节正文内容流（复用现有事件类型，tool 内 LLM 生成的内容）

前端通过事件类型区分：`agent_text` 渲染为普通聊天文本，`chunk` 渲染为章节正文（带格式，可折叠）。同一消息中两种事件按到达顺序交织展示。

**生成完成后：** 内容自动写入 DB（Chapter 表），WritingPanel 可查看/编辑。

### 审核 tool 的轻量方案

`review_chapter` 调用 LLM 审核，返回结构化结果：

```python
{
    "passed": bool,
    "scores": {"plot": 8, "character": 7, ...},
    "issues": [{"type": "逻辑", "location": "第3段", "description": "..."}],
    "suggestions": "整体建议..."
}
```

前端在聊天中渲染为审核结果卡片（passed 绿色/未通过 红色），用户可直接在聊天中讨论审核结果。

### Tool 可视化：可展开详情

每个 tool 操作默认显示名称 + 状态，点击展开显示：
- **输入参数**：tool 被调用时传入的 JSON（脱敏后）
- **返回结果**：tool 执行后的输出

写操作 tool 的返回结果需包含修改摘要（如"标题从 A 改为 B"），便于用户在展开时看到变更。

---

## 3. Agent 深度融入工作台

### 3.1 模型选择器

AI 侧栏 header 右侧（"在线"标记旁）增加模型下拉菜单：

- 复用现有 `modelConfigsApi.list()` 获取模型配置列表
- 扁平化展示所有 healthy 模型（与 InspirationPanel 逻辑一致）
- 选择后存储到 `workbenchStore.selectedModelKey`
- 发送消息时通过 `model_config_id` 传给后端

### 3.2 Prompt 系统

MVP 阶段 Agent system prompt 保持硬编码在 `agent.py`。后续迭代接入 `system_prompts` 表。

### 3.3 并发控制

**`project` 表新增字段：**

```python
is_busy: bool = False        # 是否有操作正在执行
busy_since: datetime = None  # 锁定开始时间
busy_by: str = None          # "agent" | "workflow"
```

**加锁逻辑：**
- Agent 发送消息前 → 检查 `is_busy`，如锁已过期（>5分钟）则抢占，否则拒绝
- Workflow 运行前 → 同样检查
- 操作完成后（done/error 事件）→ 释放锁

**前端配合：**
- Agent 执行中 → Workflow 运行按钮禁用，显示"Agent 工作中"
- Workflow 运行中 → Agent 输入框禁用，显示"工作流运行中"
- 通过 SSE 的 `done`/`error`/`waiting` 事件判断是否释放

### 3.4 操作回滚

MVP 阶段暂不实现。用户可通过手动编辑或 Agent 再次修改恢复。后续版本通过写前 snapshot 实现。

---

## 4. 交互体验优化

### 4.1 Context 自动刷新

每次用户发送消息时，后端 `build_project_context()` 重新从 DB 读取最新数据（outline、characters、chapter_outlines），确保 Agent 始终看到最新的项目状态。

前端不做改动——用户在左侧面板的任何修改都会在下次对话时被 Agent 感知。

### 4.2 Tool 展开详情

见 2. 中的 Tool 可视化设计。

### 4.3 快捷指令

MVP 阶段暂不实现。

---

## 5. 前端改动清单

### 新增/修改文件

| 文件 | 改动 |
|------|------|
| `AICompanionSidebar.tsx` | 新增模型选择器（header dropdown）；`handleSend` 传递 `modelConfigId`；并发控制：`disabled` 逻辑优化 |
| `AICompanionChat.tsx` | 支持混合内容消息渲染：每条消息内按事件到达顺序渲染 `agent_text`（普通文本）和 `chunk`（章节正文，可折叠）；支持 tool 操作展开/折叠 |
| `AIActionCard.tsx` | 改为可展开，显示 tool 参数和返回结果 |
| `stores/workbenchStore.ts` | 新增 `isAgentBusy`、`isWorkflowBusy` 状态；`AiMessage` 类型支持混合内容（`segments: Array<{type: 'agent_text' \| 'chunk', content: string}>`），兼容旧 `content` 字段 |
| `lib/agentApi.ts` | `chunk` 事件处理：按到达顺序追加到当前消息的 segments 数组，区分 `agent_text` 和 `chunk` 两种类型；新增 `modelConfigId` 参数传递 |

### 不修改

- Workflow 相关页面和组件（保持现有行为）
- Settings 页面
- InspirationPanel

---

## 6. 后端改动清单

### 新增文件

| 文件 | 职责 |
|------|------|
| `backend/app/agents/services/outline_service.py` | 大纲读写操作（从 agent_tools 抽出） |
| `backend/app/agents/services/chapter_service.py` | 章节生成/审核/重写的核心逻辑 |
| `backend/app/agents/services/character_service.py` | 角色 CRUD |
| `backend/app/agents/services/relation_service.py` | 关系读写 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `agent_tools.py` | 新增 5 个 tools；读/写类 tool 改为调 services/；生成类 tool 接收 side channel queue 实现流式输出 |
| `agent.py` | 并发控制：加锁/释放逻辑；每次 `agent_chat` 前检查 `is_busy`；创建 side channel queue 并注入 tool context，SSE 端点同时监听 agent stream 和 queue |
| `models/project.py` | 新增 `is_busy`、`busy_since`、`busy_by` 字段 |
| `sse_events.py` | 无需改动（`chunk` 事件已存在，复用） |

### 数据库迁移

```sql
ALTER TABLE projects ADD COLUMN is_busy BOOLEAN DEFAULT FALSE;
ALTER TABLE projects ADD COLUMN busy_since TIMESTAMP;
ALTER TABLE projects ADD COLUMN busy_by VARCHAR(20);
```

---

## 7. 不在本设计范围内

- Workflow 节点重构为 tool 编排（后续单独设计）
- Agent 操作回滚/版本控制
- Agent 聊天历史持久化（当前仍由前端管理，刷新丢失）
- 快捷指令（`/` 触发）
- Agent prompt 接入 system_prompts 表
- 多轮对话的上下文窗口管理策略

---

## 8. 设计决策记录

| 决策 | 选项 | 理由 |
|------|------|------|
| 架构方向 | Agent 为主，Workflow 降级 | 避免双轨维护，单一代码路径 |
| 生成类 tool | 聊天中流式输出 | 用户不需要切标签页就能看到 Agent 工作成果 |
| 审核 tool | 轻量卡片 | 审核是元信息，卡片展示更高效 |
| 并发控制 | 乐观锁 + 5分钟超时 | 兼顾安全性和进程崩溃容错 |
| 模型选择器 | AI 侧栏 header 下拉框 | 简洁，与 Agent 绑定明确 |
| Tool 可视化 | 可展开详情 | 透明度够，成本低，可升级 diff |
| Context 感知 | 发送前自动刷新 | 零 UI 成本，DB 查询几乎无感 |
| Prompt 系统 | MVP 硬编码 | 先跑通能力，再优化配置 |
| 快捷指令 | 暂不做 | 自然语言已覆盖主要场景 |
| 操作回滚 | 暂不做 | MVP 可通过手动编辑恢复 |
