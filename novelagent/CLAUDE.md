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
| v0.2.0 | 设计中 | Web 应用，React + FastAPI + PostgreSQL |

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

## v0.2.0 Web 版本（设计阶段）

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

## 核心原则

**先跑通再优化**
- 初版代码丑没关系，能跑就行
- 不要预留架构，不要过度抽象
- 从实践中自然抽象框架，不要先写框架再填内容

---

## Language Preference

**请使用中文回答问题和交流。**

---

## Known Issues (v0.1.x)

- **编码问题**：CLI 已处理 UTF-8 编码，支持中文和全角符号
- **API 超时**：默认 600 秒，火山方舟 API 响应较慢