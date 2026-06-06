# 去掉追踪标签页最左栏（ChapterListPanel）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 去掉追踪标签页最左栏的 ChapterListPanel，使追踪标签页从三栏变为两栏布局

**Architecture:** 修改 `ProjectWorkbench.tsx` 和 `WorkbenchLayout.tsx` 中的 `showChapterList` 逻辑，不再在追踪标签页显示章节列表栏。保留组件文件以备未来使用。

**Tech Stack:** React, TypeScript, Tailwind CSS

---

### Task 1: 修改 ProjectWorkbench.tsx — 关闭追踪标签页的章节列表

**Files:**
- Modify: `frontend/src/pages/ProjectWorkbench.tsx:101`

- [ ] **Step 1: 将 `showChapterList` 从条件表达式改为 `false`**

将第 101 行：
```typescript
const showChapterList = activeTab === 'tracking'
```
改为：
```typescript
const showChapterList = false
```

- [ ] **Step 2: 验证修改**

运行: `cd /Users/biner/Dev/novelagent/frontend && npx tsc --noEmit`
预期: 无类型错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/ProjectWorkbench.tsx
git commit -m "fix(frontend): 去掉追踪标签页最左栏章节列表"
```

---

### Task 2: 修改 WorkbenchLayout.tsx — 将 showChapterList 默认值改为 false

**Files:**
- Modify: `frontend/src/components/workbench/WorkbenchLayout.tsx:53`

- [ ] **Step 1: 将默认值从 `true` 改为 `false`**

将解构默认值：
```typescript
showChapterList = true,  // 默认显示
```
改为：
```typescript
showChapterList = false,  // 默认不显示章节列表
```

- [ ] **Step 2: 验证修改**

运行: `cd /Users/biner/Dev/novelagent/frontend && npx tsc --noEmit`
预期: 无类型错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/workbench/WorkbenchLayout.tsx
git commit -m "fix(frontend): showChapterList 默认值改为 false"
```

---

### Task 3: 浏览器验证

- [ ] **Step 1: 启动前端开发服务**

```bash
cd /Users/biner/Dev/novelagent && docker compose up -d frontend
```

- [ ] **Step 2: 验证追踪标签页**

打开工作台，切换到追踪标签页，确认：
- 最左栏（章节列表）已消失
- 分区导航（伏笔追踪/时间线/风格统计/节奏分析）正常显示
- 内容区正常渲染

- [ ] **Step 3: 验证其他标签页**

切换到写作/知识库/结构标签页，确认布局无异常
