# AGENTS.md

NovelAgent — AI 小说创作智能体系统的 Codex 工作指南。

## 项目概览

**NovelAgent v0.8.11** — AI 驱动的长篇小说创作系统。用户通过对话式创意孵化 → 结构设计 → 自动写作 → 修订的完整流程创作小说。后端基于 LangGraph 工作流，前端 React 工作台实时展示 SSE 流式输出。

> 注：`main.py` 中的 FastAPI version 字段为 `"0.7.0"`，实际版本以 CHANGELOG 为准。

**技术栈：**

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + Vite + TypeScript + shadcn/ui + Tailwind + TipTap + Zustand + @dnd-kit |
| 后端 | FastAPI + SQLAlchemy + PostgreSQL + LangGraph + LangChain |
| 数据库迁移 | Alembic |
| 部署 | Docker Compose（前端 3001、后端 8000、PostgreSQL 5432） |

---

## 架构

```
novelagent/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # pydantic-settings 配置
│   │   ├── database.py          # SQLAlchemy 引擎
│   │   ├── api/                 # REST + SSE 路由
│   │   │   ├── workflow.py      #   创作工作流（核心）
│   │   │   ├── workflow_compat.py # 旧版工作流兼容层（build_initial_state 旧格式）
│   │   │   ├── agent.py         #   自由操作 Agent（ReAct）
│   │   │   ├── chapters.py      #   章节 CRUD + 流式生成/审核
│   │   │   ├── characters.py    #   人物/关系 CRUD
│   │   │   ├── outline.py       #   大纲 CRUD + 流式生成
│   │   │   ├── knowledge.py     #   知识库查询（世界观、风格、情节块等）
│   │   │   ├── volumes.py       #   卷/弧 CRUD
│   │   │   ├── inspiration.py   #   灵感对话
│   │   │   ├── model_configs.py #   模型配置 + 连接测试
│   │   │   ├── settings.py      #   用户设置
│   │   │   ├── system_prompts.py#   Prompt 模板管理
│   │   │   ├── auth.py          #   认证
│   │   │   └── projects.py      #   项目 CRUD
│   │   ├── agents/              # LangGraph 智能体
│   │   │   ├── graph.py         #   创作工作流图定义（条件路由）
│   │   │   ├── agent_graph.py   #   自由操作 Agent（ReAct + 工具）
│   │   │   ├── state.py         #   NovelState 定义 + Phase/ConfirmationType/RevisionContext enum
│   │   │   ├── constants.py     #   禁用词、温度配置、风格示例、上下文窗口映射
│   │   │   ├── prompts.py       #   默认 prompt 模板
│   │   │   ├── sse_events.py    #   SSE 事件格式化（集中管理）
│   │   │   ├── token_budget.py  #   Token 预算计算
│   │   │   ├── context_strategy.py # 上下文构建策略
│   │   │   ├── checkpointer.py  #   LangGraph 检查点持久化
│   │   │   ├── agent_context.py #   Agent 上下文组装
│   │   │   ├── agent_tools.py   #   认知工具（感知/修改/创作辅助）
│   │   │   ├── tool_context.py  #   工具上下文（project_id 注入）
│   │   │   ├── nodes/           #   工作流节点（26 个注册 + 7 个旧版兼容）
│   │   │   └── services/        #   Agent 服务层
│   │   │       ├── knowledge_base.py # 知识库读写（所有节点共享）
│   │   │       ├── retrieval.py      # 语义检索（FAISS + BM25）
│   │   │       ├── chapter_service.py
│   │   │       ├── character_service.py
│   │   │       ├── edit_service.py
│   │   │       ├── inspiration_service.py
│   │   │       ├── outline_service.py
│   │   │       ├── relation_service.py
│   │   │       └── warning.py
│   │   ├── models/              # SQLAlchemy 模型（22 个表）
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── services/            # 业务服务
│   │   │   ├── llm.py           #   LLM 服务（多 provider、重试、截断检测）
│   │   │   ├── model_providers.py
│   │   │   ├── crypto.py        #   API Key AES 加密
│   │   │   ├── prompt_loader.py #   自定义 prompt 加载
│   │   │   ├── workflow_orchestrator.py # 旧版 SSE 编排器（chapters/outline 兼容层使用）
│   │   │   ├── chapter_service.py
│   │   │   └── outline_service.py
│   │   └── utils/               # 工具函数
│   ├── alembic/                 # 数据库迁移
│   ├── tests/                   # pytest 测试
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── pages/               # Login, Home, Settings, ProjectWorkbench
│       ├── components/
│       │   ├── workbench/       # 工作台核心
│       │   │   ├── TabNavigation.tsx      # 4 标签页：写作/知识库/结构/追踪
│       │   │   ├── WorkbenchLayout.tsx
│       │   │   ├── AgentChatPanel.tsx     # 自由操作 Agent 侧边栏
│       │   │   ├── VolumePanel.tsx
│       │   │   ├── creation/              # 写作标签页组件
│       │   │   ├── knowledge/             # 知识库标签页
│       │   │   ├── structure/             # 结构标签页
│       │   │   └── tracking/              # 追踪标签页
│       │   ├── character/       # 人物组件
│       │   ├── settings/        # 设置页面组件
│       │   ├── common/          # 通用组件（TipTapEditor, ConfirmDialog 等）
│       │   ├── layout/          # Header, Layout
│       │   └── ui/              # shadcn/ui 基础组件
│       ├── stores/              # Zustand 状态（workbench, workflow, auth, settings, project）
│       ├── lib/                 # API 客户端、SSE 解析、工具
│       │   ├── api.ts           #   基础 API 客户端
│       │   ├── workflowApi.ts   #   工作流 SSE 流
│       │   ├── agentApi.ts      #   Agent 聊天 SSE 流
│       │   ├── characterApi.ts
│       │   ├── sseParser.ts     #   SSE 事件解析
│       │   └── inspiration/     #   灵感对话配置
│       ├── hooks/               # 自定义 hooks
│       └── types/               # TypeScript 类型
└── docker-compose.yml
```

---

## LangGraph 工作流架构（强制约束）

**LangGraph 是本项目的核心工作流框架。所有 AI 生成流程必须作为 LangGraph 节点实现。**

### 创作阶段（Phase enum）

```
INCUBATION → STRUCTURE → WRITING → REVISION
```

| 阶段 | 说明 | 包含节点 |
|------|------|----------|
| INCUBATION | 创意孵化 + 知识库初建 | inspiration_dialogue, story_seed, outline_generation, character_generation, relation_generation, world_setting, style_setup, foreshadowing_plan |
| STRUCTURE | 逆向规划 + 结构设计 | question_chain, plot_blocks, subplot_network, rhythm_curve, chapter_count_estimate |
| WRITING | 感知→决策→执行→自检循环 | context_assembly → chapter_planning → chapter_writing → character_consistency → tracking_update → style_check → scene_update → post_write_summary |
| REVISION | 全书/逐卷修订 | structural_review → character_arc_review → final_polish |

**旧版兼容节点**（文件存在但未注册到主图）：`arc_outline_generation`、`chapter_generation`、`chapter_summary`、`review`、`rewrite`、`volume_arc_planning`、`wait_confirm`。这些被旧版 API 端点（chapters.py、outline.py）通过 WorkflowOrchestrator 调用。

### 两个 Agent

| Agent | 图定义 | 用途 |
|-------|--------|------|
| 创作工作流 | `agents/graph.py`（StateGraph） | 主线写作流程，条件路由，human-in-the-loop |
| 自由操作 Agent | `agents/agent_graph.py`（create_react_agent） | 用户对话式查询/修改知识库，认知工具驱动 |

### 状态管理

- **NovelState**（`agents/state.py`）— 只存流程控制 + ID 引用，不缓存 DB 数据
- **KnowledgeBaseService**（`agents/services/knowledge_base.py`）— 所有节点共享的知识库读写层，每个 API 内部创建独立 DB session
- **Phase enum** 替代旧的 `STAGE_*` 字符串常量
- **ConfirmationType enum** 类型安全的确认类型

> **注意：旧版 `STAGE_*` 常量仍存在** — `state.py` 底部保留了兼容别名（如 `STAGE_INSPIRATION = Phase.INCUBATION.value`），且 `chapters.py`、`outline.py`、`arc_outline_generation.py`、`volume_arc_planning.py` 等文件仍在引用。开发时需注意两套常量并存。

### 写后自检与卷过渡

- 写后自检拆分为 5 个独立节点：character_consistency → tracking_update → style_check → scene_update → post_write_summary
- 每 5 章触发 deep_review（条件路由）
- 卷过渡（volume_transition）负责数据交接：快照、跨卷追踪、索引重建
- 逐卷修订：structural_review → character_arc_review → final_polish
- 全书完成后进入全书修订链，最终到 END

### 并发控制

Project 模型有 busy lock 机制（`is_busy`、`busy_since`、`busy_by` 字段），防止 Agent 和工作流同时操作同一项目。Agent API 通过 `_acquire_busy_lock` 获取锁，超时 300 秒自动释放。

### 禁止行为

- **禁止** 直接在 API 路由中调用 LLM 服务 — 必须通过 LangGraph 节点
- **禁止** 绕过 StateGraph 实现新的 AI 生成流程
- **禁止** 在节点外部管理工作流状态
- **禁止** 在 state 中缓存 DB 业务数据 — 使用 KnowledgeBaseService 实时读取

---

## SSE 事件体系

所有 SSE 事件通过 `agents/sse_events.py` 集中格式化：

**工作流事件：**

| 事件 | 用途 | 来源 |
|------|------|------|
| `node_start` | 节点开始 | workflow.py |
| `node_done` | 节点完成 | workflow.py |
| `chunk` | LLM 流式文本 | workflow.py, chapters.py |
| `waiting` | 等待确认（含 confirmation_type） | workflow.py |
| `done` | 操作完成 | workflow.py |
| `error` | 错误 | 所有 SSE 端点 |
| `heartbeat` | 保活心跳（15s 间隔） | workflow.py |
| `progress` | 进度数据 | chapters.py |
| `volume_transition` | 卷过渡 | workflow.py |
| `volume_review` | 逐卷修订报告 | workflow.py |
| `revision_report` | 全书修订报告 | workflow.py |

**Agent 事件：**

| 事件 | 用途 | 来源 |
|------|------|------|
| `agent_text` | Agent 文本输出（chunk 的别名） | agent.py |
| `agent_tool_start` | 工具调用开始 | agent.py |
| `agent_tool_result` | 工具调用结果 | agent.py |
| `agent_review` | Agent 审查输出 | agent.py |
| `impact_assessment` | 变更影响评估报告 | agent.py |
| `warning` | 预警（伏笔逾期、风格漂移等） | agent.py |

前端 SSE 解析器：`frontend/src/lib/sseParser.ts`

---

## 关键文件入口

| 文件 | 说明 |
|------|------|
| `backend/app/main.py` | FastAPI 应用入口、路由注册、中间件 |
| `backend/app/agents/graph.py` | 创作工作流图定义、条件路由 |
| `backend/app/agents/agent_graph.py` | 自由操作 Agent（ReAct） |
| `backend/app/agents/state.py` | NovelState 定义、Phase/ConfirmationType/RevisionContext enum |
| `backend/app/agents/constants.py` | 禁用词、温度配置、风格示例、上下文窗口映射 |
| `backend/app/agents/sse_events.py` | SSE 事件格式化工具 |
| `backend/app/agents/token_budget.py` | Token 预算计算（三级策略） |
| `backend/app/agents/context_strategy.py` | 上下文构建策略（摘要/弧线/混合） |
| `backend/app/agents/agent_tools.py` | 认知工具定义（感知/修改/创作辅助） |
| `backend/app/agents/tool_context.py` | 工具上下文（project_id 注入） |
| `backend/app/agents/services/knowledge_base.py` | 知识库读写（所有节点共享） |
| `backend/app/api/workflow.py` | 工作流 API + stream_workflow_events + build_initial_state |
| `backend/app/api/workflow_compat.py` | 旧版工作流兼容层（旧格式 build_initial_state） |
| `backend/app/api/agent.py` | 自由操作 Agent API + 影响评估 |
| `backend/app/services/llm.py` | LLM 服务（多 provider、重试、截断检测） |
| `backend/app/services/workflow_orchestrator.py` | 旧版 SSE 编排器（chapters/outline 兼容层使用） |
| `frontend/src/lib/workflowApi.ts` | 工作流 SSE 流式客户端 |
| `frontend/src/lib/agentApi.ts` | Agent 聊天 SSE 流式客户端 |
| `frontend/src/lib/sseParser.ts` | SSE 事件解析器 |
| `frontend/src/stores/workbenchStore.ts` | 工作台核心状态（Zustand） |

---

## 常用命令

```bash
# 启动服务
docker compose up -d

# 停止服务
docker compose down

# 查看后端日志
docker compose logs backend -f

# 重启后端
docker compose restart backend

# 重建后端
docker compose build --no-cache backend && docker compose up -d backend

# 重建前端
docker compose build --no-cache frontend && docker compose up -d frontend

# 后端测试
docker exec novelagent-backend-1 pytest -v
docker exec novelagent-backend-1 pytest tests/test_workflow.py -v
docker exec novelagent-backend-1 pytest tests/ -k "test_build_initial" -v

# 前端测试
cd frontend && npm run test:run
cd frontend && npm run test:run -- src/stores/workbenchStore.test.ts
cd frontend && npm run test:coverage

# 数据库迁移
docker exec novelagent-backend-1 alembic upgrade head
docker exec novelagent-backend-1 alembic revision -m "description"
```

---

## Docker 操作安全约束

**原则：本项目容器自由操作，项目外容器需确认。**

- 安全：`docker compose up/down/restart/build/logs`
- 危险（需确认）：`docker stop/rm $(docker ps -aq)`、`docker system prune -af`、`docker volume prune`
- `docker compose down -v` 会删除数据库数据
- 历史教训：曾误执行 `docker stop $(docker ps -aq)` 删除了服务器上所有容器

---

## 后端陷阱

### LLM 服务优先级

用户模型配置（`model_configs` 表，API Key AES 加密）优先，回退到用户设置：
```python
from app.utils.llm import resolve_llm_service
```

### SSE 端点 DB Session 独立性

长 SSE 流使用 `SessionLocal()` 创建独立 Session，不要在 SSE 生成器内部使用 FastAPI 依赖注入的 `db: Session`。

### KnowledgeBaseService Session 管理

每个 API 内部创建独立 DB session，操作完成后立即关闭。LangGraph 节点无需管理 session 生命周期。返回的 ORM 对象在 session 关闭后为 detached 状态，不应再访问 lazy-loaded 关系。

### WorkflowOrchestrator 兼容层

旧版 API（`chapters.py`、`outline.py`）仍通过 `WorkflowOrchestrator` 执行 SSE 流式生成。新创作工作流（`workflow.py`）使用 `stream_workflow_events` 直接与 LangGraph 交互。修改旧版端点时注意两条路径的差别。

### Token 预算与上下文窗口

三级策略：DB 配置 > 硬编码映射（`MODEL_CONTEXT_WINDOWS`）> 默认值（32K）。`token_budget.py` 的 `estimate_tokens` 对中文按 2 token/字保守估算。

### LLM 截断检测

`chat_stream()` 检测 `finish_reason="length"` 并记录警告。出现时需增大 max_tokens。

### 节点温度配置

`constants.py` 中 `NODE_TEMPERATURES` 定义了各节点温度。创意任务（0.7-0.8）、分析/审核任务（0.2-0.3）。

### 旧版 STAGE_* 常量

`state.py` 底部保留了兼容别名（`STAGE_INSPIRATION`、`STAGE_OUTLINE` 等），映射到 Phase enum 值。部分旧版文件仍引用这些常量。新代码应使用 `Phase` enum。

---

## 前端陷阱

### SSE 流式中断处理

使用 `AbortController` 取消流式请求。`createSSEStream` 收到 `done` 事件后立即退出循环，避免后续网络断开误报 error。

### TipTap 纯文本内容转换

`setContent()` 不会自动将 `\n` 转为 `<p>` 标签：
```typescript
const html = text.split('\n').filter(p => p.trim()).map(p => `<p>${p}</p>`).join('')
editor.commands.setContent(html)
```

### shadcn/ui Button + Link 嵌套

```tsx
// 正确
<Button asChild><Link to="/path">文本</Link></Button>
```

### lucide-react 图标

统一使用 `lucide-react` 图标库，避免内联 SVG。

---

## 代码风格

- **注释**：中文注释
- **括号**：大括号独占一行（Allman 风格）
- **命名**：前端 camelCase，后端 snake_case，类/组件/类型 PascalCase
- **语言**：使用中文交流和回答

---

## Git 规范

| 类型 | 格式 | 示例 |
|------|------|------|
| 功能 | `feature/<name>` | `feature/multi-model` |
| 修复 | `fix/<name>` | `fix/login-error` |
| 重构 | `refactor/<name>` | `refactor/workflow` |

提交信息格式：`<type>(<scope>): <subject>`，scope: api | frontend | workflow | db

---

## API 端点汇总

| 模块 | 前缀 | 说明 |
|------|------|------|
| 认证 | `/api/auth` | 登录、登出、当前用户 |
| 项目 | `/api/projects` | 项目 CRUD |
| 大纲 | `/api/projects/{id}/outline` | 大纲 CRUD、流式生成 |
| 章节 | `/api/projects/{id}/chapters` | 章节 CRUD、流式生成/审核 |
| 人物 | `/api/projects/{id}/characters` | 人物/关系 CRUD |
| 卷/弧 | `/api/projects/{id}/volumes` | 卷弧 CRUD |
| 知识库 | `/api/projects/{id}/world-setting` | 世界观查询/更新 |
| 知识库 | `/api/projects/{id}/style-constraints` | 风格约束查询/更新 |
| 知识库 | `/api/projects/{id}/plot-blocks` | 情节块查询 |
| 知识库 | `/api/projects/{id}/foreshadowings` | 伏笔查询 |
| 知识库 | `/api/projects/{id}/timeline` | 时间线查询 |
| 知识库 | `/api/projects/{id}/style-snapshots` | 风格快照查询 |
| 设置 | `/api/settings` | 用户设置读写 |
| 模型 | `/api/model_configs` | 模型配置 CRUD、连接测试 |
| 提示词 | `/api/system/prompts` | Prompt 模板管理 |
| 灵感 | `/api/projects/{id}/inspiration` | 灵感对话 |

### 工作流 API

```
POST /api/projects/{id}/workflow/run     # 启动创作工作流（SSE）
POST /api/projects/{id}/workflow/confirm # 确认当前节点（可携带修改数据）
GET  /api/projects/{id}/workflow/state   # 获取工作流状态
POST /api/projects/{id}/workflow/cancel  # 取消工作流（删除检查点）
POST /api/projects/{id}/workflow/replan  # 重新规划（清追踪数据，保留大纲）
PUT  /api/projects/{id}/workflow/stage   # 手动切换阶段
POST /api/projects/{id}/workflow/cleanup # 清理检查点
```

### Agent API

```
POST   /api/projects/{id}/agent/chat            # Agent 对话（SSE）
POST   /api/projects/{id}/agent/impact-decision # 影响评估决策（proceed/adjust/abandon）
GET    /api/projects/{id}/agent/conversation    # 获取 Agent 对话历史
DELETE /api/projects/{id}/agent/conversation    # 清空 Agent 对话
```

---

## 前端页面结构

```
/                       → 首页（项目列表）
/login                  → 登录页
/project/:id/workbench → 工作台（4 标签页：写作/知识库/结构/追踪 + Agent 侧边栏）
/project/:id            → 重定向到 workbench
/settings               → 设置
```

---

## 工作原则

| 原则 | 说明 |
|------|------|
| 先讨论后实现 | 目标不清晰时停下来 |
| 推荐最短路径 | 直接建议更好的办法 |
| 追查根因 | 不打补丁，解决根本问题 |
| 输出精简 | 说重点，不废话 |
| 先跑通再优化 | 功能正确优先于性能优化 |

---

## CodeGraph

This project has a CodeGraph MCP server (`codegraph_*` tools) configured. CodeGraph is a tree-sitter-parsed knowledge graph of every symbol, edge, and file.

### When to prefer codegraph over native search

Use codegraph for **structural** questions. Use native grep/read only for **literal text** queries.

| Question | Tool |
|---|---|
| "Where is X defined?" | `codegraph_search` |
| "What calls Y?" | `codegraph_callers` |
| "What does Y call?" | `codegraph_callees` |
| "How does X reach Y?" | `codegraph_trace` |
| "What would break if I changed Z?" | `codegraph_impact` |
| "Show me Y's signature/source" | `codegraph_node` |
| "Give me focused context" | `codegraph_context` |
| "See several symbols' source" | `codegraph_explore` |
| "What files exist under path/" | `codegraph_files` |

### Rules of thumb

- Answer directly — `codegraph_context` first, then ONE `codegraph_explore` for source
- Trust codegraph results. Do NOT re-verify with grep
- Don't grep first when looking up a symbol by name
- Don't chain `codegraph_search` + `codegraph_node` — use `codegraph_context`
- Don't loop `codegraph_node` — use one `codegraph_explore`
- Index lag: file watcher debounces ~500ms behind writes

### If `.codegraph/` doesn't exist

Run `codegraph init -i` to build the index.

---

## Agent skills

### Issue tracker
GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels
uses five standard labels: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs
Single-context — one CONTEXT.md + docs/adr/ at repo root. See `docs/agents/domain.md`.
