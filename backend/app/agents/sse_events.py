"""统一的 SSE 事件格式化工具

所有 SSE 事件字符串的生成集中在此模块，避免在多个文件中重复内联格式化。
"""

import json
from typing import Any


def format_node_start(node_name: str, message: str | None = None) -> str:
    """格式化节点开始 SSE 事件

    Args:
        node_name: 节点名称
        message: 可选的提示消息，为 None 时不包含 message 字段
    """
    if message is not None:
        data = {'node': node_name, 'message': message}
    else:
        data = {'node': node_name}
    return f"event: node_start\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def format_node_done(node_name: str, output: dict[str, Any]) -> str:
    """格式化节点完成 SSE 事件"""
    return (
        f"event: node_done\n"
        f"data: {json.dumps({'node': node_name, 'state': output}, ensure_ascii=False)}\n\n"
    )


def format_chunk(content: str) -> str:
    """格式化内容块 SSE 事件"""
    return f"event: chunk\ndata: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"


def format_done(message: str = "Workflow completed", extra: dict[str, Any] | None = None) -> str:
    """格式化完成 SSE 事件"""
    data: dict[str, Any] = {"message": message}
    if extra:
        data.update(extra)
    return f"event: done\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def format_waiting(confirmation_type: str, node: str | None = None) -> str:
    """格式化等待确认 SSE 事件

    Args:
        confirmation_type: 确认类型（如 outline, characters, chapter_outlines）
        node: 可选的节点名称，为 None 时不含 node 字段
    """
    data: dict[str, Any] = {"confirmation_type": confirmation_type}
    if node is not None:
        data["node"] = node
    return f"event: waiting\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def format_error_message(error_message: str) -> str:
    """格式化错误 SSE 事件（仅消息字符串）

    对于需要 sanitize 的异常对象，请使用 format_sse_error。
    """
    return f"event: error\ndata: {json.dumps({'error': error_message}, ensure_ascii=False)}\n\n"


def format_sse_error(error: str | Exception) -> str:
    """格式化 SSE 错误事件（含错误消息净化）

    Args:
        error: 原始错误消息或异常对象

    Returns:
        格式化的 SSE 错误事件字符串
    """
    from app.utils.error import sanitize_error_message
    safe_message = sanitize_error_message(error)
    return f"event: error\ndata: {json.dumps({'error': safe_message}, ensure_ascii=False)}\n\n"


def extract_chunk_from_event(event_data: dict[str, Any]) -> str | None:
    """从 LangGraph astream_events 的 on_chat_model_stream 事件中提取内容"""
    chunk = event_data.get("chunk")
    if chunk:
        content = getattr(chunk, "content", str(chunk))
        if content:
            return content
    return None


def format_heartbeat() -> str:
    """格式化 SSE 注释行，保持连接活跃

    SSE 规范：以冒号开头的行是注释，客户端应忽略。
    用于审核等不需要发送中间内容的 SSE 流中，保持连接不被中间代理断开。
    """
    return ": heartbeat\n\n"
