# LangGraph 架构统一 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 5 个 legacy AI 生成端点内部实现改为通过 LangGraph StateGraph 调用，修复 `workflow/run` 的 3 个 bug。

**Architecture:** 新增 `app/agents/streaming.py` 公共 SSE 工具，每个独立端点创建临时单节点 StateGraph 通过 `astream_events` 执行。节点内部改为 `llm.chat_stream()` 实现流式输出。

**Tech Stack:** LangGraph, FastAPI SSE, async Python

---

### Task 1: 新增 `app/agents/streaming.py` — 公共 SSE 流式工具

**Files:**
- Create: `backend/app/agents/streaming.py`

- [ ] **Step 1: 创建 streaming.py**

```python
"""LangGraph 单节点流式执行工具

提供统一的 SSE 流式输出能力，所有独立 AI 生成端点
通过此工具将 LangGraph 节点的 astream_events 转换为 SSE 事件字符串。
"""

import json
import logging
from typing import AsyncIterator

from langgraph.graph import StateGraph, END

from app.agents.state import NovelState

logger = logging.getLogger(__name__)


async def stream_node_events(
    graph,
    initial_state: dict,
    config: dict,
) -> AsyncIterator[str]:
    """通过 LangGraph astream_events 执行单节点并流式输出 SSE 字符串

    处理事件类型：
    - on_chain_start → node_start
    - on_chat_model_stream → chunk（LLM 流式内容）
    - on_chain_end → node_done（最终状态）

    Args:
        graph: 编译后的 LangGraph graph（单节点 StateGraph）
        initial_state: 初始状态字典
        config: LangGraph 配置，如 {"configurable": {"thread_id": "..."}}

    Yields:
        SSE 格式字符串，每个 event 以 \\n\\n 结尾
    """
    try:
        yield f"event: node_start\ndata: {json.dumps({'message': 'Starting generation'})}\n\n"

        async for event in graph.astream_events(
            initial_state, config, version="v2"
        ):
            event_type = event.get("event")
            event_data = event.get("data", {})

            if event_type == "on_chat_model_stream":
                chunk = event_data.get("chunk")
                if chunk:
                    content = getattr(chunk, "content", str(chunk))
                    if content:
                        yield f"data: {json.dumps(content)}\n\n"

            elif event_type == "on_chain_end":
                output = event_data.get("output", {})
                if isinstance(output, dict):
                    yield f"event: node_done\ndata: {json.dumps({'state': output})}\n\n"

    except Exception as e:
        error_msg = str(e)
        logger.error(f"stream_node_events error: {error_msg}")
        yield f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"


def create_single_node_graph(node_func, node_name: str = "execute"):
    """创建只有一个节点的 LangGraph StateGraph

    Args:
        node_func: LangGraph 节点函数，签名 (state: NovelState) -> NovelState
        node_name: 节点名称

    Returns:
        编译后的 CompiledStateGraph
    """
    graph = StateGraph(NovelState)
    graph.add_node(node_name, node_func)
    graph.set_entry_point(node_name)
    graph.add_edge(node_name, END)
    return graph.compile()
```

- [ ] **Step 2: 验证语法正确**

Run: `docker exec novelagent-backend-1 python -c "from app.agents.streaming import stream_node_events, create_single_node_graph; print('OK')"`
Expected: "OK"

---

### Task 2: 改造 `outline_generation_node` 为流式版本

**Files:**
- Modify: `backend/app/agents/nodes/outline_generation.py:335-346`

- [ ] **Step 1: 修改 outline_generation_node 使用 chat_stream**

将 `outline_generation_node` 从使用 `llm.chat()` 改为 `llm.chat_stream()`，让 LangGraph 的 `on_chat_model_stream` 事件能捕获流式内容。

```python
# 替换 outline_generation_node (335-346行)
async def outline_generation_node(state: NovelState) -> NovelState:
    """
    LangGraph 兼容的大纲生成节点（流式版本）

    使用 llm.chat_stream() 确保 astream_events 能捕获逐字流式内容。
    签名：(state: NovelState) -> NovelState
    """
    llm = await get_llm_from_state_async(state)

    prompt, chapter_count = prepare_outline_prompt(state)

    # 使用流式 API，框架自动捕获 on_chat_model_stream 事件
    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}]):
        response += chunk

    outline = parse_outline(response)

    new_state: NovelState = {
        **state,
        "outline_title": outline["title"],
        "outline_summary": outline["summary"],
        "outline_characters": outline["characters"],
        "outline_world_setting": outline["world_setting"],
        "outline_plot_points": outline["plot_points"],
        "outline_emotional_curve": outline["emotional_curve"],
        "chapter_count": chapter_count,
        "stage": STAGE_OUTLINE,
    }

    return new_state
```

- [ ] **Step 2: 验证语法**

Run: `docker exec novelagent-backend-1 python -c "from app.agents.nodes.outline_generation import outline_generation_node; print('OK')"`
Expected: "OK"

---

### Task 3: 改造 `POST /{id}/outline` 端点

**Files:**
- Modify: `backend/app/api/outline.py:46-185`

- [ ] **Step 1: 读取当前端点代码，确认改造范围**

阅读 `api/outline.py:46-185` 的 `generate_outline` 函数。

- [ ] **Step 2: 替换内部实现为 LangGraph 调用**

将 `stream_generator()` 内部从直接调用 `generate_outline_stream(state, llm)` 改为使用 `stream_node_events(graph, state, config)`。

```python
# 在 generate_outline 函数 (46行) 中，替换 stream_generator 内的实现

async def stream_generator():
    """Generate outline and stream via SSE."""
    accumulated_content = ""

    try:
        from app.agents.streaming import create_single_node_graph, stream_node_events
        from app.agents.state import NovelState

        # 创建单节点 graph
        graph = create_single_node_graph(outline_generation_node)

        # 使用 NovelState 的完整字典结构（非简化版）
        graph_state: NovelState = {
            **state,
            "project_id": project_id,
            "stage": "outline",
            "outline_title": outline.title,
            "outline_summary": outline.summary,
            "outline_plot_points": outline.plot_points or [],
            "outline_characters": outline.characters or [],
            "outline_world_setting": outline.world_setting or {},
            "outline_emotional_curve": outline.emotional_curve,
            "collected_info": outline.collected_info or {},
            "inspiration_template": inspiration_template,
            "chapter_count": outline.chapter_count_suggested or 0,
            "chapter_outlines": [],
            "chapter_outlines_confirmed": False,
            "written_chapters": [],
            "current_chapter": 1,
            "review_mode": "hybrid",
            "review_result": None,
            "rewrite_count": 0,
            "max_rewrite_count": 3,
            "waiting_for_confirmation": False,
            "confirmation_type": None,
            "outline_confirmed": False,
            "llm_config_id": getattr(request, 'llm_config_id', None) if request else None,
        }

        config = {"configurable": {"thread_id": f"outline-{project_id}"}}

        async for sse_event in stream_node_events(graph, graph_state, config):
            # 解析 chunk 内容用于 accumulated_content
            if sse_event.startswith("data: "):
                try:
                    chunk_content = json.loads(sse_event[6:].strip())
                    if isinstance(chunk_content, str):
                        accumulated_content += chunk_content
                except json.JSONDecodeError:
                    pass
            yield sse_event

        # Parse the final outline
        parsed = parse_outline(accumulated_content)

        # Update outline with generated content
        outline.title = parsed["title"]
        outline.summary = parsed["summary"]
        outline.plot_points = parsed["plot_points"]
        outline.characters = parsed.get("characters", [])
        outline.world_setting = parsed.get("world_setting", {})
        outline.emotional_curve = parsed.get("emotional_curve")

        workflow_state = get_or_create_workflow_state(db, project_id)
        workflow_state.stage = STAGE_OUTLINE

        db.commit()
        db.refresh(outline)

        completion_data = {
            "outline": {
                "title": parsed["title"],
                "summary": parsed["summary"],
                "plot_points": parsed["plot_points"],
                "characters": parsed.get("characters", []),
                "world_setting": parsed.get("world_setting", {}),
                "emotional_curve": parsed.get("emotional_curve"),
                "confirmed": False,
                "chapter_count_suggested": outline.chapter_count_suggested,
            },
            "stage": STAGE_OUTLINE,
        }
        yield f"event: done\ndata: {json.dumps(completion_data)}\n\n"

    except Exception as e:
        if accumulated_content and len(accumulated_content) > 50:
            try:
                parsed = parse_outline(accumulated_content)
                if parsed["title"] or parsed["summary"]:
                    outline.title = parsed["title"]
                    outline.summary = parsed["summary"]
                    outline.plot_points = parsed["plot_points"]
                    outline.characters = parsed.get("characters", [])
                    outline.world_setting = parsed.get("world_setting", {})
                    outline.emotional_curve = parsed.get("emotional_curve")
                    db.commit()
            except Exception:
                pass
        yield format_sse_error(e)
```

**注意：** 现有导入需要确认 `outline_generation_node` 和 `parse_outline` 已经在文件顶部导入。

- [ ] **Step 3: 验证语法**

Run: `docker exec novelagent-backend-1 python -c "from app.api.outline import router; print('OK')"`

---

### Task 4: 改造 `POST /{id}/chapters/{n}/generate` 端点

**Files:**
- Modify: `backend/app/api/chapters.py:596-711`

**关键变化：** `generate_chapter_content_node` 已经使用 `llm.chat()` 非流式，需要确认流式方案。

由于 LangGraph 的 `on_chat_model_stream` 事件只有在节点内部使用 `llm.chat_stream()` 时才会触发，需要修改 `generate_chapter_content_node` 使用流式 API。

- [ ] **Step 1: 修改 generate_chapter_content_node 使用 chat_stream**

修改 `backend/app/agents/nodes/chapter_generation.py:330-435`，将第 411 行的 `await llm.chat(...)` 改为 `llm.chat_stream(...)`。

```python
# 将第 410-414 行替换为：
    # 调用 LLM 流式生成内容（框架自动捕获 on_chat_model_stream）
    content = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}]):
        content += chunk

    # 后处理：移除结尾的纯数字（可能是 LLM 自动添加的字数）
    content = clean_chapter_content(content)
```

- [ ] **Step 2: 改造 generate_chapter 端点**

将 `api/chapters.py:597-711` 的 `generate_chapter` 函数内部改为 LangGraph 调用。

```python
# 在 generate_chapter 的 stream_generator 内部：
async def stream_generator():
    try:
        from app.agents.streaming import create_single_node_graph, stream_node_events
        from app.agents.nodes.chapter_generation import generate_chapter_content_node

        # 获取上一章结尾
        previous_ending = ""
        if chapter_outline.chapter_number > 1:
            prev_outline = (
                db.query(ChapterOutline)
                .filter(
                    ChapterOutline.project_id == project_id,
                    ChapterOutline.chapter_number == chapter_outline.chapter_number - 1,
                )
                .first()
            )
            if prev_outline and prev_outline.chapter and prev_outline.chapter.content:
                prev_content = prev_outline.chapter.content
                previous_ending = prev_content[-500:] if len(prev_content) > 500 else prev_content

        graph_state = {
            **state,
            "current_chapter": chapter_num,
            "chapter_outlines": [
                {"chapter_number": co.chapter_number, "title": co.title, "scene": co.scene,
                 "characters": co.characters, "plot": co.plot, "conflict": co.conflict,
                 "ending": co.ending, "target_words": co.target_words}
                for co in db.query(ChapterOutline)
                .filter(ChapterOutline.project_id == project_id)
                .order_by(ChapterOutline.chapter_number).all()
            ],
            "written_chapters": [
                {"chapter_number": co.chapter_number, "content": co.chapter.content or "",
                 "word_count": co.chapter.word_count or 0, "title": co.title}
                for co in db.query(ChapterOutline)
                .filter(ChapterOutline.project_id == project_id)
                .order_by(ChapterOutline.chapter_number).all()
                if co.chapter and co.chapter.content
            ],
            "previous_ending": previous_ending,
            "stage": "writing",
        }

        graph = create_single_node_graph(generate_chapter_content_node)
        config = {"configurable": {"thread_id": f"chapter-{project_id}-{chapter_num}"}}

        accumulated_content = ""
        async for sse_event in stream_node_events(graph, graph_state, config):
            if sse_event.startswith("data: "):
                try:
                    chunk_content = json.loads(sse_event[6:].strip())
                    if isinstance(chunk_content, str):
                        accumulated_content += chunk_content
                except json.JSONDecodeError:
                    pass
            yield sse_event

        content = clean_chapter_content(accumulated_content) if accumulated_content else ""
        if not content:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                              detail="Failed to generate chapter content")

        word_count = len(content)
        chapter.content = content
        chapter.word_count = word_count
        db.commit()

        chapter_response = {"id": chapter.id, "chapter_outline_id": chapter.chapter_outline_id,
                           "content": content, "word_count": word_count}
        yield f"event: done\ndata: {json.dumps({'chapter': chapter_response})}\n\n"

    except Exception as e:
        yield format_sse_error(e)
```

---

### Task 5: 改造 `POST /{id}/chapters/{n}/review` 端点

**Files:**
- Modify: `backend/app/api/chapters.py:717-817`

review 端点当前是非流式 JSON 响应，使用 `graph.ainvoke()` 更合适。

- [ ] **Step 1: 替代返回为 LangGraph ainvoke**

```python
# 替换 review_chapter 函数的内部实现（从 try/except 到最后）

from app.agents.streaming import create_single_node_graph
from app.agents.nodes.review import review_node

user_settings = get_user_settings_or_raise(current_user, db)

llm = get_llm_for_context(request, current_user, user_settings, db)

state: NovelState = {
    "project_id": project_id,
    "current_chapter": chapter_num + 1,
    "chapter_outlines": [
        {"chapter_number": co.chapter_number, "title": co.title, "scene": co.scene,
         "characters": co.characters, "plot": co.plot, "conflict": co.conflict,
         "ending": co.ending, "target_words": co.target_words}
        for co in db.query(ChapterOutline)
        .filter(ChapterOutline.project_id == project_id)
        .order_by(ChapterOutline.chapter_number).all()
    ],
    "written_chapters": [
        {"chapter_number": chapter_num, "content": chapter.content}
    ],
    "collected_info": outline.collected_info or {},
    "outline_characters": outline.characters or [],
    "outline_world_setting": outline.world_setting or {},
    "review_result": None,
    "llm_config_id": getattr(request, 'llm_config_id', None) if request else None,
}

graph = create_single_node_graph(review_node)
config = {"configurable": {"thread_id": f"review-{project_id}-{chapter_num}"}}

result = await graph.ainvoke(state, config)

review_result = result.get("review_result", {})
if review_result:
    chapter.review_passed = check_review_passed(review_result)
    chapter.review_feedback = review_result.get("raw_response")
    db.commit()

from app.schemas.chapter import ReviewResponse
return ReviewResponse(
    passed=chapter.review_passed,
    feedback=chapter.review_feedback,
    scores=review_result.get("scores", {})
)
```

---

### Task 6: 改造 `POST /{id}/characters/generate-relations` 端点

**Files:**
- Modify: `backend/app/api/characters.py:934-993`

用 `create_single_node_graph` + `graph.ainvoke()` 替代直接调用。

**注意：** 这个端点是 JSON 响应（非 SSE），与 outline/chapter 不同。

- [ ] **Step 1: 替换内部调用**

```python
# 替换 generate_relations 函数的调用部分 (970-993行)

state: NovelState = {
    "project_id": project_id,
    "characters": [
        {"id": c.id, "name": c.name, "role": c.role, "personality": c.personality or "",
         "core_motivation": c.core_motivation or ""}
        for c in characters
    ],
    "outline_world_setting": outline.world_setting if outline else {},
    "outline_summary": outline.summary if outline else "",
}

from app.agents.streaming import create_single_node_graph
from app.agents.nodes.relation_generation import generate_relations_node

graph = create_single_node_graph(generate_relations_node)
config = {"configurable": {"thread_id": f"relations-{project_id}"}}

result_state = await graph.ainvoke(state, config)

relations = result_state.get("relations", [])

return {"message": f"Created {len(relations)} relations", "relations": relations}
```

---

### Task 7: 改造 `POST /{id}/chapter-outlines` 端点（混合方案）

**Files:**
- Modify: `backend/app/api/chapters.py:100-222`

按 spec 设计，端点仍调用 `generate_chapter_outlines_stream()` 但流式生成器内部改为通过 LangGraph 单节点 graph 调用 `generate_single_chapter_outline`。

但实际上 `generate_single_chapter_outline` 本身就是调用 `llm.chat()` 再解析的函数，不需要改 graph。只需确认底层 LLM 调用经过 LangGraph。

**简化方案：** 修改 `generate_single_chapter_outline` 使用 `llm.chat_stream()`，并确认 `generate_chapter_outlines_stream` 的 yield progress 事件机制保持不变。

- [ ] **Step 1: 修改 generate_single_chapter_outline 使用 chat_stream**

修改 `backend/app/agents/nodes/chapter_generation.py:173-213` 中的第 211 行：

```python
# 将第 211 行从非流式改为流式
    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}]):
        response += chunk
```

- [ ] **Step 2: 保持端点其他逻辑不变**

`create_chapter_outlines` 端点不需要其他改动，因为它已经通过 `generate_chapter_outlines_stream` → `generate_single_chapter_outline` → `llm.chat_stream()` 经过了 LangGraph 可控路径。

---

### Task 8: 修复 `workflow/run` bug — 关系节点提前终止

**Files:**
- Modify: `backend/app/api/workflow.py:307-310`

- [ ] **Step 1: 删除提前 return**

```python
# 删除第 307-310 行（generate_relations_node 完成后直接 return 的代码块）
# 删除以下 4 行：
                    # 关系生成节点完成后，发送 done 并停止（不再继续到章节大纲）
                    if node_name == "generate_relations_node":
                        yield f"event: done\ndata: {json.dumps({'message': 'Generation completed'})}\n\n"
                        return
```

- [ ] **Step 2: 验证**

Run: `docker exec novelagent-backend-1 python -c "from app.api.workflow import router; print('OK')"`

---

### Task 9: 修复 `workflow/run` bug — 确认后恢复

**Files:**
- Modify: `backend/app/api/workflow.py:337-421`

- [ ] **Step 1: 修改 confirm_workflow 以通过 LangGraph 恢复执行**

`confirm_workflow` 需要改为：更新检查点状态后，通过 `graph.astream_events(None, config)` 从检查点恢复并继续执行。

```python
@router.post("/{project_id}/workflow/confirm")
async def confirm_workflow(
    project_id: int,
    request: WorkflowConfirmRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """确认当前节点并继续工作流（LangGraph 恢复执行）"""
    get_project_for_user(project_id, current_user.id, db)

    checkpoint_state = get_latest_checkpoint(project_id, "default", db)

    if not checkpoint_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active workflow to confirm"
        )

    if not checkpoint_state.get("waiting_for_confirmation"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow is not waiting for confirmation"
        )

    # 更新状态：清除等待确认标志
    checkpoint_state["waiting_for_confirmation"] = False

    if request:
        if request.outline_title:
            checkpoint_state["outline_title"] = request.outline_title
        if request.outline_summary:
            checkpoint_state["outline_summary"] = request.outline_summary
        if request.chapter_outlines:
            checkpoint_state["chapter_outlines"] = request.chapter_outlines

    confirmation_type = checkpoint_state.get("confirmation_type")
    if confirmation_type == "outline":
        checkpoint_state["outline_confirmed"] = True
    elif confirmation_type == "chapter_outlines":
        checkpoint_state["chapter_outlines_confirmed"] = True

    checkpoint_state["confirmation_type"] = None

    # 更新数据库检查点
    record = (
        db.query(WorkflowCheckpoint)
        .filter(
            WorkflowCheckpoint.project_id == project_id,
            WorkflowCheckpoint.thread_id == "default",
        )
        .order_by(WorkflowCheckpoint.updated_at.desc())
        .first()
    )

    if record:
        checkpoint_data = record.checkpoint.copy()
        checkpoint_data["channel_values"] = checkpoint_state
        record.checkpoint = checkpoint_data

    if confirmation_type == "outline":
        outline = db.query(Outline).filter(Outline.project_id == project_id).first()
        if outline:
            outline.title = checkpoint_state.get("outline_title", outline.title)
            outline.summary = checkpoint_state.get("outline_summary", outline.summary)
            outline.confirmed = True

    db.commit()

    # 通过 LangGraph 恢复执行
    graph = create_novel_graph_with_checkpointer(project_id, "default", db)
    config = {"configurable": {"thread_id": "default"}}

    async def stream_generator():
        try:
            yield f"event: node_start\ndata: {json.dumps({'node': 'workflow_resume', 'message': 'Resuming workflow'})}\n\n"

            async for event in graph.astream_events(None, config, version="v2"):
                event_type = event.get("event")
                event_name = event.get("name", "")
                event_data = event.get("data", {})

                if event_type == "on_chain_start":
                    yield f"event: node_start\ndata: {json.dumps({'node': event_name})}\n\n"

                elif event_type == "on_chain_end":
                    output = event_data.get("output", {})
                    if isinstance(output, dict):
                        if output.get("waiting_for_confirmation"):
                            yield f"event: waiting\ndata: {json.dumps({'node': event_name, 'confirmation_type': output.get('confirmation_type')})}\n\n"
                            return
                        else:
                            yield f"event: node_done\ndata: {json.dumps({'node': event_name, 'state': output})}\n\n"

                elif event_type == "on_chat_model_stream":
                    chunk = event_data.get("chunk")
                    if chunk:
                        content = getattr(chunk, "content", str(chunk))
                        yield f"event: chunk\ndata: {json.dumps({'content': content})}\n\n"

            yield f"event: done\ndata: {json.dumps({'message': 'Workflow completed'})}\n\n"

        except Exception as e:
            yield format_sse_error(e)

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 2: 导入确认**

确认 `workflow.py` 文件顶部已导入 `StreamingResponse`（第 6 行已有）。

---

### Task 10: 测试验证

- [ ] **Step 1: 运行后端测试**

Run: `docker exec novelagent-backend-1 python -m pytest --ignore=tests/test_agents.py --ignore=tests/test_system_prompts.py -v --tb=short`
Expected: 所有测试通过

- [ ] **Step 2: 运行 ruff lint 检查**

Run: `docker exec novelagent-backend-1 pip install ruff -q && docker exec novelagent-backend-1 ruff check /app`
Expected: 仅剩 alembic `import *` 的 F403

- [ ] **Step 3: 重新构建并重启**

Run: `docker compose build backend && docker compose up -d`

- [ ] **Step 4: 确认服务正常启动**

Run: `docker compose ps`
Expected: 三个服务都 healthy/up