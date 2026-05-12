# 工作台状态持久化优化设计

## 问题概述

### 问题1：灵感页面规划完成后按钮状态不更新

**现象**：灵感页面完成规划后，"开始规划"按钮没有变为"重新规划"，点击会弹出"保存失败"报错。刷新页面后按钮才正确显示"重新规划"。

**根因**：规划完成后 `onComplete` 回调为空函数 `() => {}`，outline 数据未刷新，`hasOutline` prop 仍为 false。

**代码路径**：
- `InspirationPanel.tsx:1139` — `onComplete={() => {}}`
- `ProjectWorkbench.tsx:42` — `hasOutline={!!outline?.title}`
- `useProjectData.ts` — 已有 `refreshOutline` 方法但未被调用

### 问题2：章节大纲生成时切换标签页丢失进度

**现象**：章节大纲正在生成时切换标签页再切回来，已生成的章节大纲内容和进度条全部清空。

**根因**：`ChapterOutlinePanel` 使用 React 本地状态（`chapters`、`progress`、`generating`），组件卸载后状态丢失。后端 SSE 流仍在继续，但前端无法恢复显示。

**代码路径**：
- `ChapterOutlinePanel.tsx` — `useState` 管理章节列表和进度
- `ProjectWorkbench.tsx:32-33` — 标签页切换时组件直接卸载

---

## 设计方案

### 问题1修复：规划完成后刷新 outline 数据

**方案**：在 `onComplete` 回调中调用 `refreshOutline()`，使 outline 数据立即更新。

**具体修改**：

1. **InspirationPanel.tsx**：接收 `onPlanningComplete` prop（或直接传入 refreshOutline）

2. **ProjectWorkbench.tsx**：将 `refreshOutline` 传入 InspirationPanel

3. **InspirationPanel.tsx**：在 `onComplete` 回调中调用 `onPlanningComplete`

**数据流**：
```
规划完成 → OutlineProgressDialog.onComplete → onPlanningComplete()
→ refreshOutline() → outline 数据更新 → hasOutline=true → 按钮变为"重新规划"
```

**影响范围**：仅 InspirationPanel 和 ProjectWorkbench，不涉及后端。

### 问题2修复：章节大纲状态提升到 Zustand store

**方案**：将 `ChapterOutlinePanel` 中的生成相关状态提升到 `workflowStore`，组件卸载后状态保留在 store 中，重新挂载时从 store 恢复。

**需要提升的状态**：

| 状态 | 当前位置 | 提升后 |
|------|----------|--------|
| `chapters` | `useState<ChapterOutline[]>` | `workflowStore.chapterOutlines`（已有） |
| `progress` | `useState` | `workflowStore.chapterOutlineProgress`（新增） |
| `generating` | `useState` | `workflowStore.chapterOutlineGenerating`（新增） |
| `replaning` | `useState` | `workflowStore.chapterOutlineReplaning`（新增） |
| `abortControllerRef` | `useRef` | `workflowStore.chapterOutlineAbortController`（新增） |

**具体修改**：

1. **workflowStore.ts**：新增章节大纲生成相关状态和 actions

2. **ChapterOutlinePanel.tsx**：将本地状态替换为 store 状态

3. **组件挂载逻辑**：
   - 如果 store 中 `generating=true`，说明后台 SSE 流仍在进行
   - 如果 store 中已有 `chapters` 数据，直接显示
   - 如果 SSE 流已结束但 store 未清理，组件挂载时从后端刷新一次数据

**SSE 流处理**：

- 切换标签页时组件卸载，但 SSE 流（fetch + ReadableStream）继续运行
- SSE 回调中更新 store 状态（而非本地 state），数据持久化
- 切回来时组件从 store 读取状态，恢复显示

**注意事项**：

- SSE 流的 `onProgress`、`onDone`、`onError` 回调需更新 store 而非本地 state
- `onDone` 完成后应清理 `generating` 标志
- 组件卸载时不 abort SSE 流（用户可能在生成中切走再切回）
- 用户主动取消生成时才 abort 并清理状态

---

## 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/stores/workflowStore.ts` | 新增 chapterOutlineProgress、chapterOutlineGenerating、chapterOutlineReplaning、chapterOutlineAbortController 状态和 actions |
| `frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx` | 本地状态替换为 store 状态；SSE 回调更新 store |
| `frontend/src/components/workbench/planning/InspirationPanel.tsx` | 接收 onPlanningComplete prop，onComplete 回调调用刷新 |
| `frontend/src/pages/ProjectWorkbench.tsx` | 传入 refreshOutline 给 InspirationPanel |

---

## 不涉及的变更

- 后端 LangGraph 节点逻辑不变
- SSE 事件格式不变
- API 端点不变
- 其他面板（OutlinePanel、WritingPanel 等）不变
