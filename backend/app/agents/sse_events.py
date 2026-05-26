"""SSE 事件格式化工具

集中管理所有 SSE 事件字符串，适配创作智能体的新阶段和节点名称。
"""

from typing import Optional, Any


def format_node_start(node_name: str, data: Optional[dict] = None) -> str:
    """格式化节点开始事件"""
    payload = {"node": node_name}
    if data:
        payload.update(data)
    import json
    return f"event: node_start\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def format_node_done(node_name: str, data: Optional[dict] = None) -> str:
    """格式化节点完成事件"""
    payload = {"node": node_name}
    if data:
        payload.update(data)
    import json
    return f"event: node_done\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def format_chunk(content: str) -> str:
    """格式化流式文本块"""
    import json
    return f"event: chunk\ndata: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"


def format_done(message: str = "完成") -> str:
    """格式化完成事件"""
    import json
    return f"event: done\ndata: {json.dumps({'message': message}, ensure_ascii=False)}\n\n"


def format_waiting(confirmation_type: str, data: Optional[dict] = None) -> str:
    """格式化等待确认事件"""
    payload = {"confirmation_type": confirmation_type}
    if data:
        payload.update(data)
    import json
    return f"event: waiting\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def format_progress(data: dict) -> str:
    """格式化进度事件"""
    import json
    return f"event: progress\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def format_sse_error(error: str) -> str:
    """格式化错误事件"""
    import json
    return f"event: error\ndata: {json.dumps({'error': error}, ensure_ascii=False)}\n\n"
