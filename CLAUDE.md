# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 目录

- [快速开始](#快速开始)
- [Web 应用架构](#web-应用架构)
- [LangGraph 工作流架构](#langgraph-工作流架构)
- [架构约束](#架构约束)
- [Docker 操作安全约束](#docker-操作安全约束)
- [Development Process](#development-process)
- [Code Style](#code-style)
- [Gotchas](#gotchas)
- [常见问题排查](#常见问题排查)
- [Git 规范](#git-规范)
- [API 端点汇总](#api-端点汇总)

---

## Project Overview

**NovelAgent** - AI 小说创作 Agent 系统。

**当前版本：v0.8.3** - 审核SSE流式改造、章节生成修复、后端架构优化

### 快速开始

```bash
# 1. 复制环境配置
cp .env.example .env

# 2. 启动服务
docker compose up -d

# 3. 访问应用
# 前端: http://localhost:3001
# 后端: http://localhost:8000
# 默认账号: admin / admin123
```

### 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `DATABASE_URL` | 是 | PostgreSQL 连接字符串 |
| `SECRET_KEY` | 是 | JWT 签名密钥 |
| `DEFAULT_USERNAME` | 否 | 默认用户名（默认: admin） |
| `DEFAULT_PASSWORD` | 否 | 默认密码（默认: admin123） |

### 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| 前端 | 3001 | React 应用 |
| 后端 | 8000 | FastAPI 服务 |
| 数据库 | 5432 | PostgreSQL |

---

## Web 应用架构

### Development Commands

```bash
# 启动/停止服务
docker compose up -d                    # 启动所有服务
docker compose down                     # 停止所有服务
docker logs novelagent-backend-1 -f     # 查看后端日志
docker compose restart backend          # 重启后端

# 重新构建
docker compose build --no-cache frontend && docker compose up -d frontend
docker compose build --no-cache backend && docker compose up -d backend

# 后端测试
docker exec novelagent-backend-1 pytest -v
docker exec novelagent-backend-1 pytest tests/test_workflow.py -v  # 单个测试文件
docker exec novelagent-backend-1 pytest tests/ -k "test_build_initial" -v  # 按名称匹配

# 前端测试
cd frontend && npm run test:run                                       # 单次运行
cd frontend && npm run test:run -- src/stores/workbenchStore.test.ts  # 单个测试文件
cd frontend && npm run test:coverage                                  # 覆盖率
cd frontend && npm run test                                           # Watch 模式（开发时用）

# 数据库迁移
docker exec novelagent-backend-1 alembic upgrade head    # 应用迁移
docker exec novelagent-backend-1 alembic revision -m "description"  # 创建新迁移
```

### Architecture

```
novelagent/
├── backend/app/
│   ├── api/            # API 路由 (auth, projects, outline, chapters, characters, settings, model_configs, system_prompts, workflow)
│   ├── agents/         # LangGraph Agents (state, graph, nodes/, checkpointer, streaming, sse_events, prompts)
│   ├── models/         # SQLAlchemy 模型 (user, project, outline, chapter, character, model_config, checkpoint, settings, system_config, workflow_state)
│   ├── schemas/        # Pydantic schemas (user, project, outline, chapter, character, model_config, settings, system_prompt)
│   ├── services/       # 业务服务 (llm, crypto, chapter_service, outline_service, model_providers, prompt_loader, workflow_orchestrator)
│   └── utils/          # 工具函数 (auth, deps, error, logger, project, workflow, llm, workflow_persistence)
├── frontend/src/
│   ├── components/     # UI 组件 (ui/, settings/, common/, layout/, workbench/, character/)
│   │   └── workbench/  #   creation/ (大纲/章节/写作/AI面板), planning/ (灵感/人物/关系面板)
│   ├── pages/          # 页面 (Home, Login, Settings, ProjectWorkbench)
│   ├── lib/            # API 客户端与工具 (api, workflowApi, sseParser, characterApi, inspiration, utils)
│   └── stores/         # Zustand 状态 (workbenchStore, settingsStore, authStore, projectStore, workflowStore)
└── docker-compose.yml
```

### 关键文件入口

| 文件 | 说明 |
|------|------|
| `backend/app/main.py` | 后端入口，FastAPI 应用配置 |
| `backend/app/agents/graph.py` | LangGraph 工作流定义、条件路由 |
| `backend/app/agents/state.py` | NovelState 状态定义、阶段常量 |
| `backend/app/agents/sse_events.py` | SSE 事件格式化工具（集中管理所有事件字符串） |
| `backend/app/api/workflow.py` | 工作流 API 路由、stream_workflow_events 核心流函数、build_initial_state |
| `backend/app/services/workflow_orchestrator.py` | 单节点 SSE 编排器（persist + 事务回滚） |
| `frontend/src/main.tsx` | 前端入口 |
| `frontend/src/App.tsx` | 路由配置 |
| `frontend/src/lib/api.ts` | API 客户端定义 |
| `frontend/src/lib/workflowApi.ts` | 工作流 SSE 流式 API |
| `frontend/src/lib/sseParser.ts` | SSE 事件解析器 |

### 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + Vite + shadcn/ui + Tailwind + TipTap + Zustand |
| 后端 | FastAPI + SQLAlchemy + PostgreSQL + LangGraph |
| 数据库迁移 | Alembic |
| 部署 | Docker Compose |

### 页面结构

```
/                       → 首页（项目列表，独立全屏布局）
/project/:id/workbench → 工作台页面（全屏布局，Tab 布局）
/project/:id            → 重定向到 workbench
/settings               → 设置
```

---

## LangGraph 工作流架构

### 工作流模式

| 模式 | 说明 |
|------|------|
| `step_by_step` | 每个阶段需手动确认 |
| `hybrid` | 大纲和章节大纲需确认，写作自动进行 |
| `auto` | 全自动，仅审核不通过时暂停 |

### LangGraph 工作流节点

| 节点 | 文件 | 说明 |
|------|------|------|
| 大纲生成 | `nodes/outline_generation.py` | 生成小说大纲，设置 `outline_valid` 标志 |
| 角色提取 | `nodes/character_generation.py` | 从大纲自动生成人物设定 |
| 关系图谱 | `nodes/relation_generation.py` | 生成人物关系 |
| 章节大纲 | `nodes/chapter_generation.py` | 生成章节大纲（含 `_calc_max_tokens` 动态 token 计算） |
| 章节 正文 | `nodes/chapter_generation.py` | 流式生成章节正文（`generate_chapter_content_stream`） |
| 审核 | `nodes/review.py` | AI 审核章节内容 |
| 重写 | `nodes/rewrite.py` | 根据审核意见重写 |
| 工具 | `nodes/utils.py` | 节点共享工具函数 |

### 前端工作流状态管理

```typescript
// workbenchStore - Zustand store（工作台核心状态）
import { useWorkbenchStore } from '@/stores/workbenchStore'

// 主要状态
stage: WorkflowStage              // 当前阶段
waitingForConfirmation: boolean   // 是否等待确认
confirmationType: ConfirmationType // 确认类型：outline | characters | relations | chapter_outlines | review_failed
writtenChapters: WrittenChapter[] // 已写章节

// workflowApi - SSE 流式 API
import { workflowApi } from '@/lib/workflowApi'
await workflowApi.runWorkflow(projectId, {
  onNodeStart, onNodeDone, onChunk, onCheckpoint, onWaiting, onDone, onError
})
```

### SSE 事件类型

| 事件 | 说明 | 来源 |
|------|------|------|
| `node_start` | 节点开始 | workflow.py |
| `node_done` | 节点完成 | workflow.py |
| `chunk` | LLM 流式文本块 | workflow.py, chapters.py |
| `progress` | 章节大纲生成进度（含完整字段数据） | chapters.py |
| `checkpoint` | 检查点保存 | — |
| `waiting` | 等待确认（含 confirmation_type） | workflow.py |
| `done` | 工作流/操作完成 | workflow.py, chapters.py |
| `error` | 错误 | 所有 SSE 端点 |

### SSE 解析工具

```typescript
// 共享 SSE 解析器（frontend/src/lib/sseParser.ts）
import { parseSSEEventBlock, parseSSEData } from '@/lib/sseParser'

const event = parseSSEEventBlock(eventBlock)  // 解析事件块
const data = parseSSEData(event.data)          // 解析 data 字段
```

---

## 架构约束

### LangGraph 工作流框架（强制）

**LangGraph 是本项目的核心工作流框架，所有新功能开发和优化必须基于 LangGraph 实现。**

| 约束 | 说明 |
|------|------|
| 工作流节点 | 所有 AI 生成流程必须作为 LangGraph 节点实现 |
| 状态管理 | 使用 NovelState (app/agents/state.py) 管理工作流状态 |
| 阶段常量 | `STAGE_INSPIRATION → STAGE_OUTLINE → STAGE_CHARACTERS → STAGE_RELATIONS → STAGE_CHAPTER_OUTLINES → STAGE_WRITING → STAGE_REVIEW → STAGE_COMPLETE` |
| 检查点 | 使用 WorkflowCheckpoint 实现暂停/恢复功能 |
| 流式传输 | 通过 LangGraph astream_events 实现 SSE 流式输出 |
| Prompt 预加载 | `run_workflow` 将 `_prompts` 预加载到 state，节点从 `state["_prompts"]` 获取 |

**禁止行为：**
- ❌ 直接在 API 路由中调用 LLM 服务（应通过 LangGraph 节点）
- ❌ 绕过 StateGraph 实现新的 AI 生成流程
- ❌ 在节点外部管理工作流状态

**历史教训 (v0.6.2)：** 早期版本虽然在技术栈声明使用 LangGraph，但实际开发中绕过框架直接实现功能，导致 v0.6.2 需要 **大规模重构** 才能正确集成 LangGraph。任何新功能开发前，必须先确认 LangGraph 的集成方式。

---

## Docker 操作安全约束

**原则：本项目容器自由操作，项目外容器需确认。**

**危险命令（影响项目外容器时需先询问用户）：**

| 命令 | 影响范围 | 操作前确认 |
|------|----------|------------|
| `docker stop/rm $(docker ps -aq)` | 所有容器 | ✅ 必须确认 |
| `docker system prune -af` | 所有未使用资源 | ✅ 必须确认 |
| `docker volume prune` | 所有未使用卷 | ✅ 必须确认 |
| `docker network prune` | 所有未使用网络 | ✅ 必须确认 |

**安全命令（仅影响本项目，无需确认）：**

| 命令 | 说明 |
|------|------|
| `docker compose up/down/restart` | 项目范围内操作 |
| `docker compose build` | 构建项目镜像 |
| `docker compose logs` | 查看项目日志 |

**安全原则：**

1. **优先使用 `docker compose`** - 自动限定在项目范围
2. **全局通配符 `$(docker ps -aq)` 需谨慎** - 会影响所有容器
3. **`-v` 参数删除数据卷** - `docker compose down -v` 会删除数据库数据

**历史教训 (2026-04-27)：** 误执行 `docker stop $(docker ps -aq)` 删除了服务器上所有容器，包括系统服务。

---

## Development Process

使用 **Superpowers skills** 主导开发：

### 开发流程图

```
BRAINSTORMING → SPEC → WRITING-PLANS → EXECUTION (内含 TDD) → CODE-REVIEW → FINISHING
     ↓           ↓           ↓               ↓                    ↓            ↓
  设计讨论   设计文档+审查  编写实现计划   subagent 或 inline     代码审查      完成分支
```

### 技能流程表

| 阶段 | 核心技能 | 说明 |
|------|----------|------|
| 需求/设计 | `superpowers:brainstorming` | 探索项目上下文 → 提问 → 提出 2-3 个方案 → 设计 → 写 spec → 自审 → 用户审查。**不得跳过** |
| 架构检查 | 确认 LangGraph 集成方式 | **[项目特定]** 涉及 AI/工作流的功能必须先确认节点设计 |
| 计划编写 | `superpowers:writing-plans` | 基于 spec 编写详细实现计划（含文件路径、代码、命令），保存到 `docs/superpowers/plans/` |
| 执行（推荐） | `superpowers:subagent-driven-development` | 每任务一个子代理 + 两阶段审查（spec 合规 → 代码质量），同会话内连续执行 |
| 执行（备选） | `superpowers:executing-plans` | 当前会话内逐步执行，每步验证 |
| Bug 修复 | `superpowers:systematic-debugging` | 先找根因（Phase 1）→ 模式分析（Phase 2）→ 假设验证（Phase 3）→ 实现修复（Phase 4），**不得盲目修改** |
| 完成验证 | `superpowers:verification-before-completion` | 任何完成声明前必须运行验证命令并提供证据，**不得凭感觉** |
| 请求审查 | `superpowers:requesting-code-review` | 每个任务/主要功能完成后审查，审查通过后再继续 |
| 接收审查 | `superpowers:receiving-code-review` | 先理解 → 验证 → 评估 → 再实现，禁止表演性同意 |
| 完成分支 | `superpowers:finishing-a-development-branch` | 先验证测试通过 → 4 选项（合并/PR/保留/丢弃） |
| 提交代码 | `commit-commands:commit` | 审查通过后提交 |

### 方案选择规则

当需要提出多个方案时，必须遵循以下规则：

1. **必须给出推荐方案** - 不能只列出选项让用户选择
2. **推荐方案放在首位** - 用户更容易注意到
3. **说明推荐理由** - 让用户理解权衡

示例：
> 有三种实现方式：
> 1. **方案A（推荐）** - 使用 X 方式，优点是...，缺点是...
> 2. 方案B - 使用 Y 方式...
> 3. 方案C - 使用 Z 方式...
>
> 推荐方案A，因为...

### 开发检查清单

**开始开发前：**

- [ ] 是否已调用 `superpowers:brainstorming` 进行设计？
- [ ] 设计文档（spec）是否已保存到 `docs/superpowers/specs/`？
- [ ] Spec 自审是否通过（无 placeholder、无矛盾、无歧义）？
- [ ] 用户是否已审查并批准 spec？
- [ ] 实现计划是否已保存到 `docs/superpowers/plans/`？
- [ ] 是否使用 worktree 隔离开发环境？

**完成开发后：**

- [ ] 是否已运行测试并确认通过？
- [ ] 是否已运行 `superpowers:verification-before-completion`？
- [ ] 是否已请求代码审查？
- [ ] 是否需要更新 CHANGELOG？（仅版本发布时记录重要变更）

### 辅助工具

| Skill | 用途 | 触发场景 |
|-------|------|----------|
| `superpowers:using-git-worktrees` | 隔离开发环境 | 需要独立开发分支时 |
| `superpowers:test-driven-development` | TDD 测试驱动开发 | 执行计划中实现功能/修复时 |
| `superpowers:systematic-debugging` | 系统调试 | 遇到 bug/测试失败时 |
| `ui-ux-pro-max:ui-ux-pro-max` | UI/UX 设计建议 | 界面设计讨论时 |
| `agent-browser-skill:agent-browser` | 浏览器自动化 | E2E 测试、页面抓取 |
| `commit-commands:clean_gone` | 清理已删除的远程分支 | 分支维护时 |

### Visual Companion

Brainstorming 时使用端口 **53734**（固定端口，不更改）：

注意：服务器会在空闲 30 分钟后自动停止，如页面显示 "Waiting for agent" 需重新启动

---

## Code Style

### 注释
- 写成的代码必须加上中文注释

### 括号
- 大括号独占一行（Allman 风格）

### 命名
- 前端函数/变量：camelCase
- 后端函数/变量：snake_case
- 类/组件/类型：PascalCase

---

## Gotchas

### 前端

#### SSE 流式中断处理

前端使用 AbortController 取消流式请求：
```typescript
const controller = new AbortController()
await outlineApi.createStream(projectId, callbacks, { signal: controller.signal })
// 取消请求
controller.abort()
```

`createSSEStream` 收到 `done` 事件后立即退出循环，避免后续网络断开误报 error。

#### TipTap 纯文本内容转换

`setContent()` 不会自动将 `\n` 转为 `<p>` 标签：
```typescript
const html = text.split('\n').filter(p => p.trim()).map(p => `<p>${p}</p>`).join('')
editor.commands.setContent(html)
```

#### shadcn/ui Button + Link 嵌套

```jsx
// ❌ 错误
<Link to="/path"><Button>文本</Button></Link>

// ✅ 正确
<Button asChild><Link to="/path">文本</Link></Button>
```

#### lucide-react 图标使用

统一使用 `lucide-react` 图标库，避免内联 SVG：

```tsx
// ✅ 正确
import { ArrowLeft, Plus } from 'lucide-react'
<ArrowLeft className="h-4 w-4" />

// ❌ 避免
<svg>...</svg>
```

### 后端

#### 模型配置优先级

用户模型配置存储在 `model_configs` 表，API Key 使用 AES 加密。LLM 服务优先使用模型配置，回退到用户设置：
```python
# 获取 LLM 服务优先级：模型配置 > 用户设置
from app.services.llm import get_llm_service_from_config, get_llm_service
```

#### 章节 max_tokens 动态计算

LLM 默认 `max_tokens=4096` 远不够 3000 中文章节。`_calc_max_tokens` 按 `目标字数 × 2.5 + 512` 计算（最低 8192）：
```python
# nodes/chapter_generation.py
def _calc_max_tokens(target_words: int) -> int:
    return max(int(target_words * 2.5) + 512, 8192)
```

#### LLM 截断检测

`chat_stream()` 检测 `finish_reason="length"` 并记录警告。如出现此日志，需增大 max_tokens：
```
LLM output truncated (finish_reason=length). max_tokens=4096 may be too low.
```

#### SSE 端点 DB Session 独立性

章节生成/审核等长 SSE 流使用 `SessionLocal()` 创建独立 Session，避免请求级 Session 在流式操作期间失效。不要在 SSE 生成器内部使用 FastAPI 依赖注入的 `db: Session`。

#### WorkflowOrchestrator 使用模式

单节点 SSE 流式端点（章节生成、审核等）使用 `WorkflowOrchestrator`：
```python
orch = WorkflowOrchestrator(db, project_id)
async for sse_event in orch.run(graph, config, initial_state, target_node, persist_callback):
    yield sse_event
```
persist_callback 异常会触发 `db.rollback()` 并 yield error 事件。

#### workflowMode 持久化

workflowMode 使用 Zustand persist middleware 自动持久化到 localStorage：
```typescript
// settingsStore 自动保存 workflowMode 到 localStorage
// key: 'settings-storage'
```

### AI 生成

#### AI 大纲标题解析

需支持多种格式：`## 标题：《xxx》`、`# 小说大纲：《xxx》`、`# 《xxx》`

---

## Working Style

| 原则 | 说明 |
|------|------|
| 先讨论后实现 | 目标不清晰时停下来 |
| 推荐最短路径 | 直接建议更好的办法 |
| 追查根因 | 不打补丁，解决根本问题 |
| 输出精简 | 说重点，不废话 |
| 语言 | 使用中文交流和回答 |
| 核心原则 | 先跑通再优化 |

---

## 常见问题排查

### 服务无法启动

```bash
# 检查容器状态
docker compose ps

# 查看错误日志
docker compose logs backend
docker compose logs db

# 重建所有服务
docker compose down -v  # -v 会删除数据库数据
docker compose up -d --build
```

### 数据库连接失败

```bash
# 检查数据库是否健康
docker compose ps db

# 手动连接数据库
docker exec -it novelagent-db-1 psql -U novelagent -d novelagent
```

### 前端页面空白

```bash
# 检查前端构建日志
docker compose logs frontend

# 重新构建前端
docker compose build --no-cache frontend && docker compose up -d frontend
```

### API 返回 401/403

- 检查是否已登录（token 是否过期）
- 检查 .env 中的 SECRET_KEY 是否正确配置

---

## Git 规范

### 分支命名

| 类型 | 格式 | 示例 |
|------|------|------|
| 功能 | `feature/<name>` | `feature/multi-model` |
| 修复 | `fix/<name>` | `fix/login-error` |
| 重构 | `refactor/<name>` | `refactor/workflow` |

### 提交信息格式

```
<type>(<scope>): <subject>

type: feat | fix | refactor | docs | test | chore
scope: api | frontend | workflow | db

示例:
feat(api): add model config API endpoints
fix(frontend): resolve dropdown transparent background
refactor(workflow): simplify node execution logic
```

### 版本发布

发布新版本时更新 CHANGELOG.md：

```markdown
## vX.X.X - YYYY-MM-DD

### Features
- 新功能描述

### Fixes
- 修复描述

### Improvements
- 改进描述
```

**注意：** 仅记录用户可见的重要变更，不记录小修改。

---

## API 端点汇总

### 核心 API

| 模块 | 前缀 | 说明 |
|------|------|------|
| 认证 | `/api/auth` | 登录、登出、当前用户 |
| 项目 | `/api/projects` | 项目 CRUD |
| 大纲 | `/api/projects/{id}/outline` | 大纲 CRUD、流式生成、确认、章节数设定 |
| 章节 | `/api/projects/{id}/chapters` | 章节大纲 CRUD、章节正文 CRUD、流式生成、流式审核 |
| 人物 | `/api/projects/{id}/characters` | 人物 CRUD、AI 生成、关系 CRUD、关系演化 |
| 设置 | `/api/settings` | 用户设置读写 |
| 模型 | `/api/model_configs` | 模型配置 CRUD、测试连接、健康检查、可用模型 |
| 提示词 | `/api/system_prompts` | Agent Prompt 列表、更新、重置 |

### 工作流 API

```
POST /api/projects/{id}/workflow/run     # 运行工作流（SSE 流式）
POST /api/projects/{id}/workflow/confirm # 确认当前节点（可携带修改数据）
GET  /api/projects/{id}/workflow/state    # 获取工作流状态
POST /api/projects/{id}/workflow/cancel   # 取消工作流（删除检查点）
PUT  /api/projects/{id}/workflow/stage    # 手动切换工作流阶段
```

---

## Agent skills

### Issue tracker
GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels
uses five standard labels: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs
Single-context — one CONTEXT.md + docs/adr/ at repo root. See `docs/agents/domain.md`.