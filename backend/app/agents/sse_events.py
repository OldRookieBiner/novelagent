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


def format_heartbeat() -> str:
    """SSE heartbeat comment to keep connection alive"""
    return ": heartbeat\n\n"



def format_impact_assessment(data: dict) -> str:
    """Format impact assessment report event for frontend display."""
    import json
    return f"event: impact_assessment\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def format_warning(warning_type: str, data: dict) -> str:
    """Format a warning event (foreshadowing overdue, style drift, etc.)."""
    import json
    payload = {"type": warning_type, **data}
    return f"event: warning\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"



# ========== Phase 4: 卷管理事件 ==========


def format_volume_transition(data: dict) -> str:
    """Format volume transition event (卷过渡).

    data: {current_volume, new_volume, chapter_offset, unreclaimed_foreshadowings, active_subplots}
    """
    import json
    return f"event: volume_transition
data: {json.dumps(data, ensure_ascii=False)}

"


def format_volume_review(data: dict) -> str:
    """Format per-volume revision report event (逐卷修订报告).

    data: {volume_number, review_type, issues: [{severity, description, suggestion}]}
    """
    import json
    return f"event: volume_review
data: {json.dumps(data, ensure_ascii=False)}

"


def format_revision_report(data: dict) -> str:
    """Format full-book revision report event (全书修订报告).

    data: {revision_context, total_volumes, issues: [{severity, description, suggestion}],
           modifications: [{chapter, location, change}]}
    """
    import json
    return f"event: revision_report
data: {json.dumps(data, ensure_ascii=False)}

"


# Backward compatibility alias
format_error_message = format_sse_error


# Backward compatibility stubs for legacy agent.py
def format_agent_text(content: str) -> str:
    return format_chunk(content)

def format_agent_tool_start(tool_name: str, args: dict = None) -> str:
    import json
    return f"event: agent_tool_start\ndata: {json.dumps({'tool': tool_name, 'args': args or {}}, ensure_ascii=False)}\n\n"

def format_agent_tool_result(tool_name: str, result: str) -> str:
    import json
    return f"event: agent_tool_result\ndata: {json.dumps({'tool': tool_name, 'result': result}, ensure_ascii=False)}\n\n"

def format_agent_done(message: str = "完成") -> str:
    return format_done(message)

def format_ai_update(data: dict) -> str:
    return format_progress(data)

def format_agent_review(data: dict) -> str:
    import json
    return f"event: agent_review\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

def format_agent_chapter_preview(content: str) -> str:
    return format_chunk(content)
