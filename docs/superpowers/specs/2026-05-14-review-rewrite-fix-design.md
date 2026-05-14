# 审核流程三项修复 设计文档

> 修复章节审核流程中的三个问题：显示思考过程、刷新丢失结果、缺少重写功能

## 问题清单

| # | 问题 | 严重度 | 用户影响 |
|---|------|--------|----------|
| 1 | 审核时显示 AI 模型原始输出（JSON 流式文本），用户看到的是未解析的"思考过程" | 中 | 用户体验差，看到一堆 JSON |
| 2 | 刷新/切换标签页/重新打开后审核结果丢失 | 高 | 审核结果白做，无法回溯 |
| 3 | 审核后缺少重写功能，只有"重新审核"按钮 | 高 | 审核发现问题后无法一键修复 |

## 根因分析

### 问题1：显示"思考过程"

**根因**：审核 SSE 端点在流式过程中发送 `chunk` 事件（包含原始 JSON 文本），前端 `AIAssistantPanel` 实时显示 `reviewText`。审核 Prompt 要求 LLM 输出 JSON，LLM 逐字输出 JSON 结构时，用户看到的是未经解析的原始文本流。

审核与章节生成有本质区别：章节生成需要流式预览（有阅读体验价值），审核不需要（结果只有结构化数据）。但后端审核端点沿用了章节生成的 chunk 流式模式，将中间过程（原始 LLM 输出）暴露给了前端。

**涉及代码**：
- `backend/app/api/chapters.py:837-839` — 审核端点发送含 content 的 chunk 事件
- `frontend/src/components/workbench/creation/AIAssistantPanel.tsx:59-68` — 前端接收 chunk 并累积显示

### 问题2：刷新后结果丢失

**根因**：后端已正确保存审核结果到 `chapters` 表（`review_result` JSON、`review_passed` Boolean、`review_feedback` Text），GET 端点也返回这些字段。但前端存在两层断裂：

1. **类型层**：`Chapter` TypeScript 类型缺少 `review_result` 和 `rewrite_count` 字段，前端无法感知这些数据
2. **组件层**：`AIAssistantPanel` 的 `reviewResult` 是组件内部 `useState`，不与 DB 数据关联。`WritingPanel` 已从 API 获取 `chapterContent`（含 `review_result`），但没有将审核数据传递给 `AIAssistantPanel`

**涉及代码**：
- `backend/app/schemas/chapter.py:44-58` — `ChapterResponse` 已包含 `review_result`、`rewrite_count`
- `backend/app/api/chapters.py:444-455` — GET 端点已返回完整数据
- `frontend/src/types/index.ts:187-196` — `Chapter` 类型缺少 `review_result`、`rewrite_count`
- `frontend/src/components/workbench/creation/WritingPanel.tsx:618-628` — 传递给 `AIAssistantPanel` 的 props 没有 `reviewResult`

### 问题3：缺少重写功能

**根因**：后端 `rewrite_node` 已在 LangGraph 图中定义（`graph.py:162`），且 `_build_rewrite_messages()` 和 `rewrite_chapter_node()` 已完整实现。但：
1. 无单节点 SSE 端点暴露重写功能（LangGraph 图中的 rewrite 是自动循环，不支持用户手动触发）
2. 前端无重写按钮和交互流程

**涉及代码**：
- `backend/app/agents/nodes/rewrite.py:23-103` — `_build_rewrite_messages` + `rewrite_chapter_node` 已实现
- `backend/app/agents/graph.py:162` — `rewrite_node` 已在 LangGraph 图中注册
- `backend/app/api/chapters.py` — 缺少 `/chapters/{chapter_num}/rewrite` SSE 端点
- `frontend/src/components/workbench/creation/AIAssistantPanel.tsx:206-214` — 只有"重新审核"按钮

## 修复方案

### 方案1：后端审核端点不发送 chunk content，前端只展示结构化结果

**问题**：当前方案只在前端"隐藏" chunk 内容，后端仍然发送原始 JSON 文本。这是补丁，不是根源修复。如果有其他客户端接入，同样会显示原始文本。且审核 chunk 对前端无价值——审核结果只有结构化数据有意义。

**根源修复**：

**后端改动**：审核端点在流式过程中不发送 `chunk` 事件（含 content），改为发送 SSE 注释行（`: heartbeat\n\n`）保持连接活跃。只在 `done` 事件中发送结构化审核结果。

```python
# 修改前（chapters.py:837-839）
async for chunk in llm.chat_stream(messages):
    response += chunk
    yield f"event: chunk\ndata: {json.dumps({'content': chunk})}\n\n"

# 修改后
async for chunk in llm.chat_stream(messages):
    response += chunk
    # SSE 注释行保持连接活跃，不发送内容给前端
    yield ": heartbeat\n\n"
```

**前端改动**：
- `AIAssistantPanel` 删除 `reviewText` 状态和流式预览 UI
- 审核进行中只显示加载动画
- 审核完成后从 `done` 事件展示结构化结果

**为什么用 SSE 注释行而非空 chunk**：SSE 注释行（以 `:` 开头）会被标准 SSE 客户端自动忽略，不会触发 `onmessage` 事件。既保持连接活跃，又不向业务层传递无意义数据。

### 方案2：从 DB 恢复审核结果

**前端改动**：

1. **类型补充**：`Chapter` TypeScript 类型添加 `review_result` 和 `rewrite_count` 字段（对齐后端 `ChapterResponse` schema）

2. **数据传递**：`WritingPanel` 加载章节后，将 `chapterContent.review_result` 转换为 `ReviewResponse` 传给 `AIAssistantPanel`

3. **组件重置**：`WritingPanel` 给 `AIAssistantPanel` 添加 `key={selectedChapter?.chapter_number}`，章节切换时强制重新挂载，确保 `reviewResult` 从 `initialReviewResult` prop 正确初始化

4. **审核完成回调**：`onReviewComplete` 回调需更新 `WritingPanel` 的 `chapterContent`（设置 `review_passed`、`review_result`），保持 DB 数据与组件状态一致

**数据转换逻辑**（`review_result` JSON → `ReviewResponse`）：
```typescript
function mapReviewResult(result: Chapter['review_result']): ReviewResponse | null {
  if (!result) return null
  return {
    passed: result.passed,
    feedback: result.suggestions || '',
    issues: result.issues || [],
    scores: result.scores || {},
  }
}
```

### 方案3：新增重写 SSE 端点 + 前端重写按钮

**后端**：在 `chapters.py` 新增 `POST /{project_id}/chapters/{chapter_num}/rewrite` SSE 端点

端点设计遵循项目已有的单节点 SSE 模式（与 review、generate 端点一致）：

```
构建 initial_state（build_initial_state + DB 预加载角色/关系）
  → get_llm_from_state_async 获取 LLM（与 LangGraph 节点相同机制）
  → _build_rewrite_messages 构建消息（与 LangGraph rewrite_node 共享逻辑）
  → llm.chat_stream 流式生成，发送 chunk 事件
  → 原子性更新 DB：content、word_count、rewrite_count += 1
  → 清除审核状态：review_passed = False、review_result = None、review_feedback = None
  → 发送 done 事件
```

**前置校验**：
- 章节大纲存在且已确认
- 章节内容存在（有内容才能重写）
- 审核结果存在（重写需要审核建议作为输入；若无审核结果则返回 400，提示先审核）

**RewriteRequest Schema**：
```python
class RewriteRequest(BaseModel):
    llm_config_id: Optional[int] = None
```

**LLM 配置获取**：与审核/生成端点一致，通过 `build_initial_state` 从 `workflow_states` 表读取持久化的 `llm_config_id`

**written_chapters 上下文**：重写需要前文上下文。设置 `initial_state["written_chapters"]`，与审核端点逻辑一致

**done 事件格式**（与 generate 端点对齐）：
```python
{
    "chapter": {
        "id": chapter.id,
        "chapter_outline_id": chapter.chapter_outline_id,
        "content": rewritten_content,
        "word_count": word_count,
    }
}
```

**前端**：
1. `AIAssistantPanel` 添加"重写"按钮（与"重新审核"并列）
2. 点击重写后：
   - 调用 rewrite SSE 端点
   - 通过 `onRewriteChunk` 回调将重写内容实时写入 `WritingPanel` 的编辑器
   - 重写完成后通过 `onRewriteDone` 回调更新 `WritingPanel` 的 `chapterContent`（设置 `rewrite_count`、清除审核状态）
   - `AIAssistantPanel` 清除 `reviewResult`
3. 按钮可见性：只要章节有内容就显示"重写"按钮。审核未通过时按钮更突出（主色调），审核通过时为 outline 样式

## 交互流程

### 审核流程（修复后）

```
用户点击"开始审核"
  → 显示"审核中..."加载动画（后端静默调用 LLM，SSE 注释行保持连接）
  → 审核完成，后端返回 done 事件（结构化审核结果）
  → 前端展示：通过/未通过、评分详情、问题列表、修改建议
  → 刷新/切换标签页后仍可看到审核结果（从 DB 恢复）
```

### 重写流程（新增）

```
审核完成（通过或未通过均可重写）
  → 显示"重写"按钮 + "重新审核"按钮
  → 用户点击"重写"
  → 编辑器进入流式模式，AI 根据审核建议重写内容
  → 重写完成，编辑器显示新内容
  → 清除旧审核结果（重写后需重新审核验证）
  → 用户可再次点击"开始审核"验证重写效果
```

### 按钮逻辑

| 状态 | "开始审核"按钮 | "重新审核"按钮 | "重写"按钮 |
|------|--------------|--------------|-----------|
| 未审核 | 显示 | 隐藏 | 隐藏 |
| 审核中 | 隐藏 | 隐藏 | 隐藏 |
| 审核通过 | 隐藏 | 显示（outline） | 显示（outline） |
| 审核未通过 | 隐藏 | 显示（outline） | 显示（主色调） |
| 重写中 | 隐藏 | 隐藏 | 隐藏 |

## 数据模型变更

### 无需新增数据库迁移

现有 `chapters` 表已包含所有必需字段：
- `review_result` (JSON) — 审核结果
- `review_passed` (Boolean) — 审核是否通过
- `review_feedback` (Text) — 审核原始反馈
- `rewrite_count` (Integer) — 重写次数

### 后端 Schema 变更

**1. `ReviewResponse` 添加 `scores` 字段**（对齐前端类型和 done 事件实际发送的数据）：

```python
# 修改前
class ReviewResponse(BaseModel):
    passed: bool
    feedback: str
    issues: list[str] = []

# 修改后
class ReviewResponse(BaseModel):
    passed: bool
    feedback: str
    issues: list[dict] = []  # 修正：实际是 ReviewIssue 对象列表
    scores: dict = {}         # 新增：评分详情
```

**2. 新增 `RewriteRequest`**：

```python
class RewriteRequest(BaseModel):
    llm_config_id: Optional[int] = None
```

### 前端类型变更

```typescript
// frontend/src/types/index.ts — Chapter 接口补充
export interface Chapter {
  id: number;
  chapter_outline_id: number;
  content?: string;
  word_count: number;
  review_passed: boolean;
  review_feedback?: string;
  review_result?: {         // 新增
    passed: boolean;
    scores: Record<string, number>;
    issues: ReviewIssue[];
    suggestions: string;
    raw_response?: string;
  } | null;
  rewrite_count: number;    // 新增
  created_at: string;
  updated_at: string;
}
```

## 关键文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `backend/app/api/chapters.py` | 修改 | 审核端点：chunk 改为 SSE 注释行；新增 rewrite SSE 端点 |
| `backend/app/schemas/chapter.py` | 修改 | ReviewResponse 添加 scores、修正 issues 类型；新增 RewriteRequest |
| `frontend/src/types/index.ts` | 修改 | Chapter 类型添加 review_result、rewrite_count |
| `frontend/src/components/workbench/creation/AIAssistantPanel.tsx` | 重构 | 删除流式预览；添加 initialReviewResult prop；添加重写按钮和逻辑 |
| `frontend/src/components/workbench/creation/WritingPanel.tsx` | 修改 | 传递 reviewResult 给 AIAssistantPanel；添加 key prop；添加重写回调 |

## 约束与边界

- **遵循项目已有的单节点 SSE 端点模式**：rewrite 端点复用 LangGraph 节点的核心逻辑（`_build_rewrite_messages`、`get_llm_from_state_async`、`build_initial_state`），与现有 review、generate 端点保持架构一致。这是项目已确立的"单节点 SSE 端点"模式，不是绕过 LangGraph
- **遵循 SSE 端点 DB Session 独立性**：rewrite 端点使用 `SessionLocal()` 创建独立 Session
- **遵循 LLM 配置从 workflow_states 读取**：rewrite 端点从 DB 获取 llm_config_id
- **重写后需重新审核**：重写完成后清除 `review_passed`、`review_result`、`review_feedback`，用户需再次审核
- **审核通过时也可重写**：只要章节有内容就显示重写按钮，审核未通过时更突出
- **审核必须有结果才能重写**：无审核结果时重写端点返回 400，因为重写需要审核建议作为输入
