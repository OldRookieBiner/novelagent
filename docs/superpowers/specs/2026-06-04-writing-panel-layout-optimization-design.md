# 写作页面布局优化 — 设计文档

日期：2026-06-04
状态：已确认

## 概述

精简写作标签页的栏布局，去掉两个冗余面板：WorkbenchLayout 的外层左栏（写作页下数据从未正确填充）和 WritingPanel 内的 AI 审核面板（功能已被右侧 Agent 完全覆盖）。写作空间从 4-5 栏压缩到 3 栏。

## 变更

### 1. WorkbenchLayout 左栏：写作页不显示

**当前**：`showChapterList` 在 `activeTab === 'writing' || activeTab === 'tracking'` 时为 true。
**改为**：仅 `activeTab === 'tracking'` 时为 true，写作页不再渲染外层 `ChapterListPanel`。

- 文件：`ProjectWorkbench.tsx` 第 107 行，将 `showChapterList` 的条件改为 `activeTab === 'tracking'`
- WritingPanel 内部有自己的章节列表（`chapterOutlinesApi.list()`），不受影响

### 2. AIAssistantPanel 审核栏：移除

**当前**：WritingPanel 渲染 `AIAssistantPanel` 作为右侧审核面板（360px，可折叠至 48px）。
**改为**：完全移除。

具体改动：

- `WritingPanel.tsx`：
  - 删除 `AIAssistantPanel` 的 import 和渲染
  - 删除以下 state 和回调：`rightCollapsed`、`rewriting`、`handleRewriteChunk`、`handleRewriteDone`、`handleReviewCleared`、`handleReviewComplete`、`handleIssueClick`
  - 删除 `initialReviewResultMemo`（useMemo）和 `ChapterNodePanel` import（保留章节点功能）
  - 删除 `rewriteAccumulatedRef`
  - 删除相关 import：`Eye`, `Pencil`? 不，这些还在用。需要删除的 import：AIAssistantPanel 组件，以及不再需要的 `mapReviewResult`
  - 保留 `mode`（预览/编辑切换）、`chapterNode`/`showChapterNode`（章节点确认卡片，这是生成前确认，不是审核）

- `AIAssistantPanel.tsx`：暂不删除文件，标记为废弃（后续清理），避免影响其他引用。但检查是否有其他地方引用。

### 3. 不删除的文件

- `AIAssistantPanel.tsx` — 保留文件但不再被渲染，后续版本清理
- `ChapterListPanel.tsx` — 仍在 tracking 标签页使用

## 影响范围

- 无后端变更
- 无类型变更
- 无 store 变更
- 纯 UI 精简，不影响任何数据流或功能

## 验证

1. 打开任意项目的写作标签页 → 确认无外层左栏、无审核栏
2. 打开 tracking 标签页 → 确认外层左栏仍正常显示
3. 切换到其他标签页（知识库、结构）→ 确认不受影响
4. 写作页章节列表、编辑器、AI 生成、保存 → 功能正常
5. 右侧 Agent 面板正常 → 审核/重写对话功能正常
