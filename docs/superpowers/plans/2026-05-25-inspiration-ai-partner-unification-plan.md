# 灵感页面重构 实现计划

## 总览

将灵感收集从"固定表单 + 独立聊天"改为"AI搭档对话驱动 + 灵感简报"模式。
AI搭档通过新增工具维护灵感简报，`outline_generation_node` 直接使用简报作为输入。

## 任务分解

### Task 1: 后端 — AI搭档新增灵感简报工具

**新增文件：**

1. `backend/app/agents/services/inspiration_service.py`
   - `read_inspiration_brief(db, project_id)` — 从 Outline 读取 `inspiration_template`
   - `update_inspiration_brief(db, project_id, brief)` — 更新 `outline.inspiration_template`

**修改文件：**

2. `backend/app/agents/agent_tools.py`
   - 新增 `read_inspiration_brief` tool
   - 新增 `update_inspiration_brief` tool

### Task 2: 后端 — AI搭档阶段感知

**修改文件：**

1. `backend/app/agents/agent_graph.py`
   - `create_agent_graph()` 增加 `stage` 参数
   - 灵感阶段限制工具集为读取类 + 简报工具 + update_outline

2. `backend/app/api/agent.py`
   - `agent_chat()` 读取 `workflow_state.stage`
   - 灵感阶段：注入 `inspiration_brief` 到上下文、使用灵感专用系统提示
   - 灵感阶段：限制可用工具（不暴露 generate_chapter_content 等）
   - 系统提示从硬编码改为按阶段选择

3. `backend/app/agents/agent_context.py`
   - `build_project_context()` 增加 `inspiration_brief` 返回字段（灵感阶段时）

4. `backend/app/agents/prompts.py`
   - 新增 `AGENT_INSPIRATION_SYSTEM_PROMPT` — 灵感阶段系统提示

### Task 3: 后端 — 移除独立灵感聊天

**修改文件：**

1. `backend/app/api/inspiration.py`
   - 移除 `chat` 端点、`_infer_fields_from_text()`、`_get_missing_fields()`
   - 保留 `confirm` 端点（简化逻辑）

2. `backend/app/agents/prompts.py`
   - 移除 `INSPIRATION_EXTRACTION_PROMPT`、`INSPIRATION_QUESTION_PROMPT`

3. `backend/app/agents/constants.py`
   - 移除 `FIELD_INFERENCE_RULES`、`INSPIRATION_REQUIRED_FIELDS`（验证无其他引用）

### Task 4: 后端 — prepare_outline_prompt 和 confirm_outline 重构

**修改文件：**

1. `backend/app/agents/nodes/outline_generation.py`
   - `prepare_outline_prompt()` 重写：
     - 优先使用 `state["inspiration_template"]`（灵感简报）作为prompt主体
     - 从简报中提取或默认目标字数 → 计算章节数
     - 移除对 `collected_info` 旧字段名（novelType/targetReader/era/maleLead等20+字段）的依赖
     - `inspiration_template` 为空时回退从 `collected_info` 构建简易prompt（向后兼容）

2. `backend/app/api/outline.py`
   - `confirm_outline()` 移除 `collected_info.targetWords`/`wordsPerChapter` 读取
   - 章节数使用 `outline.chapter_count_suggested`（已在 outline_generation_node 中设置）

### Task 5: 前端 — 移除旧表单组件

**删除文件：**
- `InspirationForm.tsx`
- `InspirationFieldGroup.tsx`
- `InspirationTemplatePreview.tsx`
- `useInspirationForm.ts`
- `frontend/src/lib/inspiration/templates.ts`
- `frontend/src/lib/inspiration/utils.ts`
- `frontend/src/lib/inspiration/types.ts`

**保留：**
- `frontend/src/lib/inspiration/config.ts` — 选项数据
- `frontend/src/lib/inspiration/index.ts` — 精简只导出 config

**修改：**
- 检查并移除所有对上述被删文件的 import 引用

### Task 6: 前端 — 新建灵感简报 + 重写 InspirationPanel

**新增文件：**

1. `frontend/src/components/workbench/planning/InspirationBrief.tsx`
   - 渲染Markdown格式的灵感简报
   - 只读模式 / 编辑模式切换
   - 编辑模式使用 TipTap 编辑器
   - Props: `brief: string`, `onBriefChange: (brief: string) => void`, `readOnly?: boolean`

**修改文件：**

2. `frontend/src/components/workbench/planning/InspirationPanel.tsx`
   - 新布局：左栏 InspirationBrief + 右栏AI搭档
   - 监听AI搭档 SSE 事件，检测 `update_inspiration_brief` tool调用 → 更新简报
   - 确认按钮触发 workflow 运行（不再调用 `collectedInfoApi.update`）

3. `frontend/src/stores/workbenchStore.ts`
   - 移除：`inspirationFields`, `inspirationFieldStatus`, `setInspirationField`, `setInspirationFieldStatus`, `setInspirationFields`
   - 新增：`inspirationBrief: string`, `setInspirationBrief`

### Task 7: 测试和验证

1. 删除 `useInspirationForm.test.ts`
2. 更新 `workbenchStore.inspiration.test.ts` — 适配新状态
3. 新增 `inspiration_service` 单元测试
4. 运行后端测试：`docker exec novelagent-backend-1 pytest -v`
5. 运行前端测试：`cd frontend && npm run test:run`
6. 端到端测试：
   - 新项目 → AI对话 → 简报更新 → 确认 → 大纲生成正常
   - 旧项目 → 大纲生成仍正常（向后兼容回退路径）

## 执行顺序

Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7

Task 1-4 在后端容器内完成，Task 5-6 在前端完成。Task 1-2 可并行。