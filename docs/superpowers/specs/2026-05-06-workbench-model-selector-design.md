# 工作台全局模型选择器设计

## Context

章节大纲面板缺少模型选择器，用户无法在生成章节大纲时选择 LLM 模型。目前只能使用默认模型，若默认模型配额用完或不适合此任务，只能去设置页切换。灵感面板已有模型选择器，章节大纲面板和章节正文面板应与灵感面板的模型选择同步。

## 设计方案

### 核心思路：灵感面板为模型选择入口，全局同步

保留灵感面板底部的模型选择器作为唯一选择入口，选择结果存储到 workbenchStore，章节大纲面板和章节正文面板从 store 读取，三处始终同步。

### 数据流

1. 用户在灵感面板选择模型 → `selectedModelKey` 存入 workbenchStore
2. 章节大纲面板生成时，从 workbenchStore 读取 `selectedModelKey`
3. 章节正文面板写作时，从 workbenchStore 读取 `selectedModelKey`
4. 任何面板生成的 AI 内容都使用同一模型

### 交互行为

| 场景 | 行为 |
|------|------|
| 灵感面板选择模型 | 更新 workbenchStore.selectedModelKey，全局生效 |
| 批量生成章节大纲 | 使用 store 中的 selectedModelKey，传 llm_config_id 给 API |
| 章节正文写作 | 使用 store 中的 selectedModelKey，传 llm_config_id 给 API |
| 生成进行中 | 灵感面板选择器禁用（disabled），防止中途切换 |

### 灵感面板变更

- `selectedModelKey` 从组件本地状态提升到 workbenchStore
- 选择器 UI 保留不变（位置、样式均不改）
- 初始化时从 store 恢复选择

### 章节大纲面板变更

- 生成时从 workbenchStore 读取模型，传 llmConfigId 给 API

### 关键文件

| 文件 | 变更 |
|------|------|
| `frontend/src/stores/workbenchStore.ts` | 新增 selectedModelKey 状态 |
| `frontend/src/components/workbench/planning/InspirationPanel.tsx` | selectedModelKey 改用 workbenchStore |
| `frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx` | 从 store 读取模型，传 llmConfigId |
