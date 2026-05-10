"""LangGraph 流式执行工具

已废弃：create_single_node_graph 和 stream_node_events 已被
app.api.workflow.stream_workflow_events 和完整 graph + checkpointer 方案替代。

保留此文件仅用于向后兼容测试导入，实际功能已迁移到 app/api/workflow.py。
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
    """已废弃：使用 app.api.workflow.stream_workflow_events 替代

    此包装函数保持向后兼容的 SSE 事件格式，
    确保旧测试中期望的 event: done 格式仍然可用。
    """
    try:
        yield f"event: node_start\ndata: {json.dumps({'message': 'Starting generation'})}\n\n"

        async for event in graph.astream_events(initial_state, config, version="v2"):
            event_type = event.get("event")
            event_data = event.get("data", {})

            if event_type == "on_chat_model_stream":
                chunk = event_data.get("chunk")
                if chunk:
                    content = getattr(chunk, "content", str(chunk))
                    if content:
                        yield f"event: chunk\ndata: {json.dumps({'content': content})}\n\n"

            elif event_type == "on_chain_end":
                output = event_data.get("output", {})
                if isinstance(output, dict):
                    yield f"event: node_done\ndata: {json.dumps({'state': output})}\n\n"

        # 发送兼容的 done 事件（state 格式）
        yield f"event: done\ndata: {json.dumps({'state': {}})}\n\n"

    except Exception as e:
        error_msg = str(e)
        logger.error(f"stream_node_events error: {error_msg}")
        yield f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"


def create_single_node_graph(node_func, node_name: str = "execute"):
    """已废弃：使用 create_novel_graph_with_checkpointer 替代"""
    graph = StateGraph(NovelState)
    graph.add_node(node_name, node_func)
    graph.set_entry_point(node_name)
    graph.add_edge(node_name, END)
    return graph.compile()