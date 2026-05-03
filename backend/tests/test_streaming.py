"""测试 stream_node_events 的 SSE 事件格式"""
import pytest
import json
from unittest.mock import MagicMock, AsyncMock


class AsyncIteratorMock:
    """异步迭代器 mock"""
    def __init__(self, items):
        self.items = items

    def __aiter__(self):
        self._index = 0
        return self

    async def __anext__(self):
        if self._index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self._index]
        self._index += 1
        return item


@pytest.mark.asyncio
async def test_stream_node_events_chunk_has_event_prefix():
    """chunk 事件必须包含 event: chunk 前缀和数据格式 {"content": "..."}"""
    mock_chunk = MagicMock()
    mock_chunk.content = "测试文本"

    mock_event_stream = [
        {
            "event": "on_chat_model_stream",
            "name": "ChatOpenAI",
            "data": {"chunk": mock_chunk},
        },
        {
            "event": "on_chain_end",
            "name": "execute",
            "data": {"output": {"stage": "writing"}},
        },
    ]

    mock_graph = AsyncMock()
    mock_graph.astream_events = MagicMock(return_value=AsyncIteratorMock(mock_event_stream))

    from app.agents.streaming import stream_node_events

    events = []
    async for sse_event in stream_node_events(mock_graph, {}, {"configurable": {"thread_id": "test"}}):
        events.append(sse_event)

    # 验证 chunk 事件有 event: chunk 前缀
    chunk_events = [e for e in events if "event: chunk" in e]
    assert len(chunk_events) > 0, f"未找到 event: chunk 事件，实际事件: {events}"

    # 验证 chunk 事件的 data 是 {"content": "..."} 格式
    for chunk_event in chunk_events:
        assert chunk_event.startswith("event: chunk\ndata: ")
        data_str = chunk_event.split("data: ", 1)[1].strip()
        data = json.loads(data_str)
        assert "content" in data
        assert data["content"] == "测试文本"


@pytest.mark.asyncio
async def test_stream_node_events_done_event_format():
    """done 事件格式验证"""
    mock_done_event = {
        "event": "on_chain_end",
        "name": "execute",
        "data": {"output": {"stage": "writing", "written_chapters": []}},
    }

    mock_graph = AsyncMock()
    mock_graph.astream_events = MagicMock(return_value=AsyncIteratorMock([mock_done_event]))

    from app.agents.streaming import stream_node_events

    events = []
    async for sse_event in stream_node_events(mock_graph, {}, {"configurable": {"thread_id": "test"}}):
        events.append(sse_event)

    done_events = [e for e in events if e.startswith("event: done")]
    assert len(done_events) == 1
    data_str = done_events[0].split("data: ", 1)[1].strip()
    data = json.loads(data_str)
    assert "state" in data


@pytest.mark.asyncio
async def test_stream_node_events_node_start():
    """node_start 事件格式验证"""
    mock_chain_start = {
        "event": "on_chain_start",
        "name": "execute",
        "data": {"input": {}},
    }
    mock_done_event = {
        "event": "on_chain_end",
        "name": "execute",
        "data": {"output": {"stage": "writing"}},
    }

    mock_graph = AsyncMock()
    mock_graph.astream_events = MagicMock(return_value=AsyncIteratorMock([mock_chain_start, mock_done_event]))

    from app.agents.streaming import stream_node_events

    events = []
    async for sse_event in stream_node_events(mock_graph, {}, {"configurable": {"thread_id": "test"}}):
        events.append(sse_event)

    # 应包含初始 node_start 和 on_chain_start 触发的 node_start
    node_start_events = [e for e in events if "event: node_start" in e]
    assert len(node_start_events) >= 1
