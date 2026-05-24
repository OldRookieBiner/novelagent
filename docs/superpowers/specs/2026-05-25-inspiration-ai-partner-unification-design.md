# 灵感页面重构：AI搭档统一与灵感简报模式

## Context

当前灵感页面存在三套独立系统：固定44字段表单、灵感聊天（`/inspiration/chat`）、AI搭档（ReAct Agent）。三者互不依赖，用户困惑。固定表单字段限制了创作灵活性。需统一为一套以AI搭档为核心的对话驱动灵感收集流程。

## 设计决策

### 核心理念

AI搭档是唯一交互入口。用户跟AI聊天描述创意，AI实时维护一份"灵感简报"——一份连贯的叙事性创意文档。简报既是给人看的创作摘要，也是后续大纲生成的输入。

### 关键决策

| 决策 | 说明 |
|------|------|
| 合并灵感聊天到AI搭档 | 不再有独立的 `/inspiration/chat`，AI搭档统一处理灵感阶段对话 |
| 移除固定表单 | 去掉44字段的 InspirationForm，改为AI动态驱动的灵感简报 |
| 灵感简报替代设定卡 | 左栏展示AI维护的自然语言创意文档，非碎片化卡片 |
| AI搭档固定在右栏 | 与全站布局一致，不移动AI搭档位置 |
| 模型选择在AI搭档标题栏 | 读取已配置模型列表 |
| 无用户可见的"启动门槛" | AI在对话中自然覆盖必要信息 |

### 页面布局

```
┌─────────────────────────────────┬──────────────────┐
│ 📝 创作灵感简报 (AI 自动整理)    │                  │
│                                 │   🤖 AI 搭档     │
│ 故事梗概                         │   [模型选择器]    │
│ 主要人物                         │                  │
│ 核心主题                         │   对话区          │
│ 世界观/氛围                       │                  │
│ 创作参数                         │                  │
│                                 │                  │
│ [✏️ 手动编辑] [确认并生成设定 →]  │   输入框          │
└─────────────────────────────────┴──────────────────┘
```

## 前端变更

### 新增

- `InspirationBrief.tsx` — 灵感简报展示组件。渲染AI维护的Markdown文档，支持手动编辑模式切换

### 修改

- `InspirationPanel.tsx` — 重写为简报 + AI搭档布局。去掉表单逻辑，改为监听AI搭档消息更新简报
- `workbenchStore.ts` — 简化灵感状态：移除 `inspirationFields`/`inspirationFieldStatus`，新增 `inspirationBrief: string` 和 `setInspirationBrief`

### 移除

- `InspirationForm.tsx` — 整个组件
- `InspirationFieldGroup.tsx` — 整个组件
- `InspirationTemplatePreview.tsx` — 整个组件
- `useInspirationForm.ts` — 整个hook
- `frontend/src/lib/inspiration/templates.ts` — `generateInspirationTemplate()`/`parseTemplateToData()`
- `frontend/src/lib/inspiration/utils.ts` — `inferFieldsFromText()`/`saveInspirationDraft()`/`loadInspirationDraft()`/`clearInspirationDraft()`
- `frontend/src/lib/inspiration/types.ts` — `InspirationData` 接口（44字段）
- `frontend/src/lib/inspiration/config.ts` — 选项配置（部分保留供AI系统提示使用）

### 保留

- `frontend/src/lib/inspiration/config.ts` — 选项数据（novelTypes/eras/themes等）作为AI搭档灵感阶段的上下文参考
- `OutlineProgressDialog.tsx` — 确认后进度弹窗逻辑不变

## 后端变更

### 新增

- AI搭档灵感阶段系统提示 — 指导AI搭档在灵感阶段如何引导用户、维护简报、判断信息完整度

### 修改

- `backend/app/api/inspiration.py` — 移除 `/inspiration/chat` 端点，保留 `/inspiration/confirm`（简化）
- `backend/app/agents/agent_graph.py` — AI搭档增加灵感阶段上下文注入
- `backend/app/agents/agent_context.py` — 灵感阶段注入 `inspiration_brief` 字段到上下文
- `backend/app/models/outline.py` — `collected_info` 改为存储 `inspiration_brief` 文本（替代字段散列）
- `backend/app/agents/nodes/outline_generation.py` — `prepare_outline_prompt()` 直接使用 `inspiration_brief` 替代模板拼装

### 移除

- `backend/app/agents/prompts.py` — `INSPIRATION_EXTRACTION_PROMPT` 和 `INSPIRATION_QUESTION_PROMPT`
- `backend/app/agents/constants.py` — `FIELD_INFERENCE_RULES` 和 `INSPIRATION_REQUIRED_FIELDS`

## 数据流

```
1. 用户跟AI搭档聊天
       │
2. AI搭档理解新灵感 → 更新 inspiration_brief
       │  SSE: agent_text + ai_update
       ▼
3. InspirationPanel 监听 SSE 事件
       │  更新 workbenchStore.inspirationBrief
       ▼
4. InspirationBrief 实时渲染更新后的简报
       │
5. 用户满意 → 点击"确认并生成设定"
       │  PUT /api/outline/collected-info (inspiration_brief)
       ▼
6. OutlineProgressDialog → runWorkflow
       │  build_initial_state 读取 inspiration_brief
       ▼
7. outline_generation_node 使用简报作为输入
```

## 验证

1. `docker compose up -d` 启动服务
2. 创建新项目 → 进入灵感页面 → 确认AI搭档在右栏，左侧为空白简报
3. 跟AI搭档对话描述创意 → 确认简报实时更新
4. 手动编辑简报 → 确认可保存
5. 点击确认 → 确认大纲生成流程正常工作
6. 运行现有测试：`docker exec novelagent-backend-1 pytest -v`
7. 运行前端测试：`cd frontend && npm run test:run`
