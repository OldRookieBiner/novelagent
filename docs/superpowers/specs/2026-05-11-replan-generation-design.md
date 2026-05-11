# 重新生成规划 — 设计文档

## 背景

当前规划生成（大纲 → 人物 → 关系）存在两个问题：

1. **失败后无法重试**：如果 AI 模型限流或欠费导致生成中途失败，用户关闭进度弹窗后无法再次触发生成，只能重建项目
2. **无法重新规划**：如果用户对已生成的大纲/人物/关系不满意，无法重新生成，一个项目只有一次规划机会

根因：
- 前端 `OutlineProgressDialog` 的重试逻辑依赖 `workflowCleanupApi.cleanup()`，但后端**没有注册** `/workflow/cleanup` 端点，清理静默失败
- 规划成功后灵感面板没有"重新规划"入口，"开始规划"按钮不再显示
- 缺少重新规划的业务端点，无法安全地清理旧数据并重新运行工作流

## 设计方案

### 核心思路

新增 `POST /workflow/replan` 端点，统一处理数据清理和工作流重启。前端灵感面板在规划完成后显示"重新规划"按钮。

### 1. 后端：新增 `POST /workflow/replan` 端点

**路径**：`POST /api/projects/{project_id}/workflow/replan`

**请求体**：
```python
class WorkflowReplanRequest(BaseModel):
    llm_config_id: Optional[int] = None
    llm_model_name: Optional[str] = None
```

**执行步骤**：

1. 验证项目所有权
2. 清理检查点：删除该项目所有 WorkflowCheckpoint
3. 重置 WorkflowState：stage → `inspiration`，清除 waiting_for_confirmation
4. 重置 Outline：清除生成字段（title, summary, plot_points, characters, world_setting, emotional_curve），保留 collected_info（灵感数据），confirmed → False
5. 删除旧数据：Character、Relation、ChapterOutline（含关联的 Chapter）
6. 构建新的 initial_state，预加载 prompts
7. 通过 `stream_workflow_events` 启动 LangGraph 工作流（SSE 流式）
8. 返回 StreamingResponse

**数据策略**：先清理再生成。工作流每个节点完成后自动持久化到数据库，中途失败时已完成节点的数据保留，用户可再次重试。

**关键代码位置**：`backend/app/api/workflow.py`

### 2. 后端：修复缺失的 `POST /workflow/cleanup` 端点

**路径**：`POST /api/projects/{project_id}/workflow/cleanup`

**逻辑**：仅清理检查点，不删业务数据。用于 `OutlineProgressDialog` 重试时的轻量清理。

**关键代码位置**：`backend/app/api/workflow.py`

### 3. 前端：灵感面板"重新规划"按钮

**位置**：`frontend/src/components/workbench/planning/InspirationPanel.tsx`

**逻辑**：
- 规划未运行时：显示"开始规划"按钮（现有逻辑不变）
- 规划已完成时（outline 有标题，或 stage 超过 inspiration）：显示"重新规划"按钮
- 点击"重新规划"：弹出确认对话框（"重新规划将清除当前大纲、人物和关系数据，是否继续？"）
- 确认后：调用 replan 端点，弹出 OutlineProgressDialog 显示进度

**判断条件**：通过 props 传入 outline 是否存在（从父组件 ProjectWorkbench 获取）

### 4. 前端：OutlineProgressDialog 复用

**位置**：`frontend/src/components/workbench/planning/OutlineProgressDialog.tsx`

**修改**：
- 新增 `isReplan?: boolean` prop
- `isReplan=true` 时调用 `/workflow/replan`，否则调用 `/workflow/run`
- `isReplan=true` 时不调用 `workflowCleanupApi.cleanup()`（replan 端点内部已处理）

### 5. 前端：workflowApi 新增 replan 方法

**位置**：`frontend/src/lib/workflowApi.ts`

新增 `replanWorkflow(projectId, callbacks, options)` 方法，与 `runWorkflow` 结构一致，仅 URL 不同。

### 6. 数据流

```
用户点击"重新规划"
  → 确认对话框
  → 调用 POST /workflow/replan
    → 后端清理检查点 + 重置 WorkflowState + 清理旧业务数据
    → 构建 initial_state（stage=inspiration，collected_info 保留）
    → 启动 LangGraph 工作流
      → outline_generation_node（生成新大纲）
      → create_characters_from_outline_node（生成新人物）
      → generate_relations_node（生成新关系）
    → SSE 流式返回进度
  → OutlineProgressDialog 显示进度
  → 完成/失败
```

## 影响范围

| 文件 | 改动 |
|------|------|
| `backend/app/api/workflow.py` | 新增 replan、cleanup 端点 |
| `frontend/src/lib/workflowApi.ts` | 新增 replanWorkflow 方法 |
| `frontend/src/components/workbench/planning/InspirationPanel.tsx` | 添加"重新规划"按钮和确认逻辑 |
| `frontend/src/components/workbench/planning/OutlineProgressDialog.tsx` | 新增 isReplan prop，切换端点 |

## 不涉及

- 不修改 LangGraph 图结构（graph.py）或节点逻辑
- 不修改 NovelState 定义
- 不修改数据库 schema
- 不支持部分重新生成（仅全部重新生成）
