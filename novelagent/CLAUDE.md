# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**NovelAgent** - AI 小说创作 Agent 系统。

- **v0.1.x（当前）**：CLI 应用，三 Agent 协作（大纲Agent → 写作Agent → 审核Agent）
- **v0.2.0（开发中）**：Web 应用，简化流程，LangGraph 重构

## Version Status

| 版本 | 状态 | 说明 |
|------|------|------|
| v0.1.x | 已发布 | CLI 版本，完整流程 |
| v0.2.0 | 开发中 | Web 应用，React + FastAPI + PostgreSQL |

---

## v0.1.x CLI 版本

### Development Commands

```bash
# 启动 CLI
python cli.py new "项目名称"      # 创建新项目
python cli.py continue "项目名称"  # 继续现有项目
python cli.py list               # 查看项目列表
python cli.py status "项目名称"   # 查看项目状态
```

### Architecture

```
novelagent/
├── cli.py               # CLI 入口
├── config.py            # API 配置、模型选择
├── core/
│   ├── llm_client.py    # API 调用封装（OpenAI兼容接口）
│   ├── conversation.py  # 对话历史管理
│   └── state.py         # JSON 状态持久化
├── agents/
│   ├── base.py          # Agent 基类
│   ├── outline_agent.py # 大纲 Agent
│   ├── writing_agent.py # 写作 Agent
│   └── review_agent.py  # 审核 Agent
├── prompts/
│   ├── outline.py       # 大纲相关 prompt
│   ├── writing.py       # 写作 prompt
│   └── review.py        # 审核 prompt
└── data/projects/       # JSON 状态存储
```

### Configuration

```bash
export DEEPSEEK_API_KEY="your-api-key"  # 火山方舟 DeepSeek
export OPENAI_API_KEY="your-api-key"    # OpenAI
```

### 信息收集标准

| 字段 | 说明 |
|------|------|
| `genre` | 题材类型 |
| `theme` | 核心主题 |
| `main_characters` | 主角设定 |
| `world_setting` | 世界设定 |
| `style_preference` | 风格偏好或目标篇幅 |

---

## v0.2.0 Web 版本（开发中）

### Development Commands

```bash
# Docker 开发环境
docker compose up -d                    # 启动所有服务
docker compose up -d frontend backend   # 仅启动前后端
docker compose down                     # 停止所有服务

# 查看日志
docker logs novelagent-backend-1 -f
docker logs novelagent-frontend-1 -f

# 重新构建
docker compose build --no-cache backend   # 重建后端
docker compose build --no-cache frontend  # 重建前端

# 后端测试
docker exec novelagent-backend-1 pytest
docker exec novelagent-backend-1 pytest -v

# 前端（需在 frontend 目录，有 node 环境）
cd frontend && npm run build
cd frontend && npm run test
```

### Architecture

```
novelagent/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/            # API 路由 (projects, outline, chapters, settings)
│   │   ├── agents/         # LangGraph Agents (info_collection, outline_generation, chapter_generation)
│   │   ├── models/         # SQLAlchemy 模型 (user, project, outline, chapter, settings)
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # LLM 服务、加密服务
│   │   └── utils/          # 工具函数 (auth, rate_limit)
│   ├── tests/              # pytest 测试
│   ├── alembic/            # 数据库迁移
│   └── requirements.txt
├── frontend/               # React 前端
│   ├── src/
│   │   ├── components/     # UI 组件 (common/, project/, ui/)
│   │   ├── pages/          # 页面 (Home, ProjectDetail, Writing, Reading, Settings, Login)
│   │   ├── lib/            # API 客户端
│   │   ├── stores/         # Zustand 状态 (authStore, projectStore, settingsStore)
│   │   └── types/          # TypeScript 类型
│   └── package.json
└── docker-compose.yml
```

### 创作流程

```
信息收集 → 大纲 → Agent建议章节数 → 用户确认 → 章节纲(一次性) → 正文 → 审核(可选)
```

**简化点**：去掉卷纲、单元纲，直接大纲→章节纲

### 技术栈

#### 前端
| 技术 | 说明 |
|------|------|
| React 18 + Vite | 前端框架 |
| shadcn/ui + Tailwind | UI 组件 |
| Zustand | 状态管理 |
| React Router v6 | 路由 |
| TipTap | 富文本编辑 |
| fetch + SSE | HTTP/流式请求 |

#### 后端
| 技术 | 说明 |
|------|------|
| FastAPI | 后端框架 |
| SQLAlchemy + Alembic | ORM + 迁移 |
| PostgreSQL | 数据库 |
| Session + Cookie | 认证 |
| LangGraph | Agent 框架 |

#### 部署
- Docker + Docker Compose

### 页面结构

```
/                   → 首页（项目卡片列表）
/project/:id        → 项目详情
/project/:id/write  → 写作页面
/project/:id/read/:chapterId → 阅读/审核
/settings           → 设置
```

### 详细设计文档

见 `docs/superpowers/specs/2026-04-08-novelagent-v0.2.0-design.md`

---

## Development Process

本项目使用 **Superpowers skills** 主导开发流程：

```
需求/设计 → 计划编写 → 计划执行 → 测试验证 → 代码审查 → 代码提交 → 完成分支
    ↓           ↓           ↓           ↓           ↓           ↓           ↓
brainstorming  writing   executing   verification  code       commit    finishing
               plans     plans       before        review     commands  development
                                     completion                          branch
```

### 强制规则

1. **禁止跳过设计阶段直接编写代码** - 新功能必须先 `superpowers:brainstorming`
2. **设计文档提交到 `docs/superpowers/specs/`**
3. **实现计划提交到 `docs/superpowers/plans/`**
4. **Bug 修复使用 `superpowers:systematic-debugging`**
5. **完成前使用 `superpowers:verification-before-completion`**

### 常用 Skills

| 场景 | Skill |
|------|-------|
| 新功能设计 | `superpowers:brainstorming` |
| 编写计划 | `superpowers:writing-plans` |
| 执行计划 | `superpowers:executing-plans` 或 `superpowers:subagent-driven-development` |
| Bug 修复 | `superpowers:systematic-debugging` |
| 代码审查 | `superpowers:requesting-code-review` / `superpowers:receiving-code-review` |
| 提交代码 | `commit-commands:commit` |
| 完成分支 | `superpowers:finishing-a-development-branch` |

---

### 辅助工具

| Skill | 用途 | 触发场景 |
|-------|------|----------|
| `superpowers:using-git-worktrees` | 隔离开发环境 | 需要独立开发分支时 |
| `ui-ux-pro-max:ui-ux-pro-max` | UI/UX 设计建议 | 界面设计讨论时 |
| `agent-browser-skill:agent-browser` | 浏览器自动化 | E2E 测试、页面抓取 |
| `commit-commands:clean_gone` | 清理已删除的远程分支 | 分支维护时 |

## Gotchas (v0.2.0)

### shadcn/ui Button + Link 嵌套问题

```jsx
// ❌ 错误 - 无效 HTML，点击可能失效
<Link to="/path">
  <Button>文本</Button>
</Link>

// ✅ 正确 - 使用 asChild 属性
<Button asChild>
  <Link to="/path">文本</Link>
</Button>
```

### AI 大纲标题解析

AI 返回多种标题格式，`parse_outline` 需支持：
- `## 标题：《xxx》`
- `# 小说大纲：《xxx》`
- `# 《xxx》`（直接返回书名号标题）

### API Key 配置

用户需在 Settings 页面配置 API Key 才能使用 AI 功能：
- 支持 DeepSeek（官方/火山方舟）和 OpenAI
- API Key 加密存储在数据库中

## Working Style

1. 不要假设我清楚自己想要什么。动机或目标不清晰时，停下来讨论。
2. 目标清晰但路径不是最短时，直接告诉我并建议更好的办法。
3. 遇到问题追查根因，不打补丁。每个决策都要能回答"为什么"。
4. 输出说重点，砍掉一切不改变决策的信息。

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

## Known Issues

### v0.1.x (CLI)
- **编码问题**：CLI 已处理 UTF-8 编码，支持中文和全角符号
- **API 超时**：默认 600 秒，火山方舟 API 响应较慢

### v0.2.0 (Web)
- **浏览器自动化测试**：agent-browser 对 React 合成事件支持有限，建议手动验证按钮点击功能
- **开发环境热重载**：后端代码修改后需重启容器（`docker compose restart backend`）

## Docker 开发规范（自动执行）

**前端代码修改后必须重新构建镜像才能生效。** 修改 `frontend/src/` 下任何文件后，Claude 必须 **自动执行** 以下命令，无需用户确认：

```bash
docker compose build --no-cache frontend && docker compose up -d frontend
```

**后端代码修改**通过 volume 挂载实时生效，只需重启容器：
```bash
docker compose restart backend
```