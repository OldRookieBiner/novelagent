"""Tests for WorkflowOrchestrator central SSE streaming service."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_graph():
    """Mock compiled LangGraph graph."""
    return MagicMock()


@pytest.fixture
def mock_db():
    """Mock SQLAlchemy Session."""
    db = MagicMock()
    db.rollback = MagicMock()
    return db


class TestWorkflowOrchestrator:
    def test_init(self, mock_db):
        """WorkflowOrchestrator stores db and project_id."""
        from app.services.workflow_orchestrator import WorkflowOrchestrator

        orch = WorkflowOrchestrator(mock_db, project_id=1)
        assert orch.db == mock_db
        assert orch.project_id == 1

    @pytest.mark.asyncio
    async def test_run_yields_node_start_event(self, mock_graph, mock_db):
        """When graph emits on_chain_start, orchestrator yields node_start SSE."""
        from app.services.workflow_orchestrator import WorkflowOrchestrator

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

        assert len(events) >= 2
        assert "event: node_start" in events[1]
        data = json.loads(events[1].split("data: ")[1])
        assert data["node"] == "outline_generation_node"

    @pytest.mark.asyncio
    async def test_run_yields_chunk_event(self, mock_graph, mock_db):
        """When graph emits on_chat_model_stream, orchestrator yields chunk SSE."""
        from app.services.workflow_orchestrator import WorkflowOrchestrator

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
    async def test_run_yields_waiting_and_done_when_waiting_for_confirmation(
        self, mock_graph, mock_db
    ):
        """When node_done output has waiting_for_confirmation=True, yield waiting + done."""
        from app.services.workflow_orchestrator import WorkflowOrchestrator

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
        """When target node completes, persist callback is called with state."""
        from app.services.workflow_orchestrator import WorkflowOrchestrator

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
        """When persist callback raises, db is rolled back and error SSE is yielded."""
        from app.services.workflow_orchestrator import WorkflowOrchestrator

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
