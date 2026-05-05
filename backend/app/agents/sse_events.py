"""统一的 SSE 事件格式化工具

所有 SSE 事件字符串的生成集中在此模块，避免在多个文件中重复内联格式化。
"""

import json
from typing import Any


def format_node_start(node_name: str, message: str = "Starting") -> str:
    """格式化节点开始 SSE 事件"""
    return (
        f"event: node_start\n"
        f"data: {json.dumps({'node': node_name, 'message': message})}\n\n"
    )


def format_node_done(node_name: str, output: dict[str, Any]) -> str:
    """格式化节点完成 SSE 事件"""
    return (
        f"event: node_done\n"
        f"data: {json.dumps({'node': node_name, 'state': output})}\n\n"
    )


def format_chunk(content: str) -> str:
    """格式化内容块 SSE 事件"""
    return f"event: chunk\ndata: {json.dumps({'content': content})}\n\n"


def format_done(message: str = "Workflow completed", extra: dict[str, Any] | None = None) -> str:
    """格式化完成 SSE 事件"""
    data: dict[str, Any] = {"message": message}
    if extra:
        data.update(extra)
    return f"event: done\ndata: {json.dumps(data)}\n\n"


def format_waiting(confirmation_type: str) -> str:
    """格式化等待确认 SSE 事件"""
    return (
        f"event: waiting\n"
        f"data: {json.dumps({'confirmation_type': confirmation_type})}\n\n"
    )


def format_error_message(error_message: str) -> str:
    """格式化错误 SSE 事件（仅消息字符串）"""
    return f"event: error\ndata: {json.dumps({'error': error_message})}\n\n"


def extract_chunk_from_event(event_data: dict[str, Any]) -> str | None:
    """从 LangGraph astream_events 的 on_chat_model_stream 事件中提取内容"""
    chunk = event_data.get("chunk")
    if chunk:
        content = getattr(chunk, "content", str(chunk))
        if content:
            return content
    return None