# 灵感页面重构 实现计划

## 总览

将灵感收集从"固定表单 + 独立聊天"改为"AI搭档对话驱动 + 灵感简报"模式。

## 任务分解

### Task 1: 后端 — 移除独立灵感聊天，扩展AI搭档

**文件变更：**

1. `backend/app/api/inspiration.py`
   - 移除 `chat` 端点（保留 `confirm` 端点，简化逻辑）

2. `backend/app/agents/agent_context.py`
   - 灵感阶段（stage=inspiration）注入 `inspiration_brief` 到系统提示

3. `backend/app/agents/agent_graph.py`
   - 灵感阶段使用专用的灵感系统提示
   - 提示指导AI：引导用户描述创意 → 提取关键信息 → 维护灵感简报

4. `backend/app/agents/prompts.py`
   - 移除 `INSPIRATION_EXTRACTION_PROMPT` 和 `INSPIRATION_QUESTION_PROMPT`
   - 新增 `INSPIRATION_AGENT_PROMPT`（灵感阶段的AI搭档系统提示）

5. `backend/app/agents/constants.py`
   - 移除 `FIELD_INFERENCE_RULES` 和 `INSPIRATION_REQUIRED_FIELDS`

6. `backend/app/models/outline.py`
   - `collected_info` 改为存储 `{inspiration_brief: str}` 文本

### Task 2: 前端 — 移除旧表单组件

**删除文件：**
- `frontend/src/components/workbench/planning/InspirationForm.tsx`
- `frontend/src/components/workbench/planning/InspirationFieldGroup.tsx`
- `frontend/src/components/workbench/planning/InspirationTemplatePreview.tsx`
- `frontend/src/components/workbench/planning/useInspirationForm.ts`
- `frontend/src/lib/inspiration/templates.ts`
- `frontend/src/lib/inspiration/utils.ts`
- `frontend/src/lib/inspiration/types.ts`

**保留：**
- `frontend/src/lib/inspiration/config.ts` — 选项数据供AI系统提示参考
- `frontend/src/lib/inspiration/index.ts` — 精简后只导出 config

### Task 3: 前端 — 新建灵感简报组件

**新增文件：**

1. `frontend/src/components/workbench/planning/InspirationBrief.tsx`
   - 渲染Markdown格式的灵感简报
   - 支持只读模式 / 编辑模式切换
   - 编辑模式下使用 TipTap 编辑器

### Task 4: 前端 — 重写 InspirationPanel

**修改文件：**

1. `frontend/src/components/workbench/planning/InspirationPanel.tsx`
   - 新布局：左栏 InspirationBrief + 右栏AI搭档
   - 监听AI搭档 SSE 事件，提取 `ai_update` 类型更新简报内容
   - 确认按钮触发 `collectedInfoApi.update(projectId, {inspiration_brief})`

2. `frontend/src/stores/workbenchStore.ts`
   - 移除：`inspirationFields`, `inspirationFieldStatus`, `setInspirationField`, `setInspirationFieldStatus`, `setInspirationFields`
   - 新增：`inspirationBrief: string`, `setInspirationBrief`

### Task 5: 后端 — 大纲生成使用灵感简报

**修改文件：**

1. `backend/app/agents/nodes/outline_generation.py`
   - `prepare_outline_prompt()` 直接使用 `state["inspiration_brief"]` 替代模板拼装

2. `backend/app/api/workflow.py`
   - `build_initial_state()` 从 Outline 读取 `inspiration_brief` 传入 NovelState

### Task 6: 测试和验证

1. 更新受影响的测试文件：
   - `useInspirationForm.test.ts` — 删除
   - `workbenchStore.inspiration.test.ts` — 更新为新状态
2. 运行后端测试：`docker exec novelagent-backend-1 pytest -v`
3. 运行前端测试：`cd frontend && npm run test:run`
4. 手动端到端测试：创建项目 → 对话 → 简报更新 → 确认 → 大纲生成

## 执行顺序

Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6
