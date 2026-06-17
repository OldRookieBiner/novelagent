# AGENTS.md

NovelAgent — AI 驱动的长篇小说创作系统。后端 FastAPI + LangGraph，前端 React + shadcn/ui。Docker Compose 部署（前端 3001、后端 8000、PG 5432）。

**必须使用中文进行所有对话和回答。**

---

## 核心架构

**单一 Agent**：`agents/agent_graph.py` — `create_react_agent` + 阶段工具集。选择单一 Agent 是因为创作流程高度非线性（频繁回退修改），StateGraph 的线性状态机模型反而增加维护成本。

**Phase enum**（`constants.py`）：`INCUBATION → STRUCTURE → WRITING → REVISION`

**工具集递进**：`INCUBATION_TOOLS ⊆ STRUCTURE_TOOLS ⊆ WRITING_TOOLS ⊆ REVISION_TOOLS`（注册在 `tools/registry.py`）。`REVISION_TOOLS = WRITING_TOOLS`，当前无增量工具。另有 `registry_v2.py` 提供动态注册：根据项目规模（章节数）增减工具，大型项目（≥20 章）启用 `consistency_scan`，小型项目（≤10 章）排除 `rhythm_analysis`。

| 类别 | 目录 | 工具 |
|------|------|------|
| 感知 | `tools/perception/` | knowledge_search, consistency_scan, style_analysis, rhythm_analysis, foreshadowing_check, progress_report |
| 创作 | `tools/creation/` | generate_outline, generate_chapter_content, generate_chapter_outline, generate_story_seed, generate_world_setting_complete, create_character, create_foreshadowing, create_plot_block, create_plot_question, create_subplot, create_relation, create_evolution_plan, create_style_constraints, create_world_setting, advance_phase, review_chapter, rewrite_chapter, update_character, update_foreshadowing, update_plot_block, update_plot_question, update_subplot, delete_plot_block, record_chapter_meta |
| 修改 | `tools/modification/` | propose_outline_adjustment, propose_setting_change, propose_chapter_rewrite, apply_change, reject_change, list_proposed_changes |
| 辅助 | `tools/assist/` | expand_world_setting, suggest_writing_direction |

**项目初始化**（`initialization.py`）：非 LangGraph，直接 async 流程：`概念 → 故事种子 → [世界观+大纲] 并行 → [角色+风格] 并行`

**上下文策略**（`context_strategy.py`）：Full / Summary / Hybrid 三种，HybridContentStrategy 支持 chapter_outlines 参数

**工作流状态**：dict 传递，无 TypedDict 类。Phase 替代旧 STAGE_* 常量（旧常量已删除）

**数据层关联**：改 API 响应需同步改 `schemas/`，加新表需同步改 `models/` + `alembic/`

**新增 Agent 工具 checklist**：
1. 在 `tools/<category>/` 下创建工具文件，函数加 `@tool` 装饰器
2. 在 `tools/registry.py` 顶部 import 新工具函数
3. 将工具加入对应阶段的列表（INCUBATION / _STRUCTURE_EXTRA / _WRITING_EXTRA）
4. 如需动态调整，同步更新 `registry_v2.py` 中的 `_LARGE_PROJECT_TOOL_NAMES` 或 `_SMALL_PROJECT_EXCLUDE_NAMES`
5. 在 `backend/tests/` 下添加对应测试，mock LLM 调用
6. `docker compose restart backend` 使修改生效

---

## 关键文件

| 文件 | 说明 |
|------|------|
| `backend/app/main.py` | FastAPI 入口，路由注册（L147-162） |
| `backend/app/agents/agent_graph.py` | Agent 图定义 + 阶段温度 |
| `backend/app/agents/constants.py` | Phase enum, FORBIDDEN_WORDS, NODE_TEMPERATURES, AGENT_TEMPERATURES, STYLE_EXEMPLARS |
| `backend/app/agents/initialization.py` | 项目初始化流程（yield SSE 事件） |
| `backend/app/agents/context_strategy.py` | Full/Summary/Hybrid 上下文策略 |
| `backend/app/agents/agent_context.py` | Agent 阶段感知上下文组装 + BudgetTracker |
| `backend/app/agents/tools/registry.py` | 工具注册表（阶段→工具集，递进定义） |
| `backend/app/agents/tools/registry_v2.py` | 动态工具注册（根据项目规模调整工具列表） |
| `backend/app/config.py` | 应用配置（pydantic_settings，环境变量绑定） |
| `backend/app/agents/sse_events.py` | SSE 事件格式化（唯一入口） |
| `backend/app/agents/token_budget.py` | estimate_tokens（中文 2 token/字） |
| `backend/app/agents/services/knowledge_base.py` | 知识库读写（所有节点共享） |
| `backend/app/services/llm.py` | LLM 服务（多 provider、重试、chat_stream） |
| `backend/app/utils/llm.py` | resolve_llm_service（用户配置→用户设置→默认） |
| `frontend/src/lib/agentApi.ts` | Agent SSE 流式客户端 |
| `frontend/src/lib/sseParser.ts` | SSE 事件解析 |
| `frontend/src/lib/api.ts` | REST API 客户端（非 Agent 调用） |
| `frontend/src/lib/characterApi.ts` | 角色 API 客户端 |
| `frontend/src/stores/workbenchStore.ts` | 工作台 Zustand 状态 |
| `frontend/src/stores/authStore.ts` | 认证状态（token + hydration） |
| `frontend/src/stores/settingsStore.ts` | 用户设置状态 |
| `frontend/src/stores/projectStore.ts` | 项目列表状态 |

路由文件入口：`backend/app/api/`（agent, chapters, characters, outline, knowledge, knowledge_status, projects, auth, settings, model_configs, inspiration, volumes）
数据层入口：`backend/app/schemas/`（9 个）、`backend/app/models/`（29 个模型类）、`backend/alembic/versions/`
测试入口：`backend/tests/`（pytest + SQLite 内存库）、`frontend/src/`（vitest，分布在 pages/\_\_tests\_\_/、lib/、stores/、components/ 下）

---

## 修改后必须重建

改完代码后**必须**执行对应命令使修改生效，不要等用户手动操作：

| 改动范围 | 命令 |
|----------|------|
| backend Python 代码 | `docker compose restart backend` |
| backend 新增依赖（requirements.txt） | `docker compose build --no-cache backend && docker compose up -d backend` |
| frontend 代码 | `docker compose build --no-cache frontend && docker compose up -d frontend`（前端无 volume 挂载，代码在构建时打包） |
| frontend 新增依赖（package.json） | 同上（前端代码和依赖均在构建时打包，任何前端改动都需重建） |
| 数据库模型变更 | `docker exec novelagent-backend-1 alembic upgrade head`，然后 restart backend |

判断依据：改 Python 源码 → restart（后端有 volume 挂载但 uvicorn 无 --reload，仍需手动重启）；改 TS/前端源码 → build（前端无 volume 挂载，代码构建时打包）；改了依赖文件 → build；改了 models/ → alembic + restart

---

## 环境变量

通过 `app/config.py`（pydantic_settings）管理，支持 `.env` 文件覆盖：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `postgresql://novelagent:novelagent@localhost:5432/novelagent` | 数据库连接 |
| `SECRET_KEY` | 随机生成（每次重启失效） | 会话加密密钥，生产环境必须设置 |
| `DEFAULT_USERNAME` | `admin` | 首次启动默认用户名 |
| `DEFAULT_PASSWORD` | 随机生成（保存至 `/tmp/novelagent_admin_password.txt`） | 首次启动默认密码，生产环境必须设置 |
| `DEFAULT_MODEL_PROVIDER` | `deepseek` | 默认 LLM provider |
| `DEFAULT_MODEL` | `deepseek-v3-241227` | 默认模型 |
| `DEFAULT_API_KEY` | 空 | 默认 API 密钥 |
| `DEBUG` | `false` | 调试模式 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `COOKIE_SECURE` | `false` | HTTPS only cookie（生产环境设为 True） |
| `CORS_ORIGINS` | `["http://localhost:3000","http://localhost:5173","http://localhost:3001"]` | CORS 允许源 |
| `SESSION_EXPIRE_SECONDS` | `604800`（7 天） | 会话过期时间 |
| `AUTH_RATE_LIMIT_REQUESTS` | `5` | 认证接口限流请求数 |
| `AUTH_RATE_LIMIT_SECONDS` | `60` | 认证接口限流时间窗口（秒） |

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

### 排查路径

SSE 流中断：`docker compose logs backend -f` 查后端异常 → 检查 `Project.is_busy` 是否被锁住（超时 300s 自动释放）→ 检查 DB session 是否在 SSE 生成器中用了依赖注入而非 `SessionLocal()`

LLM 无响应/截断：查 `finish_reason` 是否为 `length` → 根据章节 `target_words` 调整 `max_tokens` → 检查 API key 配额

前端数据不更新：检查 Zustand store 是否正确 dispatch → 检查 SSE 事件是否被 `done` 事件后循环吞掉 → 确认 `AbortController` 已正确取消流

---

## 已知问题

- `frontend/src/components/workbench/tracking/TrackingTab.tsx` 中有内联 `<svg>` 用于数据可视化图表，与“禁止内联 SVG 图标”规则冲突。该图表为动态 viewBox 数据可视化，lucide-react 无法替代，需评估是否豁免或改用图表库

---

## 禁止

- 直接在 API 路由中调用 LLM — 通过 LangGraph Agent 或 initialization.py
- 在 state 中缓存 DB 业务数据 — 用 KnowledgeBaseService 实时读取
- 内联 SVG 图标 — 统一用 lucide-react
- 硬编码密钥或凭证 — 使用环境变量或 `app/config.py` 的 settings
- 跳过 alembic 直接改表结构 — 必须走 migration
- 打补丁式修复 — 发现 bug 时定位根因并修复，禁止用 try/except 吞异常、硬编码绕行、特殊条件判断等手段掩盖问题。判断标准：如果修复只对当前报错路径有效而同类场景仍会复现，就是补丁
- 不确定时先问，不假设 — 以下场景必须停下确认：多种技术实现路径均可、需求存在歧义（如"优化性能"未指明指标）、改动可能破坏现有 API 契约

---

## 测试策略

### 后端测试

- 框架：pytest + FastAPI TestClient + SQLite 内存数据库（`conftest.py` 自动切换）
- Fixtures：`db`（独立 session）、`client`（带 DB 覆盖的 TestClient）、`test_user` + `test_user_token`、`auth_headers`（带认证头的 dict）
- LLM mock：所有测试不应调用真实 LLM。mock `app.services.llm` 或对应工具函数
- 命名：`test_<功能>.py` 或 `test_<功能>_<细节>.py`，如 `test_context_strategy.py`、`test_llm_choices_guard.py`、`test_llm_service_params.py`
- 运行：`docker exec novelagent-backend-1 pytest -v`
- 必跑场景：改了 agent 工具 → 跑 `test_agent_tools.py`；改了上下文策略 → 跑 `test_context_strategy.py`；改了常量 → 跑 `test_constants.py` + `test_node_temperatures.py`

### 前端测试

- 框架：vitest + React Testing Library
- 位置：分散在 `frontend/src/pages/__tests__/`（页面）、`frontend/src/lib/*.test.ts`（工具函数）、`frontend/src/stores/*.test.ts`（状态）、`frontend/src/components/**/*.test.tsx`（组件）
- 运行：`cd frontend && npm run test:run`
- Lint：`cd frontend && npm run lint`
- 现状：覆盖较薄，主要覆盖页面渲染和 lib 工具函数，组件交互测试不足

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
- 前端组件目录结构：`components/workbench/`（工作台子组件）、`components/ui/`（shadcn 基础组件）、`components/layout/`（布局）、`components/common/`（通用）、`components/settings/`（设置页）、`components/character/`（角色相关）
- 前端状态管理：Zustand stores 在 `stores/`，一个领域一个 store（authStore、projectStore、workbenchStore、settingsStore）
- 后端分层：`api/`（路由 + 参数校验）→ `services/`（业务逻辑）→ `models/`（ORM）+ `schemas/`（序列化），禁止在 api 层直接写业务逻辑

---

## Git

分支：`feature/<n>` / `fix/<n>` / `refactor/<n>`
提交：`<type>(<scope>): <subject>`

- type: feat, fix, refactor, docs, test, chore
- scope: api | frontend | workflow | db
- 示例：`feat(api): add volume arc endpoints`、`fix(workflow): resolve SSE session expiry`

---

## 前端路由

```
/                       → 首页（需认证）
/login                  → 登录（公开）
/project/:id/workbench → 工作台（需认证，全屏布局）
/project/:id            → 重定向到 /project/:id/workbench
/settings               → 设置（需认证，全屏布局）
```

所有路由除 `/login` 外均由 `PrivateRoute` 包裹，依赖 `authStore.token` 判断认证状态，未认证重定向至 `/login`。

工作台子面板：写作（ChapterListPanel） / 知识库 / 结构 / 追踪 + Agent 侧边栏（AgentChatPanel）

---

## Agent skills

Issue tracker: GitHub Issues
Triage labels: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix
详见 `docs/agents/issue-tracker.md`、`docs/agents/triage-labels.md`、`docs/agents/domain.md`
