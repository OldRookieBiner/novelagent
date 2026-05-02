# LangGraph 架构统一 — 设计文档

日期：2026-05-02
状态：已确认

---

## 背景

审计发现项目存在两套并行的 AI 生成系统：

1. **LangGraph 路径** (`workflow/run`): 正确使用 StateGraph + astream_events + checkpointer
2. **Legacy 路径** (5 个独立端点): 直接调用 agents/nodes 中的函数，绕过 LangGraph

此外 `workflow/run` 存在 3 个 bug：确认后无法恢复、关系节点提前终止、部分节点非流式输出。

## 目标

1. 5 个 legacy 端点统一通过 LangGraph StateGraph 执行
2. 修复 `workflow/run` 的 3 个 bug
3. **前端零改动**（原地改造，URL 不变，请求/响应格式不变）

## 架构

```
前端 (不变)
  ├─ outlineApi.createStream()      → POST /{id}/outline
  ├─ chapterOutlinesApi.createStream() → POST /{id}/chapter-outlines
  ├─ createSSEStream()              → POST /{id}/chapters/{n}/generate
  ├─ chaptersApi.review()           → POST /{id}/chapters/{n}/review
  └─ workflowApi.runWorkflow()      → POST /{id}/workflow/run

后端 (改造内部实现)
  ├─ POST /{id}/outline              → 创建单节点 graph(outline_generation_node) → astream_events → SSE
  ├─ POST /{id}/chapter-outlines     → 创建单节点 graph(chapter_outlines_node) → astream_events → SSE
  ├─ POST /{id}/chapters/{n}/generate → 创建单节点 graph(generate_chapter_content_node) → astream_events → SSE
  ├─ POST /{id}/chapters/{n}/review  → 创建单节点 graph(review_node) → astream_events → SSE
  └─ POST /{id}/workflow/run         → 保持原有 StateGraph → astream_events → SSE (修复确认恢复)
```

## 详细设计

### 1. 新增 `app/agents/streaming.py` — 公共 SSE 流式工具

提供 `stream_node_events()` 函数，封装对单节点 graph 的 astream_events 调用，处理通用的 on_chain_start / on_chat_model_stream / on_chain_end 事件转换。

签名：
```python
async def stream_node_events(graph, initial_state, config) -> AsyncIterator[str]:
    """通过 LangGraph astream_events 执行单节点并流式输出 SSE 字符串"""
    yield "event: node_start\ndata: ...\n\n"
    async for event in graph.astream_events(initial_state, config, version="v2"):
        # 处理 on_chat_model_stream → yield 文本 chunk
        # 处理 on_chain_end → yield 最终状态
    yield "event: done\ndata: ...\n\n"
```

每个独立端点的 `stream_generator()` 内部调用此函数，再包装自己特有的业务逻辑（如解析大纲结果、保存数据库）。

### 2. 节点改为流式输出

当前 `outline_generation_node` 和 `chapter_outlines_node` 使用 `llm.chat()`（非流式），在 graph 中执行时 `on_chat_model_stream` 事件不会触发，导致前端收不到逐字内容。

**改为 `llm.chat_stream()`**，LangGraph 的 `astream_events` 自动捕获流式内容通过 `on_chat_model_stream` 事件暴露。

`generate_chapter_content_node` 已经使用 `llm.chat_stream()` 并手动 yield——改为直接调用 `llm.chat_stream()`，由框架自动捕获流式事件。

### 3. 修复 `workflow/run` 的 3 个 bug

#### 3a. 确认后恢复

**问题：** `confirm_workflow` 直接操作 checkpoint 数据库记录，从未调用 `graph.astream_events()` 继续执行。

**修复：** `confirm_workflow` 在更新检查点状态后，创建新的 `stream_generator`，以 `None` 作为输入调用 `graph.astream_events(None, config, version="v2")`，LangGraph 从检查点自动恢复并继续执行。

#### 3b. 关系节点提前终止

**问题：** `workflow.py:307-310` 中 `generate_relations_node` 完成后直接 `return`，阻断了到 `chapter_outlines_node` 的边。

**修复：** 删除该处 `return`。

#### 3c. 确保确认后 graph 能继续

`graph.py` 中 `wait_confirm` → `END` 的边在确认后需要通过 `confirm_workflow` → `astream_events(None, config)` 恢复。此时 LangGraph 从检查点读取到 `waiting_for_confirmation: False`，重新评估路由条件，自动走到正确的下一个节点。

### 4. 端点改造详情

#### 4a. `POST /{id}/outline` (api/outline.py)

```
当前: async for chunk in generate_outline_stream(state, llm): ...
改造: 创建单节点 graph(outline_generation_node)
      await stream_node_events(graph, state, config)
      解析最终输出 → 保存数据库 → yield done 事件
```

流式: `llm.chat_stream()` — 由 `on_chat_model_stream` 事件捕获
done 事件: 保持现有格式 `{ outline: {...}, stage: "..." }`

#### 4b. `POST /{id}/chapter-outlines` (api/chapters.py)

当前实现使用 `generate_chapter_outlines_stream()` 异步生成器，逐章 yield `{ type: "progress" }` 事件。
改造方式：由于 `chapter_outlines_node` 需要逐章生成并发送 progress（非 LLM 流式），不适合通过 LangGraph 单节点 + astream_events 处理。

**采用混合方案：** 端点仍调用 `generate_chapter_outlines_stream()` 流式生成器，但生成器内部改为通过 LangGraph 调用 `generate_single_chapter_outline`。即：

```
outer: async for event in generate_chapter_outlines_stream(state, llm):
inner:   使用 LangGraph 单节点调用 llm.chat() 生成单章大纲
         chapter_outline = await graph.ainvoke(single_chapter_state, config)
```

这确保每个 LLM 调用都经过 LangGraph，同时保持逐章 progress 事件的能力。

#### 4c. `POST /{id}/chapters/{n}/generate` (api/chapters.py)

```
当前: async for chunk in generate_chapter_content_stream(state, llm): ...
改造: 创建单节点 graph(generate_chapter_content_node)
      await stream_node_events(graph, state, config)
      保存生成内容 → yield done 事件
```

done 事件: 保持现有格式 `{ chapter: {...} }`

#### 4d. `POST /{id}/chapters/{n}/review` (api/chapters.py)

```
当前: result = await review_chapter_node(state, llm)
改造: 创建单节点 graph(review_node)
      await stream_node_events(graph, state, config)
      返回审核结果
```

这个端点目前是非流式的——改为流式后返回 `application/json` 或保持 SSE 取决于前端期望。当前前端 `chaptersApi.review()` 返回 `ChapterResponse`，应保持 JSON 响应格式，使用 `graph.ainvoke()` 而非 `astream_events()`。

#### 4e. `POST /{id}/characters/generate-relations` (api/characters.py)

同样模式——创建单节点 graph(generate_relations_node)，astream_events → SSE。

### 5. 不改造的范围

- `POST /{id}/workflow/run` 一键工作流端点（只修 bug，不改结构）
- `POST /{id}/workflow/confirm`（修复恢复逻辑）
- 手动 CRUD 端点（章节增删改查、角色增删改查、关系增删改查）
- 前端任何代码

### 6. 风险点

| 风险 | 缓解 |
|------|------|
| 流式节点在 astream_events 中行为与直接调用不同 | 先用现有 `workflow/run` 测试流式节点，确认 `on_chat_model_stream` 事件正常 |
| `chapter_outlines_node` 的 progress 事件如何透传 | 评估 `astream_events` 是否支持节点内部的自定义事件，不行则保持节点内手动 yield + 外部包装 |
| `confirm_workflow` 恢复后状态不一致 | 检查点中保存的 `waiting_for_confirmation` 状态在修改后需确保路由条件正确评估 |

### 7. 实现顺序

1. 新增 `app/agents/streaming.py` 公共工具
2. 改造 `outline_generation_node` → 流式版本，验证 `workflow/run` 正常
3. 改造 `POST /{id}/outline` → 使用 stream_node_events
4. 改造 `chapter_outlines_node` → 流式版本
5. 改造 `POST /{id}/chapter-outlines` → 使用 stream_node_events
6. 改造 `POST /{id}/chapters/{n}/generate` → 使用 stream_node_events
7. 改造 `POST /{id}/chapters/{n}/review` → 使用 graph.ainvoke
8. 改造 `POST /{id}/characters/generate-relations` → 使用 stream_node_events
9. 修复 `workflow/run` bug — 确认恢复 + 关系节点提前终止
10. 测试验证

## 文件变更清单

| 文件 | 变更类型 |
|------|----------|
| `app/agents/streaming.py` | **新增** |
| `app/agents/nodes/outline_generation.py` | 修改 — 节点改为流式 |
| `app/agents/nodes/chapter_generation.py` | 修改 — 节点改为流式 |
| `app/api/outline.py` | 修改 — 使用 LangGraph |
| `app/api/chapters.py` | 修改 — 3 个端点使用 LangGraph |
| `app/api/characters.py` | 修改 — 1 个端点使用 LangGraph |
| `app/api/workflow.py` | 修改 — 修复确认恢复 + 删除提前终止 |
| `frontend/` | **零变更** |