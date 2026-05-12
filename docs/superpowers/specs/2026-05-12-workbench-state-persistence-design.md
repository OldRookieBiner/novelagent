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

**根因**：SSE 流管理在 `ChapterOutlinePanel` 组件内部，与组件生命周期绑定。组件卸载时 `useEffect` cleanup 调用 `abortControllerRef.current.abort()` 终止 SSE 流，状态随之丢失。

**代码路径**：
- `ChapterOutlinePanel.tsx:83-93` — useEffect cleanup 中 abort SSE
- `ChapterOutlinePanel.tsx:283-365` — handleReplanChapterOutlines 在组件内管理 SSE
- `ProjectWorkbench.tsx:32-33` — 标签页切换时组件直接卸载

---

## 设计方案

### 问题1修复：规划完成后刷新 outline 数据

**方案**：在 `onComplete` 回调中调用 `refreshOutline()`，使 outline 数据立即更新。

**具体修改**：

1. **InspirationPanel.tsx**：新增 `onPlanningComplete` prop
2. **ProjectWorkbench.tsx**：将 `refreshOutline` 传入 InspirationPanel
3. **InspirationPanel.tsx**：在 `onComplete` 回调中调用 `onPlanningComplete`

**数据流**：
```
规划完成 → OutlineProgressDialog.onComplete → onPlanningComplete()
→ refreshOutline() → outline 数据更新 → hasOutline=true → 按钮变为"重新规划"
```

**影响范围**：仅 InspirationPanel 和 ProjectWorkbench，不涉及后端。

### 问题2修复：SSE 流管理提升到 workflowStore

**核心理念**：将 SSE 流的创建、回调、状态管理从组件内提升到 `workflowStore`，使 SSE 生命周期与组件解耦。

**架构变化**：

```
当前架构（问题根因）：
ChapterOutlinePanel (组件内部)
├── AbortController (组件局部变量)
├── useState: chapters, progress, generating
├── SSE 回调 → 更新本地 state
└── useEffect cleanup → abort() 终止 SSE
→ 标签页切换 → 组件卸载 → SSE 流断开 → 进度丢失

改进后架构：
workflowStore (全局 store)
├── AbortController (store 持有)
├── state: chapterOutlineProgress, chapterOutlineGenerating 等
├── startReplanChapterOutlines() action
│   └── 调用 workflowApi.replanChapterOutlines()
│       └── 回调 → 更新 store 状态
└── (组件卸载不触发 abort)
→ 标签页切换 → 组件卸载 → Store 保留 → SSE 继续 → 进度保留
```

**新增 store 状态**：

| 状态 | 类型 | 说明 |
|------|------|------|
| `chapterOutlineProgress` | `{ current: number; total: number; currentTitle?: string; completed?: string[] } \| null` | 生成进度 |
| `chapterOutlineGenerating` | `boolean` | 是否正在生成 |
| `chapterOutlineReplaning` | `boolean` | 是否正在重新生成 |
| `chapterOutlineAbortController` | `AbortController \| null` | SSE 流取消控制器 |

**新增 store actions**：

| Action | 说明 |
|--------|------|
| `startGenerateChapterOutlines(projectId, llmConfigId)` | 启动章节大纲生成 SSE 流 |
| `startReplanChapterOutlines(projectId, llmConfigId)` | 启动章节大纲重新生成 SSE 流 |
| `cancelChapterOutlineGeneration()` | 取消生成（abort SSE + 清理状态） |
| `clearChapterOutlineProgress()` | 清理进度状态（生成完成后调用） |

**SSE 回调处理**（在 store action 内部）：

- `onProgress`：更新 `chapterOutlines`（复用已有 action `addChapterOutline`）和 `chapterOutlineProgress`
- `onDone`：重置 `chapterOutlineGenerating`/`chapterOutlineReplaning`，清理 `chapterOutlineAbortController`，从后端刷新完整数据
- `onError`：重置所有生成状态，显示错误 toast

**ChapterOutlinePanel 修改**：

1. 移除本地 `generating`、`replaning`、`progress`、`abortControllerRef` 状态
2. 从 store 读取：`const { generating, replaning, progress } = useWorkflowStore()`
3. 调用 store action 启动生成：`startReplanChapterOutlines(projectId, llmConfigId)`
4. **移除** useEffect cleanup 中的 `abort()` 调用
5. 保留 `chapters` 本地状态用于编辑交互（非生成相关）

**组件挂载恢复逻辑**：

- 挂载时检查 store 中 `chapterOutlineGenerating` 或 `chapterOutlineReplaning`
- 如果为 true，说明 SSE 流仍在进行，直接从 store 读取进度
- 如果为 false 但 `chapterOutlineProgress` 有残留，说明上次的流已完成但未清理，从后端刷新数据

---

## 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/stores/workflowStore.ts` | 新增章节大纲生成状态和 actions（含 SSE 流管理） |
| `frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx` | 本地状态替换为 store；调用 store action 启动 SSE；移除 useEffect abort |
| `frontend/src/components/workbench/planning/InspirationPanel.tsx` | 新增 onPlanningComplete prop，onComplete 回调调用刷新 |
| `frontend/src/pages/ProjectWorkbench.tsx` | 传入 refreshOutline 给 InspirationPanel |

---

## 改动评估

| 维度 | 评估 |
|------|------|
| 改动文件数 | 4 个前端文件 |
| 后端改动 | 无 |
| API 层改动 | 无（workflowApi.ts、sseParser.ts 不动） |
| 其他面板影响 | 无 |
| 用户操作流程 | 完全不变 |
| 系统稳定性 | 低风险，逻辑不变只是状态位置从组件挪到 store |
| 技术债 | 无，是项目架构的自然演进 |

---

## 不涉及的变更

- 后端 LangGraph 节点逻辑不变
- SSE 事件格式不变
- API 端点不变
- 其他面板（OutlinePanel、WritingPanel 等）不变
