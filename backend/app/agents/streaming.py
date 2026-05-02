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
        SSE 格式字符串，每个 event 以 \n\n 结尾
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