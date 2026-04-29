# 工作台页面 API 对接设计文档

## 概述

**版本**: v0.8.1
**日期**: 2026-04-29
**目标**: 为工作台页面对接后端 API，实现完整的 CRUD 和 AI 生成功能

### 对接范围（Phase 1: 创作模块）

| 模块 | 功能 | 优先级 |
|------|------|--------|
| 小说大纲 | 获取、更新、生成、确认 | P0 |
| 章节大纲 | 列表、编辑、确认、生成 | P0 |
| 写作 | 内容读取、保存、生成、审核 | P0 |

### 现有组件（不修改布局）

- `OutlinePanel.tsx` - 大纲编辑面板
- `ChapterOutlinePanel.tsx` - 章节大纲面板
- `WritingPanel.tsx` - 写作面板
- `AIAssistantPanel.tsx` - AI 助手面板

---

## API 端点汇总

### 大纲 API (`/api/projects/{id}/outline`)

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/projects/{id}/outline` | 获取大纲 |
| PUT | `/projects/{id}/outline` | 更新大纲 |
| POST | `/projects/{id}/outline` | AI 生成大纲（SSE） |
| POST | `/projects/{id}/outline/confirm` | 确认大纲 |

### 章节大纲 API (`/api/projects/{id}/chapter-outlines`)

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/projects/{id}/chapter-outlines` | 获取章节大纲列表 |
| PUT | `/projects/{id}/chapter-outlines/{num}` | 更新章节大纲 |
| POST | `/projects/{id}/chapter-outlines/{num}/confirm` | 确认章节大纲 |
| POST | `/projects/{id}/chapter-outlines` | AI 批量生成（SSE） |

### 章节内容 API (`/api/projects/{id}/chapters/{num}`)

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/projects/{id}/chapters/{num}` | 获取章节内容 |
| PUT | `/projects/{id}/chapters/{num}` | 保存章节内容 |
| POST | `/projects/{id}/chapters/{num}/generate` | AI 生成内容（SSE） |
| POST | `/projects/{id}/chapters/{num}/review` | AI 审核 |

---

## 文件变更规划

### 新增文件

```
frontend/src/lib/outlineApi.ts     # 大纲 API 客户端
frontend/src/lib/chapterApi.ts     # 章节 API 客户端
```

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/components/workbench/creation/OutlinePanel.tsx` | 对接大纲 API |
| `frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx` | 对接章节大纲 API |
| `frontend/src/components/workbench/creation/WritingPanel.tsx` | 对接写作/审核 API |
| `frontend/src/components/workbench/creation/AIAssistantPanel.tsx` | 实现 AI 助手功能 |

---

## 实现顺序

1. **创建 API 客户端** - `outlineApi.ts` 和 `chapterApi.ts`
2. **大纲页面** - 对接 OutlinePanel
3. **章节大纲页面** - 对接 ChapterOutlinePanel
4. **写作页面** - 对接 WritingPanel + AIAssistantPanel

---

## 约束条件

- 不修改现有 UI 布局和样式
- 保持现有的组件结构
- 使用项目现有的 `request` 封装进行 API 调用
- SSE 流式处理使用现有的 `sseParser` 工具