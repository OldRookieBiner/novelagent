# 灵感页面重构：AI搭档统一与灵感简报模式

## Context

当前灵感页面存在三套独立系统：固定44字段表单、灵感聊天（`/inspiration/chat`）、AI搭档（ReAct Agent）。三者互不依赖，用户困惑。固定表单字段限制了创作灵活性。需统一为一套以AI搭档为核心的对话驱动灵感收集流程。

## 设计决策

### 核心理念

AI搭档是唯一交互入口。用户跟AI聊天描述创意，AI通过专用工具实时维护一份"灵感简报"——一份连贯的叙事性创意文档。简报存储在 `outline.inspiration_template` 字段中（复用现有列），既是给人看的创作摘要，也是后续大纲生成的输入。

### 关键决策

| 决策 | 说明 |
|------|------|
| 合并灵感聊天到AI搭档 | 移除 `/inspiration/chat`，AI搭档统一处理灵感阶段对话 |
| 移除固定表单 | 去掉44字段的 InspirationForm，改为AI动态驱动的灵感简报 |
| 简报存储在 `outline.inspiration_template` | 复用现有Text列，`build_initial_state` 已从此列读取 |
| AI搭档固定在右栏 | 与全站布局一致 |
| 模型选择在AI搭档标题栏 | 读取已配置模型列表 |
| AI搭档阶段感知 | `agent_chat()` 根据项目 stage 切换系统提示和可用工具 |

### 页面布局

```
┌─────────────────────────────────┬──────────────────┐
│ 📝 创作灵感简报                  │   🤖 AI 搭档     │
│                                 │   [模型选择器]    │
│ AI实时整理的创意文档             │                  │
│ 支持只读/编辑模式切换            │   对话区          │
│                                 │                  │
│                                 │                  │
│ [✏️ 手动编辑] [确认并生成设定 →]  │   输入框          │
└─────────────────────────────────┴──────────────────┘
```

## 前端变更

### 新增

- `InspirationBrief.tsx` — 灵感简报展示组件。渲染Markdown文档，支持只读/编辑模式切换

### 修改

- `InspirationPanel.tsx` — 重写为简报 + AI搭档布局。监听AI搭档 `agent_text` SSE事件，更新简报内容
- `workbenchStore.ts` — 移除 `inspirationFields`/`inspirationFieldStatus` 及相关 setter，新增 `inspirationBrief: string` + `setInspirationBrief`

### 移除

- `InspirationForm.tsx`
- `InspirationFieldGroup.tsx`
- `InspirationTemplatePreview.tsx`
- `useInspirationForm.ts`
- `frontend/src/lib/inspiration/templates.ts`
- `frontend/src/lib/inspiration/utils.ts`
- `frontend/src/lib/inspiration/types.ts`

### 保留

- `frontend/src/lib/inspiration/config.ts` — 选项数据供AI搭档灵感阶段系统提示参考
- `OutlineProgressDialog.tsx` — 确认后进度弹窗逻辑不变

## 后端变更

### 新增

1. **AI搭档工具** — 在 `agent_tools.py` 新增：
   - `read_inspiration_brief(project_id)` — 读取当前灵感简报
   - `update_inspiration_brief(project_id, brief: str)` — 更新灵感简报
   - 对应 `agent_services/inspiration_service.py` 服务层

2. **AI搭档阶段系统提示** — `agent_chat()` 根据 `workflow_state.stage` 选择不同系统提示：
   - `stage == "inspiration"` → 灵感阶段提示：引导用户描述创意、维护简报、判断信息完整度
   - 其他阶段 → 保持现有提示

3. **灵感阶段系统提示** — 在 `prompts.py` 新增 `AGENT_INSPIRATION_SYSTEM_PROMPT`

### 修改

1. `backend/app/api/agent.py` — `agent_chat()` 增加阶段感知：
   - 读取 `workflow_state.stage`
   - 灵感阶段：注入 `inspiration_brief` 到上下文、使用灵感专用系统提示
   - 灵感阶段：限制工具集为读取类 + 灵感简报工具（不应暴露章节生成等工具）

2. `backend/app/agents/agent_context.py` — `build_project_context()` 灵感阶段增补 `inspiration_brief` 字段

3. `backend/app/agents/agent_graph.py` — `create_agent_graph()` 支持按阶段过滤工具集

4. `backend/app/agents/nodes/outline_generation.py` — `prepare_outline_prompt()` 重构：
   - 优先使用 `state["inspiration_template"]`（即灵感简报）作为prompt主体
   - 从简报或 `collected_info` 提取目标字数 → 计算章节数
   - 移除对 `collected_info` 旧字段名（novelType、targetReader、era等）的依赖
   - 如 `inspiration_template` 为空，回退到从 `collected_info` 构建简易prompt（向后兼容旧项目）

5. `backend/app/api/outline.py` — `confirm_outline()` 移除对 `collected_info.targetWords`/`wordsPerChapter` 的读取，改用 `outline.chapter_count_suggested`

6. `backend/app/api/workflow.py` — `build_initial_state()` 无需改动（已从 `outline.inspiration_template` 列读取）

### 移除

- `backend/app/api/inspiration.py` — `chat` 端点及 `_infer_fields_from_text()`、`_get_missing_fields()` 辅助函数
- `backend/app/agents/prompts.py` — `INSPIRATION_EXTRACTION_PROMPT`、`INSPIRATION_QUESTION_PROMPT`
- `backend/app/agents/constants.py` — `FIELD_INFERENCE_RULES`、`INSPIRATION_REQUIRED_FIELDS`（仅被 inspiration.py 使用，安全移除）

## 数据流

```
1. 用户进入灵感页面 → AI搭档自动加载灵感阶段系统提示
       │
2. 用户跟AI搭档聊天
       │  AI调用 read_inspiration_brief 读取当前简报
       │  AI调用 update_inspiration_brief 写入/更新简报
       │  SSE: agent_text + agent_tool_result
       ▼
3. InspirationPanel 监听 SSE 事件
       │  检测 update_inspiration_brief 调用 → 更新 workbenchStore.inspirationBrief
       ▼
4. InspirationBrief 实时渲染更新后的简报
       │
5. 用户满意 → 点击"确认并生成设定"
       │  触发 workflowApi.runWorkflow()
       ▼
6. build_initial_state 读取 outline.inspiration_template（即简报）
       │  传入 NovelState["inspiration_template"]
       ▼
7. prepare_outline_prompt() 直接使用简报作为prompt主体
       │  附加大纲格式要求，计算章节数
       ▼
8. outline_generation_node 生成大纲
```

## 向后兼容

- 旧项目 `collected_info` 保留不动
- `prepare_outline_prompt()` 中 `inspiration_template` 为空时回退到从 `collected_info` 构建简易prompt
- 新项目统一使用 `inspiration_template` 列存储灵感简报
- 前端从 store 移除 `inspirationFields` 但 migration 不做字段级数据转换

## 验证

1. `docker compose up -d` 启动服务
2. 创建新项目 → 灵感页面：AI搭档在右栏、左侧空白简报
3. 跟AI搭档对话描述创意 → 确认 `update_inspiration_brief` 工具被调用，简报实时更新
4. 手动编辑简报 → 确认可修改
5. 点击确认 → 大纲生成正常
6. 旧项目（已填表单）→ 确认大纲生成仍正常（向后兼容回退路径）
7. `docker exec novelagent-backend-1 pytest -v` → 全部通过
8. `cd frontend && npm run test:run` → 更新后的测试通过