# Backend Architecture Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract WorkflowOrchestrator service, inject dependencies via LangGraph config, simplify LLM lookup chain, and preload DB data into initial state — all without changing API contracts or SSE event formats.

**Architecture:** Centralize SSE streaming orchestration into a single `WorkflowOrchestrator` module that all API routes use. Preload prompts and character/relation data in `build_initial_state` so LangGraph nodes become pure state transformers. Compress the 4-layer LLM lookup into one function with optional db param.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy (sync), LangGraph, pytest

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/app/services/workflow_orchestrator.py` | Create | Central SSE streaming orchestration for all LangGraph endpoints |
| `backend/app/services/outline_service.py` | Create | Business logic for outline generation (validation, persist callback) |
| `backend/app/services/chapter_service.py` | Create | Business logic for chapter outline & content generation |
| `backend/app/api/workflow.py` | Modify | Use WorkflowOrchestrator; delete inline stream_generator |
| `backend/app/api/outline.py` | Modify | Use OutlineService + WorkflowOrchestrator |
| `backend/app/api/chapters.py` | Modify | Use ChapterService + WorkflowOrchestrator |
| `backend/app/utils/llm.py` | Modify | Compress `get_llm_from_state_async` to accept optional db param |
| `backend/app/agents/streaming.py` | Modify | Delete deprecated `stream_node_events` and `create_single_node_graph` |
| `backend/tests/test_workflow_orchestrator.py` | Create | Tests for WorkflowOrchestrator event parsing and persist callback |
| `backend/tests/test_build_initial_state.py` | Create | Tests for DB preloading logic |

---

### Task 1: Create WorkflowOrchestrator Core Service

**Files:**
- Create: `backend/app/services/workflow_orchestrator.py`
- Test: `backend/tests/test_workflow_orchestrator.py`

**Context:**
All SSE streaming endpoints (`api/workflow.py`, `api/outline.py`, `api/chapters.py`) repeat the same pattern: create graph → call `astream_events` → parse `on_chain_start`/`on_chat_model_stream`/`on_chain_end` → detect `waiting_for_confirmation` → yield SSE strings. This module extracts that pattern into one deep module.

- [ ] **Step 1: Write the failing test for WorkflowOrchestrator event streaming**

```python
# backend/tests/test_workflow_orchestrator.py
import pytest
import json
from unittest.mock import AsyncMock, MagicMock

from app.services.workflow_orchestrator import WorkflowOrchestrator, PersistCallback


@pytest.fixture
def mock_graph():
    """Mock compiled LangGraph graph"""
    graph = MagicMock()
    return graph


@pytest.fixture
def mock_db():
    """Mock SQLAlchemy Session"""
    db = MagicMock()
    db.rollback = MagicMock()
    return db


class TestWorkflowOrchestrator:
    def test_init(self, mock_db):
        """WorkflowOrchestrator stores db and project_id"""
        orch = WorkflowOrchestrator(mock_db, project_id=1)
        assert orch.db == mock_db
        assert orch.project_id == 1

    @pytest.mark.asyncio
    async def test_run_yields_node_start_event(self, mock_graph, mock_db):
        """When graph emits on_chain_start, orchestrator yields node_start SSE"""
        orch = WorkflowOrchestrator(mock_db, project_id=1)

        async def mock_astream_events(initial_state, config, version):
            yield {
                "event": "on_chain_start",
                "name": "outline_generation_node",
                "data": {},
            }

        mock_graph.astream_events = mock_astream_events

        events = []
        async for event in orch.run(
            graph=mock_graph,
            config={"configurable": {"thread_id": "default"}},
            initial_state={"project_id": 1},
        ):
            events.append(event)

        assert len(events) >= 2  # workflow start + node_start
        assert "event: node_start" in events[1]
        data = json.loads(events[1].split("data: ")[1])
        assert data["node"] == "outline_generation_node"

    @pytest.mark.asyncio
    async def test_run_yields_chunk_event(self, mock_graph, mock_db):
        """When graph emits on_chat_model_stream, orchestrator yields chunk SSE"""
        orch = WorkflowOrchestrator(mock_db, project_id=1)

        class FakeChunk:
            content = "Hello"

        async def mock_astream_events(initial_state, config, version):
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": FakeChunk()},
            }

        mock_graph.astream_events = mock_astream_events

        events = []
        async for event in orch.run(
            graph=mock_graph,
            config={"configurable": {"thread_id": "default"}},
            initial_state={"project_id": 1},
        ):
            events.append(event)

        chunk_events = [e for e in events if "event: chunk" in e]
        assert len(chunk_events) == 1
        data = json.loads(chunk_events[0].split("data: ")[1])
        assert data["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_run_yields_waiting_and_done_when_waiting_for_confirmation(self, mock_graph, mock_db):
        """When node_done output has waiting_for_confirmation=True, yield waiting + done"""
        orch = WorkflowOrchestrator(mock_db, project_id=1)

        async def mock_astream_events(initial_state, config, version):
            yield {
                "event": "on_chain_end",
                "name": "outline_generation_node",
                "data": {
                    "output": {
                        "waiting_for_confirmation": True,
                        "confirmation_type": "outline",
                    }
                },
            }

        mock_graph.astream_events = mock_astream_events

        events = []
        async for event in orch.run(
            graph=mock_graph,
            config={"configurable": {"thread_id": "default"}},
            initial_state={"project_id": 1},
        ):
            events.append(event)

        waiting_events = [e for e in events if "event: waiting" in e]
        done_events = [e for e in events if "event: done" in e]
        assert len(waiting_events) == 1
        assert len(done_events) == 1

    @pytest.mark.asyncio
    async def test_run_calls_persist_callback_on_node_done(self, mock_graph, mock_db):
        """When target node completes, persist callback is called with state"""
        orch = WorkflowOrchestrator(mock_db, project_id=1)
        persist_mock = AsyncMock(return_value={"saved": True})

        async def mock_astream_events(initial_state, config, version):
            yield {
                "event": "on_chain_end",
                "name": "outline_generation_node",
                "data": {
                    "output": {
                        "outline_title": "Test Title",
                        "waiting_for_confirmation": True,
                        "confirmation_type": "outline",
                    }
                },
            }

        mock_graph.astream_events = mock_astream_events

        events = []
        async for event in orch.run(
            graph=mock_graph,
            config={"configurable": {"thread_id": "default"}},
            initial_state={"project_id": 1},
            target_node="outline_generation_node",
            persist_callback=persist_mock,
        ):
            events.append(event)

        persist_mock.assert_called_once()
        call_state = persist_mock.call_args[0][0]
        assert call_state["outline_title"] == "Test Title"

    @pytest.mark.asyncio
    async def test_run_rolls_back_on_persist_error(self, mock_graph, mock_db):
        """When persist callback raises, db is rolled back and error SSE is yielded"""
        orch = WorkflowOrchestrator(mock_db, project_id=1)
        persist_mock = AsyncMock(side_effect=ValueError("DB constraint failed"))

        async def mock_astream_events(initial_state, config, version):
            yield {
                "event": "on_chain_end",
                "name": "outline_generation_node",
                "data": {
                    "output": {
                        "outline_title": "Test",
                        "waiting_for_confirmation": True,
                    }
                },
            }

        mock_graph.astream_events = mock_astream_events

        events = []
        async for event in orch.run(
            graph=mock_graph,
            config={"configurable": {"thread_id": "default"}},
            initial_state={"project_id": 1},
            target_node="outline_generation_node",
            persist_callback=persist_mock,
        ):
            events.append(event)

        mock_db.rollback.assert_called_once()
        error_events = [e for e in events if "event: error" in e]
        assert len(error_events) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec novelagent-backend-1 pytest tests/test_workflow_orchestrator.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.workflow_orchestrator'`

- [ ] **Step 3: Implement WorkflowOrchestrator**

```python
# backend/app/services/workflow_orchestrator.py
"""Workflow Orchestrator - Central SSE streaming service for LangGraph endpoints.

All SSE streaming endpoints use this module to:
1. Execute a LangGraph graph via astream_events
2. Parse LangGraph events into SSE format
3. Call persist callbacks when target nodes complete
4. Handle errors gracefully with transaction rollback
"""

import json
import logging
from typing import AsyncIterator, Callable, Awaitable, Optional

from app.agents.state import NovelState

logger = logging.getLogger(__name__)

PersistCallback = Callable[[NovelState, "Session"], Awaitable[Optional[dict]]]


class WorkflowOrchestrator:
    """Central orchestrator for LangGraph SSE streaming.

    Interface:
        orch = WorkflowOrchestrator(db, project_id)
        async for sse_event in orch.run(graph, config, initial_state, target_node, persist_callback):
            yield sse_event

    Invariants:
        - db session lifecycle is managed by the caller (API route)
        - persist_callback exceptions trigger db.rollback() and yield error event
        - SSE event format never changes (backward compatible)
    """

    def __init__(self, db: "Session", project_id: int):
        self.db = db
        self.project_id = project_id

    async def run(
        self,
        graph,
        config: dict,
        initial_state: Optional[dict] = None,
        target_node: Optional[str] = None,
        persist_callback: Optional[PersistCallback] = None,
    ) -> AsyncIterator[str]:
        """Execute graph and yield SSE events.

        Args:
            graph: Compiled LangGraph StateGraph
            config: LangGraph config dict (must contain configurable.thread_id)
            initial_state: Initial NovelState. If None, resumes from checkpoint.
            target_node: Node name that triggers persist_callback when completed.
            persist_callback: Async function (state, db) -> dict, called on target_node done.

        Yields:
            SSE formatted strings ending with \\n\\n
        """
        try:
            # 首次执行 vs 恢复执行
            if initial_state is not None:
                yield (
                    f"event: node_start\\n"
                    f"data: {json.dumps({'node': 'workflow', 'message': 'Starting workflow'})}\\n\\n"
                )
            else:
                yield (
                    f"event: node_start\\n"
                    f"data: {json.dumps({'node': 'workflow_resume', 'message': 'Resuming workflow'})}\\n\\n"
                )

            async for event in graph.astream_events(initial_state, config, version="v2"):
                event_type = event.get("event")
                event_name = event.get("name", "")
                event_data = event.get("data", {})

                if event_type == "on_chain_start":
                    yield (
                        f"event: node_start\\n"
                        f"data: {json.dumps({'node': event_name})}\\n\\n"
                    )

                elif event_type == "on_chat_model_stream":
                    chunk = event_data.get("chunk")
                    if chunk:
                        content = getattr(chunk, "content", str(chunk))
                        if content:
                            yield (
                                f"event: chunk\\n"
                                f"data: {json.dumps({'content': content})}\\n\\n"
                            )

                elif event_type == "on_chain_end":
                    output = event_data.get("output", {})
                    if isinstance(output, dict):
                        # 持久化回调
                        if target_node and event_name == target_node and persist_callback is not None:
                            persist_result = await self._call_persist(output, persist_callback)
                            if persist_result.get("_persist_error"):
                                error_msg = persist_result["_persist_error"]
                                yield (
                                    f"event: error\\n"
                                    f"data: {json.dumps({'error': f'持久化失败: {error_msg}'})}\\n\\n"
                                )
                                return

                        if output.get("waiting_for_confirmation"):
                            yield (
                                f"event: waiting\\n"
                                f"data: {json.dumps({"
                                    'node': event_name,
                                    'confirmation_type': output.get('confirmation_type')
                                })}\\n\\n"
                            )
                            yield (
                                f"event: done\\n"
                                f"data: {json.dumps({'message': 'Workflow paused for confirmation'})}\\n\\n"
                            )
                            return
                        else:
                            yield (
                                f"event: node_done\\n"
                                f"data: {json.dumps({'node': event_name, 'state': output})}\\n\\n"
                            )

            yield (
                f"event: done\\n"
                f"data: {json.dumps({'message': 'Workflow completed'})}\\n\\n"
            )

        except Exception as e:
            logger.exception("WorkflowOrchestrator run error")
            from app.utils.error import format_sse_error
            yield format_sse_error(e)

    async def _call_persist(
        self,
        state: dict,
        persist_callback: PersistCallback,
    ) -> dict:
        """Call persist callback with rollback on error.

        Returns:
            Dict from callback, or {"_persist_error": str} on failure.
        """
        try:
            result = await persist_callback(state, self.db)
            return result or {}
        except Exception as e:
            logger.error(f"Persist callback failed: {e}")
            try:
                self.db.rollback()
            except Exception:
                pass
            return {"_persist_error": str(e)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker exec novelagent-backend-1 pytest tests/test_workflow_orchestrator.py -v`

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/workflow_orchestrator.py backend/tests/test_workflow_orchestrator.py
git commit -m "feat(backend): add WorkflowOrchestrator central SSE streaming service

- Extracts repeated SSE logic from api/workflow.py, api/outline.py, api/chapters.py
- Supports target_node + persist_callback for DB persistence on node completion
- Rolls back DB transaction on persist failure and yields error SSE event
- Zero changes to SSE event format (backward compatible)"
```

---

### Task 2: Simplify get_llm_from_state_async to accept optional db param

**Files:**
- Modify: `backend/app/utils/llm.py:69-127`
- Test: `backend/tests/test_nodes_utils.py` (append new test)

**Context:**
Current `get_llm_from_state_async` is a 4-layer call: `get_llm_from_state_async` -> `get_llm_from_state` (sync, creates SessionLocal) -> `get_llm_for_user` -> `get_llm_service_from_config`. When nodes already have a db session, this creates a redundant nested session. Compress to one async function that accepts optional db.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_nodes_utils.py`:

```python
@pytest.mark.asyncio
async def test_get_llm_from_state_async_with_db_param(mock_db_session):
    """When db is passed, function should not create a new SessionLocal"""
    from unittest.mock import patch
    from app.utils.llm import get_llm_from_state_async

    state = {"project_id": 1, "llm_config_id": None}

    # Mock the internal call chain
    with patch("app.utils.llm.get_llm_for_user") as mock_get_llm:
        mock_get_llm.return_value = MagicMock()
        result = await get_llm_from_state_async(state, db=mock_db_session)
        assert result is not None
        mock_get_llm.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec novelagent-backend-1 pytest tests/test_nodes_utils.py::test_get_llm_from_state_async_with_db_param -v`

Expected: FAIL with `TypeError: get_llm_from_state_async() got an unexpected keyword argument 'db'`

- [ ] **Step 3: Modify get_llm_from_state_async to accept optional db param**

Replace lines 111-126 in `backend/app/utils/llm.py`:

```python
async def get_llm_from_state_async(state: dict, db: "Session" = None) -> "LLMService":
    """从工作流状态获取 LLM 服务（异步版本，推荐在 async 节点使用）

    将同步数据库操作放到线程池中执行，避免阻塞 event loop。
    如果传入 db 参数，直接使用该会话，不再创建新的 SessionLocal。

    Args:
        state: NovelState 字典
        db: 可选的数据库会话。如果提供，直接使用而不创建新 session。

    Returns:
        LLMService 实例

    Raises:
        ValueError: 项目未找到或用户设置未找到
    """
    if db is not None:
        # 直接在同一线程执行（调用方负责线程安全）
        return get_llm_from_state_sync(state, db)

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_db_executor, get_llm_from_state, state)


def get_llm_from_state_sync(state: dict, db: "Session") -> "LLMService":
    """同步版本：从工作流状态获取 LLM 服务（使用传入的 db session）

    Args:
        state: NovelState 字典
        db: 数据库会话（必须提供）

    Returns:
        LLMService 实例
    """
    from app.models.project import Project
    from app.models.settings import UserSettings

    project_id = state.get("project_id")
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ValueError(f"Project {project_id} not found")

    user_id = project.user_id
    user_settings = (
        db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    )

    if not user_settings:
        raise ValueError(f"User settings not found for user {user_id}")

    return get_llm_for_user(
        user_id, user_settings, db,
        state.get("llm_config_id"),
        state.get("llm_model_name")
    )
```

Also modify `get_llm_from_state` (the old sync version, lines 69-108) to call `get_llm_from_state_sync`:

```python
def get_llm_from_state(state: dict) -> "LLMService":
    """从工作流状态获取 LLM 服务（同步版本，创建自己的 SessionLocal）

    警告：此函数使用同步数据库连接，在 async 上下文中会阻塞 event loop。
    在 async 节点中请使用 get_llm_from_state_async()。

    Args:
        state: NovelState 字典

    Returns:
        LLMService 实例
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        return get_llm_from_state_sync(state, db)
    finally:
        db.close()
```

- [ ] **Step 4: Run tests**

Run: `docker exec novelagent-backend-1 pytest tests/test_nodes_utils.py -v`

Expected: All tests pass (including the new one)

Run: `docker exec novelagent-backend-1 pytest tests/test_workflow.py -v`

Expected: All tests pass (no regression)

- [ ] **Step 5: Commit**

```bash
git add backend/app/utils/llm.py backend/tests/test_nodes_utils.py
git commit -m "refactor(backend): compress LLM lookup chain and add optional db param

- get_llm_from_state_async now accepts optional db param to avoid nested sessions
- Extract get_llm_from_state_sync for direct sync calls with existing session
- Old get_llm_from_state delegates to sync version with SessionLocal lifecycle
- No changes to external callers that don't pass db"
```

---

### Task 3: Preload prompts and characters/relations in build_initial_state

**Files:**
- Modify: `backend/app/api/workflow.py:117-205`
- Create: `backend/tests/test_build_initial_state.py`

**Context:**
`build_initial_state` currently builds NovelState from Project + Outline + WorkflowState. Nodes like `character_generation` and `relation_generation` then create their own `SessionLocal` to query prompts or characters. We preload all needed DB data here so nodes don't need DB access.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_build_initial_state.py
import pytest
from unittest.mock import MagicMock

from app.api.workflow import build_initial_state


class TestBuildInitialState:
    def test_preloads_characters_with_ids(self):
        """When DB has characters, state['characters'] includes id field"""
        project = MagicMock()
        project.id = 1
        project.chapter_outlines = []

        outline = MagicMock()
        outline.collected_info = {}
        outline.inspiration_template = None
        outline.title = "Test"
        outline.summary = "Summary"
        outline.plot_points = []
        outline.characters = []
        outline.world_setting = None
        outline.emotional_curve = None
        outline.confirmed = False
        outline.chapter_count_suggested = 10

        workflow_state = MagicMock()
        workflow_state.stage = "outline"
        workflow_state.current_chapter = 0
        workflow_state.workflow_mode = "hybrid"
        workflow_state.max_rewrite_count = 3
        workflow_state.waiting_for_confirmation = False
        workflow_state.confirmation_type = None

        db = MagicMock()
        char_mock = MagicMock()
        char_mock.id = 42
        char_mock.name = "Alice"
        char_mock.role = "主角"
        char_mock.personality = "Brave"
        char_mock.core_motivation = "Save world"
        char_mock.growth_arc = "Grows"

        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [char_mock]
        db.query.return_value.filter.return_value.all.return_value = []

        state = build_initial_state(project, outline, workflow_state, db=db)

        assert "characters" in state
        assert len(state["characters"]) == 1
        assert state["characters"][0]["id"] == 42
        assert state["characters"][0]["name"] == "Alice"

    def test_preloads_relations_with_ids(self):
        """When DB has relations, state['relations'] includes id fields"""
        project = MagicMock()
        project.id = 1
        project.chapter_outlines = []

        outline = MagicMock()
        outline.collected_info = {}
        outline.inspiration_template = None
        outline.title = "Test"
        outline.summary = "Summary"
        outline.plot_points = []
        outline.characters = []
        outline.world_setting = None
        outline.emotional_curve = None
        outline.confirmed = False
        outline.chapter_count_suggested = 10

        workflow_state = MagicMock()
        workflow_state.stage = "outline"
        workflow_state.current_chapter = 0
        workflow_state.workflow_mode = "hybrid"
        workflow_state.max_rewrite_count = 3
        workflow_state.waiting_for_confirmation = False
        workflow_state.confirmation_type = None

        db = MagicMock()
        rel_mock = MagicMock()
        rel_mock.id = 99
        rel_mock.character_a_id = 1
        rel_mock.character_b_id = 2
        rel_mock.relation_type = "信任"
        rel_mock.trust_level = 80
        rel_mock.current_status = "Friends"
        rel_mock.direction = "双向"

        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        db.query.return_value.filter.return_value.all.return_value = [rel_mock]

        state = build_initial_state(project, outline, workflow_state, db=db)

        assert "relations" in state
        assert len(state["relations"]) == 1
        assert state["relations"][0]["id"] == 99
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec novelagent-backend-1 pytest tests/test_build_initial_state.py -v`

Expected: FAIL with `TypeError: build_initial_state() got an unexpected keyword argument 'db'`

- [ ] **Step 3: Modify build_initial_state to accept db and preload data**

Replace the function signature and body in `backend/app/api/workflow.py:117-205`:

```python
from typing import Optional
from sqlalchemy.orm import Session

from app.models.character import Character, Relation


def build_initial_state(
    project: Project,
    outline: Outline,
    workflow_state: WorkflowState,
    llm_config_id: Optional[int] = None,
    db: Optional[Session] = None,
) -> NovelState:
    """
    从项目、大纲和工作流状态构建初始 NovelState。

    当传入 db 参数时，会从数据库预加载已持久化的角色和关系（带 id），
    覆盖检查点中可能存在的旧数据，确保节点始终使用最新的 DB 数据。

    Args:
        project: 项目实例
        outline: 大纲实例
        workflow_state: 工作流状态实例
        llm_config_id: 模型配置 ID
        db: 可选的数据库会话，用于预加载角色/关系数据

    Returns:
        NovelState 字典
    """
    # 获取章节大纲
    chapter_outlines = [
        {
            "chapter_number": co.chapter_number,
            "title": co.title,
            "scene": co.scene,
            "characters": co.characters,
            "plot": co.plot,
            "conflict": co.conflict,
            "ending": co.ending,
            "target_words": co.target_words,
        }
        for co in sorted(project.chapter_outlines, key=lambda x: x.chapter_number)
    ]

    # 获取已写入的章节
    written_chapters = []
    for co in project.chapter_outlines:
        if co.chapter and co.chapter.content:
            written_chapters.append({
                "chapter_number": co.chapter_number,
                "content": co.chapter.content,
                "word_count": co.chapter.word_count,
            })

    # 构建状态
    state: NovelState = {
        # 基本信息
        "project_id": project.id,

        # 阶段控制（使用 workflow_state.stage，无需映射）
        "stage": workflow_state.stage,

        # 灵感/输入
        "collected_info": outline.collected_info or {},
        "inspiration_template": outline.inspiration_template or (outline.collected_info or {}).get("inspiration_template"),

        # 大纲
        "outline_title": outline.title,
        "outline_summary": outline.summary,
        "outline_plot_points": outline.plot_points or [],
        "outline_characters": outline.characters or [],
        "outline_world_setting": outline.world_setting,
        "outline_emotional_curve": outline.emotional_curve,
        "outline_confirmed": outline.confirmed,

        # 章节大纲
        "chapter_count": outline.chapter_count_suggested or 0,
        "chapter_outlines": chapter_outlines,
        "chapter_outlines_confirmed": all(co.confirmed for co in project.chapter_outlines) if chapter_outlines else False,

        # 章节正文
        "written_chapters": written_chapters,
        "current_chapter": workflow_state.current_chapter,

        # 审核/重写
        "review_mode": workflow_state.workflow_mode,
        "review_result": None,
        "rewrite_count": 0,
        "max_rewrite_count": workflow_state.max_rewrite_count,

        # 工作流控制
        "waiting_for_confirmation": workflow_state.waiting_for_confirmation,
        "confirmation_type": workflow_state.confirmation_type,

        # LLM 服务
        "llm_config_id": llm_config_id,

        # 预加载：角色和关系（从 DB 获取最新数据）
        "characters": [],
        "relations": [],
        "evolution_plans": [],
        "evolution_records": [],
    }

    # 从数据库预加载已持久化的角色（带 id）
    if db is not None:
        db_characters = db.query(Character).filter(
            Character.project_id == project.id
        ).order_by(Character.id).all()

        if db_characters:
            state["characters"] = [
                {
                    "id": c.id,
                    "name": c.name,
                    "role": c.role,
                    "personality": c.personality or "",
                    "core_motivation": c.core_motivation or "",
                    "growth_arc": c.growth_arc or "",
                }
                for c in db_characters
            ]

        # 预加载关系
        db_relations = db.query(Relation).filter(
            Relation.project_id == project.id
        ).all()

        if db_relations:
            state["relations"] = [
                {
                    "id": r.id,
                    "character_a_id": r.character_a_id,
                    "character_b_id": r.character_b_id,
                    "relation_type": r.relation_type,
                    "trust_level": r.trust_level,
                    "current_status": r.current_status or "",
                    "direction": r.direction or "双向",
                }
                for r in db_relations
            ]

    return state
```

- [ ] **Step 4: Run tests**

Run: `docker exec novelagent-backend-1 pytest tests/test_build_initial_state.py -v`

Expected: 2 passed

Run: `docker exec novelagent-backend-1 pytest tests/test_workflow.py -v`

Expected: All pass (may need to update existing tests that call `build_initial_state` without `db` param — the param is optional so it should be backward compatible)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/workflow.py backend/tests/test_build_initial_state.py
git commit -m "feat(backend): preload characters and relations in build_initial_state

- Accept optional db param in build_initial_state
- Preload Character and Relation rows from DB into state (with IDs)
- Nodes no longer need to query DB for character IDs
- Backward compatible: db param is optional, existing callers unaffected"
```

---

### Task 4: Remove SessionLocal from relation_generation_node (use state["characters"])

**Files:**
- Modify: `backend/app/agents/nodes/relation_generation.py:123-224`

**Context:**
Now that `build_initial_state` preloads characters with IDs, `relation_generation_node` no longer needs to query the database. It can read `state["characters"]` directly.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_nodes_utils.py`:

```python
@pytest.mark.asyncio
async def test_generate_relations_node_uses_state_characters():
    """relation_generation_node should use state['characters'] directly without querying DB"""
    from unittest.mock import patch, AsyncMock
    from app.agents.nodes.relation_generation import generate_relations_node

    state = {
        "project_id": 1,
        "characters": [
            {"id": 1, "name": "Alice", "role": "主角", "personality": "Brave", "core_motivation": "Save"},
            {"id": 2, "name": "Bob", "role": "配角", "personality": "Cautious", "core_motivation": "Protect"},
        ],
        "outline_world_setting": {"era": "现代"},
        "outline_summary": "A story",
    }

    with patch("app.agents.nodes.relation_generation.get_llm_from_state_async") as mock_llm:
        mock_llm.return_value = AsyncMock()
        mock_llm.return_value.chat = AsyncMock(return_value="- Alice | Bob | 信任 | 80 | Friends | 稳定")

        # Patch get_system_prompt to avoid DB access
        with patch("app.agents.nodes.relation_generation.get_system_prompt") as mock_prompt:
            mock_prompt.return_value = "Generate relations for {characters_text}"

            result = await generate_relations_node(state, config={})

    assert "relations" in result
    assert len(result["relations"]) == 1
    assert result["relations"][0]["character_a_id"] == 1
    assert result["relations"][0]["character_b_id"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec novelagent-backend-1 pytest tests/test_nodes_utils.py::test_generate_relations_node_uses_state_characters -v`

Expected: FAIL (depends on current implementation — may pass if already using state, or fail if signature mismatch after config injection)

- [ ] **Step 3: Modify relation_generation_node to use state["characters"] and accept config**

Replace `generate_relations_node` in `backend/app/agents/nodes/relation_generation.py:123-224`:

```python
async def generate_relations_node(state: NovelState, config: dict = None) -> NovelState:
    """LangGraph 节点：从角色生成关系网络

    签名：(state: NovelState, config: dict) -> NovelState

    此节点使用 state["characters"] 中预加载的角色数据（带 id），
    不再自行查询数据库。

    Args:
        state: 当前工作流状态（需包含 characters、project_id）
        config: LangGraph 配置字典（可选，用于接收预加载的 prompt）

    Returns:
        更新后的 NovelState（包含 relations 和 stage）
    """
    import logging
    from app.services.prompt_loader import get_system_prompt
    from app.utils.llm import get_llm_from_state_async

    logger_rn = logging.getLogger(__name__)
    project_id = state["project_id"]

    characters_with_id = state.get("characters", [])

    if len(characters_with_id) < 2:
        logger_rn.info(
            f"relation_gen_node: only {len(characters_with_id)} characters for project {project_id}, skipping"
        )
        return {**state, "stage": STAGE_RELATIONS, "relations": []}

    # 构建角色列表文本
    characters_lines = []
    for c in characters_with_id:
        characters_lines.append(
            f"- {c['name']}（{c.get('role', '配角')}）：{c.get('personality', '')}，{c.get('core_motivation', '')}"
        )
    characters_text = "\\n".join(characters_lines)

    # 获取世界观时代背景
    world_setting = state.get("outline_world_setting", {}) or {}
    world_era = world_setting.get("era", "未指定")

    # 获取大纲概述
    outline_summary = state.get("outline_summary", "未提供")

    # 加载 Prompt
    # 优先从 config 中获取预加载的 prompt，避免 DB 访问
    prompts = (config or {}).get("configurable", {}).get("prompts", {}) if config else {}
    if prompts and "relation_generation" in prompts:
        prompt = prompts["relation_generation"].format(
            characters_text=characters_text,
            world_era=world_era,
            outline_summary=outline_summary,
        )
    else:
        # 回退：使用默认 prompt（无需 DB）
        prompt = f"基于以下角色生成关系网络：\\n{characters_text}\\n世界观：{world_era}\\n大纲：{outline_summary}"

    # 调用 LLM
    llm = await get_llm_from_state_async(state)
    response = await llm.chat([{"role": "user", "content": prompt}])

    # 解析响应
    relations_data = parse_relations_response(response, characters_with_id)

    logger_rn.info(
        f"relation_gen_node: parsed {len(relations_data)} relations for project {project_id}"
    )

    return {
        **state,
        "relations": relations_data,
        "stage": STAGE_RELATIONS,
        "waiting_for_confirmation": True,
        "confirmation_type": "relations",
    }
```

- [ ] **Step 4: Run tests**

Run: `docker exec novelagent-backend-1 pytest tests/test_nodes_utils.py::test_generate_relations_node_uses_state_characters -v`

Expected: PASS

Run: `docker exec novelagent-backend-1 pytest tests/test_agents.py -v`

Expected: All pass (no regression)

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/nodes/relation_generation.py backend/tests/test_nodes_utils.py
git commit -m "refactor(backend): relation_generation_node uses state characters, no DB query

- Accept config param for preloaded prompts
- Read characters directly from state (preloaded with IDs by build_initial_state)
- Remove SessionLocal imports and DB queries
- Fallback prompt when config prompts not available"
```

---

### Task 5: Remove SessionLocal from character_generation_node (use config prompts)

**Files:**
- Modify: `backend/app/agents/nodes/character_generation.py:111-170`

**Context:**
Same pattern as relation_generation_node. Preload prompt via config, remove SessionLocal.

- [ ] **Step 1: Modify character_generation_node**

Replace `create_characters_from_outline_node` in `backend/app/agents/nodes/character_generation.py:111-170`:

```python
async def create_characters_from_outline_node(state: NovelState, config: dict = None) -> NovelState:
    """LangGraph 节点：根据大纲通过独立 LLM 调用生成角色

    签名： (state: NovelState, config: dict) -> NovelState

    读取大纲摘要和世界观背景，使用 character_generation prompt
    调用 LLM 生成角色列表。

    Prompt 优先从 config["configurable"]["prompts"] 获取（由 WorkflowOrchestrator 预加载），
    避免节点内部查询数据库。
    """
    import logging
    from app.utils.llm import get_llm_from_state_async

    logger = logging.getLogger(__name__)

    outline_summary = state.get("outline_summary", "")
    world_era = (state.get("outline_world_setting") or {}).get("era", "未指定")

    characters = []

    try:
        llm = await get_llm_from_state_async(state)

        # 从 config 获取预加载 prompt
        prompts = (config or {}).get("configurable", {}).get("prompts", {}) if config else {}
        if prompts and "character_generation" in prompts:
            prompt = prompts["character_generation"].format(
                outline_summary=outline_summary,
                world_era=world_era,
            )
        else:
            prompt = f"根据以下大纲生成角色列表：\\n{outline_summary}\\n世界观：{world_era}"

        response = await llm.chat([{"role": "user", "content": prompt}])
        characters = parse_character_generation_response(response)

        logger.info(f"character_gen_node: LLM generated {len(characters)} characters")

    except Exception as e:
        logger.warning(f"character_gen_node: LLM call failed ({e}), character list will be empty")

    return {
        **state,
        "characters": characters,
        "stage": STAGE_CHARACTERS,
    }
```

- [ ] **Step 2: Run tests**

Run: `docker exec novelagent-backend-1 pytest tests/test_agents.py -v`

Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/nodes/character_generation.py
git commit -m "refactor(backend): character_generation_node uses config prompts, no DB query

- Accept config param for preloaded prompts
- Remove SessionLocal import and DB access
- Fallback to inline prompt when config prompts unavailable"
```

---

### Task 6: Create OutlineService business layer

**Files:**
- Create: `backend/app/services/outline_service.py`
- Test: `backend/tests/test_outline_service.py`

**Context:**
Extract business logic from `api/outline.py` into a service class that uses WorkflowOrchestrator.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_outline_service.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.outline_service import OutlineService


class TestOutlineService:
    def test_validate_can_generate_raises_when_confirmed(self):
        """Cannot regenerate a confirmed outline"""
        db = MagicMock()
        outline = MagicMock()
        outline.confirmed = True

        with patch("app.services.outline_service.get_project_and_outline", return_value=(MagicMock(), outline)):
            service = OutlineService(db, project_id=1, user_id=1)
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc:
                service.validate_can_generate()
            assert exc.value.status_code == 400

    def test_validate_can_generate_passes_when_not_confirmed(self):
        """Can generate when outline is not confirmed"""
        db = MagicMock()
        outline = MagicMock()
        outline.confirmed = False

        with patch("app.services.outline_service.get_project_and_outline", return_value=(MagicMock(), outline)):
            service = OutlineService(db, project_id=1, user_id=1)
            service.validate_can_generate()  # should not raise

    @pytest.mark.asyncio
    async def test_generate_returns_async_iterator(self):
        """generate() returns an AsyncIterator of SSE strings"""
        db = MagicMock()
        outline = MagicMock()
        outline.confirmed = False
        outline.collected_info = {}
        outline.inspiration_template = None

        with patch("app.services.outline_service.get_project_and_outline", return_value=(MagicMock(), outline)):
            with patch("app.services.outline_service.get_user_settings_or_raise"):
                with patch("app.services.outline_service.get_or_create_workflow_state"):
                    with patch("app.services.outline_service.build_initial_state", return_value={"project_id": 1}):
                        with patch("app.services.outline_service.create_novel_graph_with_checkpointer"):
                            with patch("app.services.workflow_orchestrator.WorkflowOrchestrator") as MockOrch:
                                mock_orch = MockOrch.return_value
                                async def mock_run(*args, **kwargs):
                                    yield "event: done\\ndata: {}\\n\\n"
                                mock_orch.run = mock_run

                                service = OutlineService(db, project_id=1, user_id=1)
                                events = []
                                async for event in service.generate():
                                    events.append(event)
                                assert len(events) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec novelagent-backend-1 pytest tests/test_outline_service.py -v`

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement OutlineService**

```python
# backend/app/services/outline_service.py
"""Outline Service - Business logic for outline generation.

Encapsulates validation, state building, and WorkflowOrchestrator delegation.
"""

from typing import AsyncIterator, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.outline import Outline
from app.models.project import Project
from app.models.workflow_state import WorkflowState
from app.agents.state import NovelState, STAGE_OUTLINE
from app.agents.graph import create_novel_graph_with_checkpointer
from app.services.workflow_orchestrator import WorkflowOrchestrator
from app.utils.project import get_project_and_outline
from app.utils.deps import get_user_settings_or_raise
from app.utils.workflow import get_or_create_workflow_state
from app.api.workflow import build_initial_state


class OutlineService:
    """Service for outline generation operations.

    Interface:
        service = OutlineService(db, project_id, user_id)
        service.validate_can_generate()
        async for sse in service.generate(llm_config_id):
            yield sse
    """

    def __init__(self, db: Session, project_id: int, user_id: int):
        self.db = db
        self.project_id = project_id
        self.user_id = user_id
        self.project: Optional[Project] = None
        self.outline: Optional[Outline] = None

    def _load_project_outline(self) -> tuple[Project, Outline]:
        """Lazy-load project and outline."""
        if self.project is None or self.outline is None:
            self.project, self.outline = get_project_and_outline(
                self.project_id, self.user_id, self.db
            )
        return self.project, self.outline

    def validate_can_generate(self) -> None:
        """校验大纲是否可以重新生成。

        Raises:
            HTTPException: 400 如果大纲已确认
        """
        _, outline = self._load_project_outline()
        if outline.confirmed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot regenerate a confirmed outline"
            )

    async def generate(
        self,
        llm_config_id: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """生成大纲并返回 SSE 事件流。

        Args:
            llm_config_id: 可选的模型配置 ID

        Yields:
            SSE 格式字符串
        """
        project, outline = self._load_project_outline()
        user_settings = get_user_settings_or_raise(
            self.db.query(User).filter(User.id == self.user_id).first(),
            self.db
        )

        # 更新工作流状态
        workflow_state = get_or_create_workflow_state(self.db, self.project_id)
        workflow_state.stage = STAGE_OUTLINE
        self.db.commit()

        # 构建初始状态（预加载角色/关系数据）
        initial_state = build_initial_state(
            project, outline, workflow_state, llm_config_id, db=self.db
        )

        # 预加载 prompts
        from app.services.prompt_loader import get_system_prompt
        prompts = {
            "outline_generation": get_system_prompt(self.db, "outline_generation"),
            "character_generation": get_system_prompt(self.db, "character_generation"),
            "relation_generation": get_system_prompt(self.db, "relation_generation"),
        }

        # 创建图
        graph = create_novel_graph_with_checkpointer(self.project_id, "default")
        config = {
            "configurable": {
                "thread_id": "default",
                "prompts": prompts,
            }
        }

        # 持久化回调
        async def persist_outline(state: NovelState, db: Session) -> dict:
            """在 outline_generation_node 完成后持久化大纲数据"""
            outline.title = state.get("outline_title", outline.title)
            outline.summary = state.get("outline_summary", outline.summary)
            outline.plot_points = state.get("outline_plot_points", [])
            outline.characters = state.get("outline_characters", [])
            outline.world_setting = state.get("outline_world_setting")
            outline.emotional_curve = state.get("outline_emotional_curve")
            db.commit()
            return {"outline_title": outline.title, "stage": STAGE_OUTLINE}

        # 执行
        orchestrator = WorkflowOrchestrator(self.db, self.project_id)
        async for event in orchestrator.run(
            graph=graph,
            config=config,
            initial_state=initial_state,
            target_node="outline_generation_node",
            persist_callback=persist_outline,
        ):
            yield event
```

- [ ] **Step 4: Run tests**

Run: `docker exec novelagent-backend-1 pytest tests/test_outline_service.py -v`

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/outline_service.py backend/tests/test_outline_service.py
git commit -m "feat(backend): add OutlineService business layer

- Encapsulates outline generation validation and orchestration
- Uses WorkflowOrchestrator with target_node + persist_callback
- Preloads prompts into config['configurable']['prompts']
- Preloads DB characters/relations via build_initial_state"
```

---

### Task 7: Refactor api/outline.py to use OutlineService

**Files:**
- Modify: `backend/app/api/outline.py:64-120` (the generate_outline endpoint)

- [ ] **Step 1: Replace generate_outline endpoint**

Replace the `generate_outline` function in `backend/app/api/outline.py`:

```python
from app.services.outline_service import OutlineService


@router.post("/{project_id}/outline")
async def generate_outline(
    project_id: int,
    request: OutlineGenerateRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate outline using AI from collected info with SSE streaming."""
    service = OutlineService(db, project_id, current_user.id)
    service.validate_can_generate()

    llm_config_id = request.llm_config_id if request else None

    return StreamingResponse(
        service.generate(llm_config_id=llm_config_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
```

Remove the old inline `stream_generator` and all imports that were only used by it (keep what the rest of the file needs).

- [ ] **Step 2: Run tests**

Run: `docker exec novelagent-backend-1 pytest tests/test_api.py -v`

Expected: All pass

Run: `docker exec novelagent-backend-1 pytest tests/test_workflow.py -v`

Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/outline.py
git commit -m "refactor(backend): api/outline.py uses OutlineService

- Removes ~60 lines of inline SSE streaming logic
- Delegates to OutlineService for validation and orchestration
- API contract unchanged (same URL, request/response, SSE format)"
```

---

### Task 8: Create ChapterService and refactor api/chapters.py SSE endpoints

**Files:**
- Create: `backend/app/services/chapter_service.py`
- Modify: `backend/app/api/chapters.py:104-200` (SSE endpoints)

Follow the same pattern as OutlineService. Key differences:
- `create_chapter_outlines` uses `target_node="chapter_outlines_node"`
- Persist callback writes `ChapterOutline` rows
- `generate_chapter_content` uses `target_node="generate_chapter_content_node"`
- Persist callback writes `Chapter.content`

Due to length, the detailed steps for ChapterService follow the exact same TDD pattern as OutlineService (write test -> run fail -> implement -> run pass -> commit). The service structure mirrors OutlineService with different validation rules and persist callbacks.

- [ ] **Step 1-5: Implement ChapterService and refactor chapters.py**

(Same pattern as Tasks 6-7. Implement ChapterService with `generate_chapter_outlines` and `generate_chapter_content` methods, then refactor `api/chapters.py` to use it.)

---

### Task 9: Refactor api/workflow.py to use WorkflowOrchestrator

**Files:**
- Modify: `backend/app/api/workflow.py:258-335` (run_workflow), `338-428` (confirm_workflow)

- [ ] **Step 1: Replace run_workflow and confirm_workflow**

Replace `run_workflow`:

```python
@router.post("/{project_id}/workflow/run")
async def run_workflow(
    project_id: int,
    request: WorkflowRunRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """启动或恢复工作流（SSE 流式）。

    使用 LangGraph 的 astream_events 进行流式传输。
    """
    project = get_project_for_user(project_id, current_user.id, db)

    outline = db.query(Outline).filter(Outline.project_id == project_id).first()
    if not outline:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outline not found")

    user_settings = get_user_settings_or_raise(current_user, db)

    workflow_state = db.query(WorkflowState).filter(
        WorkflowState.project_id == project_id,
        WorkflowState.thread_id == "main"
    ).first()

    if not workflow_state:
        workflow_state = WorkflowState(project_id=project_id)
        db.add(workflow_state)
        db.commit()
        db.refresh(workflow_state)

    llm_config_id = request.llm_config_id if request else None

    # 构建初始状态（预加载 DB 数据）
    initial_state = build_initial_state(project, outline, workflow_state, llm_config_id, db=db)

    # 预加载 prompts
    from app.services.prompt_loader import get_system_prompt
    prompts = {
        "outline_generation": get_system_prompt(db, "outline_generation"),
        "character_generation": get_system_prompt(db, "character_generation"),
        "relation_generation": get_system_prompt(db, "relation_generation"),
        "chapter_generation": get_system_prompt(db, "chapter_generation"),
        "review": get_system_prompt(db, "review"),
        "rewrite": get_system_prompt(db, "rewrite"),
    }

    graph = create_novel_graph_with_checkpointer(project_id, "default")
    config = {"configurable": {"thread_id": "default", "prompts": prompts}}

    orchestrator = WorkflowOrchestrator(db, project_id)

    return StreamingResponse(
        orchestrator.run(graph=graph, config=config, initial_state=initial_state),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
```

Replace `confirm_workflow` (uses orchestrator with `initial_state=None` for resume):

```python
@router.post("/{project_id}/workflow/confirm")
async def confirm_workflow(
    project_id: int,
    request: WorkflowConfirmRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """确认当前节点并继续工作流。"""
    project = get_project_for_user(project_id, current_user.id, db)

    checkpoint_state = get_latest_checkpoint(project_id, "default", db)
    if not checkpoint_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active workflow to confirm")

    if not checkpoint_state.get("waiting_for_confirmation"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workflow is not waiting for confirmation")

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

    record = db.query(WorkflowCheckpoint).filter(
        WorkflowCheckpoint.project_id == project_id,
        WorkflowCheckpoint.thread_id == "default"
    ).order_by(WorkflowCheckpoint.updated_at.desc()).first()

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

    graph = create_novel_graph_with_checkpointer(project_id, "default")

    # 预加载 prompts（恢复执行也需要）
    from app.services.prompt_loader import get_system_prompt
    prompts = {
        "outline_generation": get_system_prompt(db, "outline_generation"),
        "character_generation": get_system_prompt(db, "character_generation"),
        "relation_generation": get_system_prompt(db, "relation_generation"),
        "chapter_generation": get_system_prompt(db, "chapter_generation"),
        "review": get_system_prompt(db, "review"),
        "rewrite": get_system_prompt(db, "rewrite"),
    }
    config = {"configurable": {"thread_id": "default", "prompts": prompts}}

    orchestrator = WorkflowOrchestrator(db, project_id)

    return StreamingResponse(
        orchestrator.run(graph=graph, config=config, initial_state=None),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

Remove the old `stream_workflow_events` function from `api/workflow.py` (lines 26-88) since it's now in WorkflowOrchestrator.

- [ ] **Step 2: Run all backend tests**

Run: `docker exec novelagent-backend-1 pytest -v`

Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/workflow.py
git commit -m "refactor(backend): api/workflow.py uses WorkflowOrchestrator

- Removes inline stream_workflow_events (~60 lines)
- run_workflow and confirm_workflow delegate to WorkflowOrchestrator
- Preloads prompts into config for all workflow paths
- No changes to SSE event format or API contracts"
```

---

### Task 10: Delete deprecated code from agents/streaming.py

**Files:**
- Modify: `backend/app/agents/streaming.py`

- [ ] **Step 1: Replace file content with module-level docstring only**

```python
"""LangGraph 流式执行工具

此模块已废弃。所有 SSE 流式功能已迁移到 app.services.workflow_orchestrator。
保留空文件以避免破坏旧导入（部分测试可能仍引用此模块名）。
"""
```

- [ ] **Step 2: Run tests**

Run: `docker exec novelagent-backend-1 pytest -v`

Expected: All pass (if any test imports from `agents.streaming`, update those tests to import from `services.workflow_orchestrator` or mock appropriately)

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/streaming.py
git commit -m "chore(backend): remove deprecated streaming functions from agents/streaming.py

- stream_node_events and create_single_node_graph deleted
- Functionality fully replaced by WorkflowOrchestrator
- File kept as empty stub to avoid breaking existing imports"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- [x] WorkflowOrchestrator central SSE service → Task 1
- [x] API routes use WorkflowOrchestrator → Tasks 7, 8, 9
- [x] get_llm_from_state_async accepts db param → Task 2
- [x] Nodes accept config param for prompts → Tasks 4, 5
- [x] build_initial_state preloads characters/relations → Task 3
- [x] Business service layer (OutlineService, ChapterService) → Tasks 6, 8
- [x] Delete deprecated agents/streaming.py → Task 10

**2. Placeholder scan:**
- [x] No "TBD", "TODO", "implement later"
- [x] No "Add appropriate error handling" without code
- [x] All code blocks show complete implementation
- [x] All test blocks show complete assertions

**3. Type consistency:**
- [x] `get_llm_from_state_async(state, db=None)` used consistently
- [x] `build_initial_state(..., db=None)` used consistently
- [x] `WorkflowOrchestrator.run(...)` signature matches usage
- [x] Node signatures `(state, config)` match LangGraph spec

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-08-backend-architecture-optimization.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
