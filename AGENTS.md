# AGENTS.md

NovelAgent v0.8.11 — AI 驱动的长篇小说创作系统。后端 FastAPI + LangGraph，前端 React + shadcn/ui。Docker Compose 部署（前端 3001、后端 8000、PG 5432）。

**必须使用中文进行所有对话和回答。**

---

## 核心架构

**单一 Agent**：`agents/agent_graph.py` — `create_react_agent` + 阶段工具集。无独立 StateGraph。

**Phase enum**（`constants.py`）：`INCUBATION → STRUCTURE → WRITING → REVISION`

**工具集递进**：`INCUBATION_TOOLS ⊆ STRUCTURE_TOOLS ⊆ WRITING_TOOLS`（注册在 `tools/registry.py`）

| 类别 | 目录 | 工具示例 |
|------|------|----------|
| 感知 | `tools/perception/` | knowledge_search, consistency_check, style_analysis, rhythm_analysis |
| 创作 | `tools/creation/` | generate_outline, generate_chapter_content, create_character, create_foreshadowing |
| 修改 | `tools/modification/` | propose_outline_adjustment, propose_setting_change, propose_chapter_rewrite |
| 辅助 | `tools/assist/` | writer_block_assist, suggest_foreshadowing, suggest_plot_twist |

**项目初始化**（`initialization.py`）：非 LangGraph，直接 async 流程：`概念 → 故事种子 → [世界观+大纲] 并行 → [角色+风格] 并行`

**上下文策略**（`context_strategy.py`）：Full / Summary / Hybrid 三种，HybridContentStrategy 支持 chapter_outlines 参数

**工作流状态**：dict 传递，无 TypedDict 类。Phase 替代旧 STAGE_* 常量（旧常量已删除）

**数据层关联**：改 API 响应需同步改 `schemas/`，加新表需同步改 `models/` + `alembic/`

---

## 关键文件

| 文件 | 说明 |
|------|------|
| `backend/app/main.py` | FastAPI 入口，路由注册（L130-143） |
| `backend/app/agents/agent_graph.py` | Agent 图定义 + 阶段温度 |
| `backend/app/agents/constants.py` | Phase enum, FORBIDDEN_WORDS, NODE_TEMPERATURES, AGENT_TEMPERATURES, MODEL_CONTEXT_WINDOWS |
| `backend/app/agents/initialization.py` | 项目初始化流程（yield SSE 事件） |
| `backend/app/agents/context_strategy.py` | Full/Summary/Hybrid 上下文策略 |
| `backend/app/agents/agent_context.py` | Agent 阶段感知上下文组装 + BudgetTracker |
| `backend/app/agents/tools/registry.py` | 工具注册表（阶段→工具集） |
| `backend/app/agents/sse_events.py` | SSE 事件格式化（唯一入口） |
| `backend/app/agents/token_budget.py` | estimate_tokens（中文 2 token/字） |
| `backend/app/agents/services/knowledge_base.py` | 知识库读写（所有节点共享） |
| `backend/app/services/llm.py` | LLM 服务（多 provider、重试、chat_stream） |
| `backend/app/utils/llm.py` | resolve_llm_service（用户配置→用户设置→默认） |
| `frontend/src/lib/agentApi.ts` | Agent SSE 流式客户端 |
| `frontend/src/lib/sseParser.ts` | SSE 事件解析 |
| `frontend/src/stores/workbenchStore.ts` | 工作台 Zustand 状态 |

路由文件入口：`backend/app/api/`（agent, chapters, characters, outline, knowledge, projects, auth, settings, model_configs, inspiration, volumes）
数据层入口：`backend/app/schemas/`、`backend/app/models/`（~20 表）、`backend/alembic/versions/`
测试入口：`backend/tests/`（pytest）、`frontend/src/pages/__tests__/`（vitest）

---

## 修改后必须重建

改完代码后**必须**执行对应命令使修改生效，不要等用户手动操作：

| 改动范围 | 命令 |
|----------|------|
| backend Python 代码 | `docker compose restart backend` |
| backend 新增依赖（requirements.txt） | `docker compose build --no-cache backend && docker compose up -d backend` |
| frontend 代码 | `docker compose restart frontend` |
| frontend 新增依赖（package.json） | `docker compose build --no-cache frontend && docker compose up -d frontend` |
| 数据库模型变更 | `docker exec novelagent-backend-1 alembic upgrade head`，然后 restart backend |

判断依据：仅改 Python/TS 源码 → restart；改了依赖文件 → build；改了 models/ → alembic + restart

---

## 陷阱

### SSE 端点 DB Session

SSE 生成器内部用 `SessionLocal()` 创建独立 Session，**不要**用 FastAPI 依赖注入的 `db: Session`。长流期间注入的 session 会过期。

### 前端 SSE 流中断

`createSSEStream` 收到 `done` 事件后必须立即退出循环，否则网络断开会误报 error。用 `AbortController` 取消流式请求。

### KnowledgeBaseService detached ORM

每个 API 内部创建独立 DB session，操作完立即关闭。返回的 ORM 对象在 session 关闭后为 **detached 状态**，访问 lazy-loaded 关系会抛 DetachedInstanceError。

### LLM 截断

`chat_stream()` 默认 `max_tokens=4096`。检测到 `finish_reason="length"` 时记警告。章节正文生成需根据 `target_words` 计算足够 max_tokens 传入。

### volumes.py 未注册

`api/volumes.py` 存在但未在 `main.py` 注册路由，卷/弧 API 调用会 404。

### TipTap 换行

`setContent()` 不自动将 `\n` 转 `<p>`：
```typescript
const html = text.split('\n').filter(p => p.trim()).map(p => `<p>${p}</p>`).join('')
editor.commands.setContent(html)
```

### shadcn Button+Link

```tsx
<Button asChild><Link to="/path">文本</Link></Button>
```

### 项目 busy lock

`Project.is_busy` / `busy_since` / `busy_by` 防并发。Agent API `_acquire_busy_lock` 获取，超时 300s 自动释放。

---

## 禁止

- 直接在 API 路由中调用 LLM — 通过 LangGraph Agent 或 initialization.py
- 在 state 中缓存 DB 业务数据 — 用 KnowledgeBaseService 实时读取
- 内联 SVG 图标 — 统一用 lucide-react
- 不确定时先问，不假设 — 目标有多种理解时停下来确认

---

## 常用命令

```bash
docker compose up -d                    # 启动
docker compose down                     # 停止
docker compose logs backend -f          # 后端日志
docker compose build --no-cache backend && docker compose up -d backend   # 重建后端
docker compose build --no-cache frontend && docker compose up -d frontend  # 重建前端
docker exec novelagent-backend-1 pytest -v                                   # 后端测试
cd frontend && npm run test:run                                              # 前端测试
cd frontend && npm run lint                                                  # 前端 lint
docker exec novelagent-backend-1 alembic upgrade head                       # 数据库迁移
docker exec novelagent-backend-1 alembic revision -m "desc"                 # 新建迁移
```

---

## Docker 安全

安全：`docker compose up/down/restart/build/logs`
危险（需确认）：`docker stop/rm $(docker ps -aq)`、`docker system prune -af`、`docker volume prune`
`docker compose down -v` 删数据库数据
历史教训：曾误执行 `docker stop $(docker ps -aq)` 删除了服务器上所有容器

---

## 代码风格

- 中文注释
- Allman 大括号（独占一行）
- 前端 camelCase / 后端 snake_case / 类/组件 PascalCase
- 图标：lucide-react，禁止内联 SVG

---

## Git

分支：`feature/<n>` / `fix/<n>` / `refactor/<n>`
提交：`<type>(<scope>): <subject>`，scope: api | frontend | workflow | db

---

## 前端路由

```
/                       → 首页
/login                  → 登录
/project/:id/workbench → 工作台（写作/知识库/结构/追踪 + Agent 侧边栏）
/settings               → 设置
```

---

## Agent skills

Issue tracker: GitHub Issues
Triage labels: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix
详见 `docs/agents/issue-tracker.md`、`docs/agents/triage-labels.md`、`docs/agents/domain.md`
