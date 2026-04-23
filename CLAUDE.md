# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**NovelAgent** - AI 小说创作 Agent 系统。

| 版本 | 状态 | 说明 |
|------|------|------|
| v0.1.x | 已发布 | CLI 版本，三 Agent 协作 |
| v0.2.0 | 已发布 | Web 应用，React + FastAPI + PostgreSQL |
| v0.6.2 | 当前 | LangGraph 工作流集成、SSE 流式传输、暂停/恢复 |

---

## v0.1.x CLI 版本

```bash
python cli.py new "项目名称"      # 创建新项目
python cli.py continue "项目名称"  # 继续现有项目
python cli.py list               # 查看项目列表
```

配置：`export DEEPSEEK_API_KEY="your-key"` 或 `export OPENAI_API_KEY="your-key"`

---

## v0.2.0+ Web 版本

### Development Commands

```bash
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

# 前端测试
cd frontend && npm run test:run
cd frontend && npm run test:run -- src/stores/workflowStore.test.ts  # 单个测试文件
cd frontend && npm run test:coverage
```

### Architecture

```
novelagent/
├── backend/app/
│   ├── api/            # API 路由 (projects, outline, chapters, settings, model_configs, agent_prompts, workflow)
│   ├── agents/         # LangGraph Agents (state, graph, nodes/, checkpointer)
│   ├── models/         # SQLAlchemy 模型 (user, project, outline, chapter, model_config, checkpoint)
│   ├── schemas/        # Pydantic schemas
│   └── services/       # LLM 服务、加密服务
├── frontend/src/
│   ├── components/     # UI 组件 (ui/, project/, settings/)
│   ├── pages/          # 页面
│   ├── lib/            # API 客户端 (api, workflowApi, sseParser)
│   └── stores/         # Zustand 状态 (workflowStore, settingsStore)
└── docker-compose.yml
```

### 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + Vite + shadcn/ui + Tailwind + TipTap + Zustand |
| 后端 | FastAPI + SQLAlchemy + PostgreSQL + LangGraph |
| 部署 | Docker Compose |

### 页面结构

```
/                   → 首页（项目列表）
/project/:id        → 项目详情
/project/:id/write  → 写作页面
/project/:id/read/:chapterId → 阅读/审核
/settings           → 设置
```

---

## v0.6.2 LangGraph 工作流架构

### 工作流模式

| 模式 | 说明 |
|------|------|
| `step_by_step` | 每个阶段需手动确认 |
| `hybrid` | 大纲和章节大纲需确认，写作自动进行 |
| `auto` | 全自动，仅审核不通过时暂停 |

### 后端工作流 API

```
POST /api/projects/{id}/workflow/run     # 运行工作流（SSE 流式）
POST /api/projects/{id}/workflow/confirm # 确认当前节点
GET  /api/projects/{id}/workflow/state    # 获取工作流状态
POST /api/projects/{id}/workflow/cancel   # 取消工作流
```

### 前端工作流状态管理

```typescript
// workflowStore - Zustand store
import { useWorkflowStore } from '@/stores/workflowStore'

// 主要状态
stage: WorkflowStage              // 当前阶段
waitingForConfirmation: boolean   // 是否等待确认
confirmationType: ConfirmationType // 确认类型
writtenChapters: WrittenChapter[] // 已写章节

// workflowApi - SSE 流式 API
import { workflowApi } from '@/lib/workflowApi'
await workflowApi.runWorkflow(projectId, {
  onNodeStart, onNodeDone, onChunk, onCheckpoint, onWaiting, onDone, onError
})
```

### SSE 事件类型

| 事件 | 说明 |
|------|------|
| `node_start` | 节点开始 |
| `node_done` | 节点完成 |
| `chunk` | 文本块 |
| `checkpoint` | 检查点保存 |
| `waiting` | 等待确认 |
| `done` | 工作流完成 |
| `error` | 错误 |

### SSE 解析工具

```typescript
// 共享 SSE 解析器（frontend/src/lib/sseParser.ts）
import { parseSSEEventBlock, parseSSEData } from '@/lib/sseParser'

const event = parseSSEEventBlock(eventBlock)  // 解析事件块
const data = parseSSEData(event.data)          // 解析 data 字段
```

---

## Development Process

使用 **Superpowers skills** 主导开发：

| 阶段 | 核心技能/命令 | 强制要求 |
|------|--------------|----------|
| 需求/设计 | `superpowers:brainstorming` | 新功能必须先设计讨论，**不得跳过** |
| 计划编写 | `superpowers:writing-plans` | 设计确认后编写详细实现计划 |
| 计划执行 | `superpowers:executing-plans` | 按计划逐步执行 |
| 并行开发 | `superpowers:subagent-driven-development` | 并行执行独立任务 |
| 测试驱动 | `superpowers:test-driven-development` | TDD：先写测试再写实现 |
| 完成验证 | `superpowers:verification-before-completion` | 完成前运行验证命令 |
| 请求审查 | `superpowers:requesting-code-review` | 审查通过后再提交 |
| 接收审查 | `superpowers:receiving-code-review` | 处理审查反馈，修改代码 |
| 提交代码 | `commit-commands:commit` | 审查通过后提交 |
| 提交并推送 | `commit-commands:commit-push-pr` | 提交 + 推送 + 创建 PR（一条龙） |
| Bug 修复 | `superpowers:systematic-debugging` | 系统排查，**不得盲目修改** |
| 完成分支 | `superpowers:finishing-a-development-branch` | 合并/PR/清理分支 |

### 辅助工具

| Skill | 用途 | 触发场景 |
|-------|------|----------|
| `superpowers:using-git-worktrees` | 隔离开发环境 | 需要独立开发分支时 |
| `ui-ux-pro-max:ui-ux-pro-max` | UI/UX 设计建议 | 界面设计讨论时 |
| `agent-browser-skill:agent-browser` | 浏览器自动化 | E2E 测试、页面抓取 |
| `commit-commands:clean_gone` | 清理已删除的远程分支 | 分支维护时 |

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

### v0.6.0 模型配置

用户模型配置存储在 `model_configs` 表，API Key 使用 AES 加密。LLM 服务优先使用模型配置，回退到用户设置：
```python
# 获取 LLM 服务优先级：模型配置 > 用户设置
from app.services.llm import get_llm_service_from_config, get_llm_service
```

### v0.6.2 workflowMode 持久化

workflowMode 使用 Zustand persist middleware 自动持久化到 localStorage：
```typescript
// settingsStore 自动保存 workflowMode 到 localStorage
// key: 'settings-storage'
```

### SSE 流式中断处理

前端使用 AbortController 取消流式请求：
```typescript
const controller = new AbortController()
await outlineApi.createStream(projectId, callbacks, { signal: controller.signal })
// 取消请求
controller.abort()
```

### SSE 流式传输换行符

`data:` 行包含换行符会破坏 SSE 格式。后端 JSON 编码：
```python
yield f"data: {json.dumps(chunk)}\n\n"
```
前端使用 `sseParser.ts` 解析：
```typescript
import { parseSSEEventBlock, parseSSEData } from '@/lib/sseParser'
```

### TipTap 纯文本内容转换

`setContent()` 不会自动将 `\n` 转为 `<p>` 标签：
```typescript
const html = text.split('\n').filter(p => p.trim()).map(p => `<p>${p}</p>`).join('')
editor.commands.setContent(html)
```

### shadcn/ui Button + Link 嵌套

```jsx
// ❌ 错误
<Link to="/path"><Button>文本</Button></Link>

// ✅ 正确
<Button asChild><Link to="/path">文本</Link></Button>
```

### lucide-react 图标使用

统一使用 `lucide-react` 图标库，避免内联 SVG：

```tsx
// ✅ 正确
import { ArrowLeft, Plus } from 'lucide-react'
<ArrowLeft className="h-4 w-4" />

// ❌ 避免
<svg>...</svg>
```

### AI 大纲标题解析

需支持多种格式：`## 标题：《xxx》`、`# 小说大纲：《xxx》`、`# 《xxx》`

---

## Working Style

1. 目标不清晰时停下来讨论
2. 路径不是最短时直接建议更好的办法
3. 追查根因，不打补丁
4. 输出说重点

## 核心原则

**先跑通再优化**

---

## Language Preference

**请使用中文回答问题和交流。**

---

## Visual Companion

Brainstorming 时使用端口 **53734**（固定端口，不更改）：

注意：服务器会在空闲 30 分钟后自动停止，如页面显示 "Waiting for agent" 需重新启动

---

## Docker 开发规范（自动执行）

**前端修改后自动执行：**
```bash
docker compose build --no-cache frontend && docker compose up -d frontend
```

**后端修改后：**
```bash
docker compose restart backend
```