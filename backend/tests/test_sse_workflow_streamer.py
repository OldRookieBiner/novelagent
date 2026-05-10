"""Tests for shared SSE workflow event streamer"""

import json
from unittest.mock import MagicMock
import pytest

from app.api.workflow import stream_workflow_events


def _make_chunk(content: str) -> MagicMock:
    """Build a mock LangGraph stream chunk"""
    chunk = MagicMock()
    chunk.content = content
    return chunk


def _make_chain_end_event(name: str, output: dict) -> dict:
    """Build on_chain_end event dict"""
    return {
        "event": "on_chain_end",
        "name": name,
        "data": {"output": output},
    }


def _make_chain_start_event(name: str) -> dict:
    """Build on_chain_start event dict"""
    return {
        "event": "on_chain_start",
        "name": name,
        "data": {},
    }


def _make_chat_model_stream_event(content: str) -> dict:
    """Build on_chat_model_stream event dict"""
    return {
        "event": "on_chat_model_stream",
        "name": "ChatOpenAI",
        "data": {"chunk": _make_chunk(content)},
    }


class FakeGraph:
    """Mock compiled LangGraph graph that replays preset events"""

    def __init__(self, events: list[dict]):
        self._events = events

    async def astream_events(self, initial_state, config, version="v2"):
        for event in self._events:
            yield event


class TestStreamWorkflowEvents:
    """Tests for shared SSE workflow event streamer"""

    @pytest.mark.asyncio
    async def test_initial_run_dispatches_node_events(self):
        """Initial run should convert on_chain_start to SSE node_start"""
        graph = FakeGraph([
            _make_chain_start_event("outline_generation_node"),
            _make_chain_end_event(
                "outline_generation_node",
                {"stage": "outline", "waiting_for_confirmation": False},
            ),
        ])
        config = {"configurable": {"thread_id": "test-1"}}

        events = []
        async for sse_event in stream_workflow_events(
            graph, config,
            initial_state={"project_id": 1, "stage": "inspiration"},
        ):
            events.append(sse_event)

        event_types = [e.split("\n")[0] for e in events if e.startswith("event:")]
        assert "event: node_start" in event_types
        assert "event: node_done" in event_types
        assert "event: done" in event_types

    @pytest.mark.asyncio
    async def test_resume_dispatches_resume_event(self):
        """Resume (no initial_state) should emit workflow_resume first"""
        graph = FakeGraph([
            _make_chain_end_event(
                "chapter_outlines_node", {"stage": "chapter_outlines"}
            ),
        ])
        config = {"configurable": {"thread_id": "test-2"}}

        events = []
        async for sse_event in stream_workflow_events(graph, config):
            events.append(sse_event)

        first_data = json.loads(events[0].split("data: ")[1])
        assert first_data["node"] == "workflow_resume"

    @pytest.mark.asyncio
    async def test_waiting_stops_stream(self):
        """waiting_for_confirmation=True should emit waiting and stop"""
        graph = FakeGraph([
            _make_chain_start_event("outline_generation_node"),
            _make_chain_end_event(
                "outline_generation_node",
                {
                    "waiting_for_confirmation": True,
                    "confirmation_type": "outline",
                },
            ),
            _make_chain_end_event(
                "create_characters_from_outline_node", {"stage": "characters"}
            ),
        ])
        config = {"configurable": {"thread_id": "test-3"}}

        events = []
        async for sse_event in stream_workflow_events(
            graph, config,
            initial_state={"project_id": 1, "stage": "outline"},
        ):
            events.append(sse_event)

        event_lines = [e for e in events if e.startswith("event:")]
        waiting_events = [e for e in event_lines if "waiting" in e]
        done_events = [e for e in event_lines if e.startswith("event: done")]

        assert len(waiting_events) == 1
        # waiting 后也会发送 done 事件，通知前端当前阶段完成
        assert len(done_events) == 1

    @pytest.mark.asyncio
    async def test_chat_model_stream_yields_chunks(self):
        """LLM streaming output should become SSE chunk events"""
        graph = FakeGraph([
            _make_chain_start_event("generate_chapter_content_node"),
            _make_chat_model_stream_event("chap1"),
            _make_chat_model_stream_event("content"),
            _make_chain_end_event(
                "generate_chapter_content_node", {"stage": "writing"}
            ),
        ])
        config = {"configurable": {"thread_id": "test-4"}}

        chunks = []
        async for sse_event in stream_workflow_events(
            graph, config,
            initial_state={"project_id": 1, "stage": "writing"},
        ):
            if "event: chunk" in sse_event:
                # 提取 data 行中的 JSON
                for line in sse_event.split("\n"):
                    if line.startswith("data: "):
                        chunks.append(line)

        assert len(chunks) == 2
        c1 = json.loads(chunks[0].split("data: ")[1])
        c2 = json.loads(chunks[1].split("data: ")[1])
        assert c1["content"] == "chap1"
        assert c2["content"] == "content"

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Graph exception should emit SSE error event"""
        graph = FakeGraph([])

        async def broken_stream(*args, **kwargs):
            raise ValueError("LLM API error")
            yield

        graph.astream_events = broken_stream
        config = {"configurable": {"thread_id": "test-5"}}

        events = []
        async for sse_event in stream_workflow_events(
            graph, config, initial_state={"project_id": 1}
        ):
            events.append(sse_event)

        assert any("event: error" in e for e in events)

    @pytest.mark.asyncio
    async def test_sse_format_endswith_double_newline(self):
        """Each SSE event must end with double newline"""
        graph = FakeGraph([
            _make_chain_start_event("test_node"),
            _make_chain_end_event("test_node", {"stage": "outline"}),
        ])
        config = {"configurable": {"thread_id": "test-6"}}

        events = []
        async for sse_event in stream_workflow_events(
            graph, config, initial_state={"project_id": 1}
        ):
            events.append(sse_event)

        for event in events:
            assert event.endswith("\n\n"), f"Missing \\n\\n: {event[:60]}"

    @pytest.mark.asyncio
    async def test_node_done_contains_state(self):
        """node_done events must include state in data payload"""
        graph = FakeGraph([
            _make_chain_end_event("test_node", {
                "stage": "writing",
                "current_chapter": 5,
                "waiting_for_confirmation": False,
            }),
        ])
        config = {"configurable": {"thread_id": "test-7"}}

        events = []
        async for sse_event in stream_workflow_events(
            graph, config, initial_state={"project_id": 1}
        ):
            events.append(sse_event)

        node_done_lines = [e for e in events if "node_done" in e]
        assert len(node_done_lines) == 1
        done_data = json.loads(node_done_lines[0].split("data: ")[1])
        assert "state" in done_data
        assert done_data["state"]["current_chapter"] == 5

    @pytest.mark.asyncio
    async def test_non_dict_output_sends_done_event(self):
        """When output is not a dict (e.g., END string), done event must still be sent.

        Regression test for: 规划完成后报错"发生未知错误"

        When LangGraph workflow routes to END via conditional edges,
        the on_chain_end output is the string "END" rather than a dict.
        The stream_workflow_events must still send a 'done' event in this case.
        """
        # Create an event with non-dict output (simulates END)
        end_event = {
            "event": "on_chain_end",
            "name": "generate_relations_node",
            "data": {"output": "END"},  # Non-dict output
        }
        graph = FakeGraph([end_event])
        config = {"configurable": {"thread_id": "test-8"}}

        events = []
        async for sse_event in stream_workflow_events(
            graph, config, initial_state={"project_id": 1}
        ):
            events.append(sse_event)

        # Must have a done event
        done_events = [e for e in events if "event: done" in e]
        assert len(done_events) >= 1, "Missing done event when output is non-dict"

        # Should NOT have a node_done event for non-dict output
        node_done_events = [e for e in events if "event: node_done" in e]
        assert len(node_done_events) == 0, "Should not have node_done for non-dict output"
