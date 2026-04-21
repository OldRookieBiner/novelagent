# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**NovelAgent** - AI 小说创作 Agent 系统。

| 版本 | 状态 | 说明 |
|------|------|------|
| v0.1.x | 已发布 | CLI 版本，三 Agent 协作 |
| v0.2.0 | 已发布 | Web 应用，React + FastAPI + PostgreSQL |
| v0.5.x | 当前 | UX 优化，灵感采集表单改进 |

---

## v0.1.x CLI 版本

```bash
python cli.py new "项目名称"      # 创建新项目
python cli.py continue "项目名称"  # 继续现有项目
python cli.py list               # 查看项目列表
```

配置：`export DEEPSEEK_API_KEY="your-key"` 或 `export OPENAI_API_KEY="your-key"`

---

## v0.2.0 Web 版本

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

# 前端测试（需 node 环境）
cd frontend && npm run test:run
cd frontend && npm run test:coverage
```

### Architecture

```
novelagent/
├── backend/app/
│   ├── api/            # API 路由 (projects, outline, chapters, settings)
│   ├── agents/         # LangGraph Agents
│   ├── models/         # SQLAlchemy 模型
│   ├── schemas/        # Pydantic schemas
│   └── services/       # LLM 服务
├── frontend/src/
│   ├── components/     # UI 组件
│   ├── pages/          # 页面
│   ├── lib/            # API 客户端
│   └── stores/         # Zustand 状态
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

## Gotchas (v0.2.0)

### SSE 流式传输换行符

`data:` 行包含换行符会破坏 SSE 格式。后端 JSON 编码：
```python
yield f"data: {json.dumps(chunk)}\n\n"
```
前端解码：
```typescript
const decoded = JSON.parse(data)
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