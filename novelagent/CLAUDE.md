# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**NovelAgent** - AI 小说创作 Agent 系统。三 Agent 协作：大纲Agent → 写作Agent → 审核Agent。

采用"先 Agent 后框架"策略，初版专注跑通流程。

## Development Commands

```bash
# 启动 CLI
python cli.py new "项目名称"      # 创建新项目
python cli.py continue "项目名称"  # 继续现有项目
python cli.py list               # 查看项目列表
python cli.py status "项目名称"   # 查看项目状态
```

## Architecture

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
│   ├── outline_agent.py # 大纲 Agent（阶段1）
│   ├── writing_agent.py # 写作 Agent（阶段3）
│   └── review_agent.py  # 审核 Agent（阶段3）
├── prompts/
│   ├── outline.py       # 大纲相关 prompt
│   ├── writing.py       # 写作 prompt（阶段3）
│   └── review.py        # 审核 prompt（阶段3）
└── data/projects/       # JSON 状态存储
```

## Tech Stack

- Python 3 + 直接 LLM API 调用（无框架依赖）
- DeepSeek（初版），config.py 配置多模型切换
- JSON 文件持久化

## Implementation Phases

| 阶段 | 目标 |
|------|------|
| 阶段1 | 大纲Agent：对话收集想法 → 生成大纲 → 确认 |
| 阶段2 | 大纲Agent：加入卷纲、单元纲 |
| 阶段3 | 写作Agent + 审核Agent |
| 阶段4 | 单元衔接、多章节循环 |

## Language Preference

**请使用中文回答问题和交流。**

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
4. **Bug 修复使用 `superpowers:systematic-debugging`** - 不得盲目修改
5. **完成前使用 `superpowers:verification-before-completion`** - 运行验证命令
6. **避免过度设计** - 初版专注跑通流程，代码丑一点没关系

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

## 项目教训

本项目前身 inkworkflow 因"想得太复杂"导致开发陷入泥潭。

**核心原则：先跑通再优化**
- 初版代码丑没关系，能跑就行
- 不要预留架构，不要过度抽象
- 从实践中自然抽象框架，不要先写框架再填内容