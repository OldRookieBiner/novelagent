# 章节大纲功能设计

## 问题

`ChapterOutline` 模型已存在，但"章节大纲功能"几乎不存在：

1. **无生成环节** — 没有独立的"生成章节大纲"工具。只在项目初始化时批量生成一次，写作阶段 Agent 不生成也不更新章节大纲
2. **无审查环节** — 前端没有章节大纲面板。`ChapterOutlinePanel` 等组件是死代码，未被任何页面渲染
3. **无参考环节** — Agent 写正文时不读取当前章的 `ChapterOutline`，等于大纲写了白写

导致 LLM 从全书大纲直接跳到写 3000 字正文，缺少"先规划再动笔"的中间步骤，章节内容常出现节奏失控、跨章衔接生硬、情绪一平到底等问题。

## 方案

采用**规划-审查-写作三步流程**，核心三环节 + 新增指导性字段，一步到位。

### 数据模型变更

`chapter_outlines` 表新增 4 列：

| 列名 | 类型 | 说明 |
|------|------|------|
| `opening_state` | Text, nullable | 开场状态——本章起笔时角色/局面的状态，解决跨章衔接 |
| `emotional_arc` | Text, nullable | 情绪弧线——如"压抑→紧张→爆发→余波" |
| `key_scenes` | JSON, nullable | 核心场景列表，如 `[{"seq":1,"desc":"大殿对峙","mood":"紧张"}]` |
| `pacing_note` | Text, nullable | 节奏标注——如"前慢后快，2/3处转折" |

同步更新：
- `ChapterOutline` 模型（`backend/app/models/outline.py`）
- `ChapterOutlineBase` / `ChapterOutlineUpdate` / `ChapterOutlineResponse` schema（`backend/app/schemas/chapter.py`）
- Alembic 迁移：4 个 ALTER TABLE ADD COLUMN，nullable，无数据回填

### Agent 工具变更

**新增 `generate_chapter_outline` 工具**（注册到 STRUCTURE_TOOLS 和 WRITING_TOOLS）

输入：chapter_number, title, scene, characters, plot, conflict, turning_point, hook, transition, ending, target_words, opening_state, emotional_arc, key_scenes, pacing_note

行为：
1. 查找 ChapterOutline（按 project_id + chapter_number）
2. 存在 → 更新所有字段；不存在 → 创建
3. 设 confirmed = False（等待用户审查）
4. 返回完整大纲内容

**修改 `generate_chapter_content` 工具**

写正文前读取当前章的 ChapterOutline：
- 存在且 confirmed → 正常写正文（大纲已通过 agent_context 注入 Agent system prompt，LLM 在调用此工具时已参考大纲）
- 存在但未 confirmed → 返回错误提示"请先确认章节大纲"
- 不存在 → 正常写正文（向后兼容，保留原有自动创建空壳 ChapterOutline 的逻辑）

### Agent 上下文变更

`agent_context.py` 的 writing phase 新增：
- 如果 `current_chapter_number` 有值，读取该章的 `ChapterOutline`，放入 `context["current_chapter_outline"]`
- 包含所有字段（含新增 4 个），token 计入 budget（预估 200-400 tokens）

`HybridContentStrategy` 不需要改——已用 `chapter_outlines` 做远章概要。

### 审核和重写上下文变更

以下位置需要同步包含新增的 4 个字段，确保审核/重写时 LLM 能参考写作指导：

1. `review_chapter.py` — 手动构建的 `chapter_outline_dict` 需要加 4 个新字段
2. `rewrite_chapter.py` — 同上
3. `review_utils.py` 的 `_format_chapter_outline_str` — 输出时包含开场状态、情绪弧线、节奏标注、核心场景
4. `rewrite_utils.py` 的 `_format_chapter_outline_str` — 同上
5. `tools/utils.py` 的 `_build_state_for_review` — `chapter_outlines` 列表中的每项加 4 个新字段

### SSE 事件变更

不新增自定义 SSE 事件。`generate_chapter_outline` 工具的执行结果通过 Agent 已有的 `agent_tool_result` 事件推送（tool_name = "generate_chapter_outline"）。前端通过监听 `onToolResult` 回调中 `tool === "generate_chapter_outline"` 的结果来刷新大纲数据，无需新事件类型。

### 前端变更

**布局方案：大纲在正文上方（可折叠面板）**

1. **`WritingPanel` 正文上方增加可折叠"本章大纲"面板**
   - 展示全部字段，分两个区域：基础规划（8 个原有字段）+ 写作指导（4 个新增字段）
   - 每个字段 inline 可编辑（点击变输入框，失焦保存，调用 `chapterOutlinesApi.update`）
   - 底部两个按钮：确认大纲（调用 `chapterOutlinesApi.confirm`）、重新规划（发送"重新规划第N章大纲"消息到 Agent）
   - 大纲未确认时默认展开 + 虚线边框 + "待确认"标签；确认后可折叠 + 实线边框 + "已确认"标签
   - 大纲不存在时显示空状态提示："尚未规划本章，点击重新规划或通过 Agent 对话生成"

2. **左侧章节列表增加大纲状态标识**
   - ○ 未规划（无 ChapterOutline 记录或 plot 为空）
   - ● 已规划（有记录但 confirmed=false）
   - ● 已确认（confirmed=true）
   - ✓ 已写正文（has_content=true）

3. **写作前置检查**
   - 用户点击"AI 生成"按钮时，前端先检查当前章是否有已确认的大纲
   - 无大纲 → toast 提示"请先规划本章大纲"，同时自动发送"规划第N章"消息到 Agent
   - 有大纲但未确认 → toast 提示"请先确认章节大纲"
   - 已确认 → 正常进入写作流程

4. **删除死代码** — `ChapterOutlinePanel.tsx`、`ChapterOutlineEditor.tsx`、`ChapterOutlineCard.tsx`、`ChapterOutlineFlatList.tsx`、`ChapterOutlineTreeView.tsx`

5. **Agent 结果监听**
   - `agentApi.ts` 的 `onToolResult` 回调中，当 `tool === "generate_chapter_outline"` 时，自动刷新当前章的大纲数据

### 写作流程变更

**规划阶段**：用户说"规划第5章" → Agent 调用 `generate_chapter_outline` → 大纲写入 DB → 通过 `agent_tool_result` SSE 推送结果 → 前端监听到后刷新大纲面板 → 用户审查/编辑/确认

**写作阶段**：用户说"写第5章" → 前端检查大纲已确认 → Agent 调用 `generate_chapter_content`（Agent 的 system prompt 中已包含当前章大纲，LLM 参考大纲调用工具）→ 正文生成

**快捷路径**：用户说"直接写第5章" → 大纲已确认则直接写；未规划则 Agent 先自动生成大纲再写正文（一次对话完成，大纲质量无保障）

## 改动范围汇总

| 文件 | 改动 |
|------|------|
| `backend/app/models/outline.py` | ChapterOutline 加 4 列 |
| `backend/app/schemas/chapter.py` | schema 加 4 字段 |
| `backend/alembic/versions/` | 新增迁移 |
| `backend/app/agents/tools/creation/generate_chapter_outline.py` | 新增工具 |
| `backend/app/agents/tools/creation/__init__.py` | 导出新工具 |
| `backend/app/agents/tools/registry.py` | 注册到 STRUCTURE/WRITING_TOOLS |
| `backend/app/agents/tools/creation/generate_chapter_content.py` | 写正文前检查 confirmed 状态 |
| `backend/app/agents/agent_context.py` | writing phase 加载 current_chapter_outline |
| `backend/app/agents/tools/creation/review_chapter.py` | chapter_outline_dict 加 4 字段 |
| `backend/app/agents/tools/creation/rewrite_chapter.py` | chapter_outline_dict 加 4 字段 |
| `backend/app/agents/review_utils.py` | _format_chapter_outline_str 加新字段 |
| `backend/app/agents/rewrite_utils.py` | _format_chapter_outline_str 加新字段 |
| `backend/app/agents/tools/utils.py` | _build_state_for_review 加新字段 |
| `backend/app/agents/services/outline_service.py` | read/update_chapter_outline 加新字段 |
| `backend/app/api/chapters.py` | update/confirm 端点支持新字段 |
| `frontend/src/components/workbench/creation/WritingPanel.tsx` | 加大纲面板 + 编辑 + 状态标识 + 前置检查 |
| `frontend/src/types/index.ts` | ChapterOutline 类型加 4 字段 |
| 死代码文件 ×5 | 删除 |
