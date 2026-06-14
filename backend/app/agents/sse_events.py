"""SSE 事件格式化工具

集中管理所有 SSE 事件字符串，适配创作智能体的新阶段和节点名称。

修复：
- import json 提取到模块级别（原每个函数内部重复 import）
- format_node_start 第二个参数改为 node_label: str，与 workflow.py 调用签名一致
"""

import json
from typing import Optional








def format_sse_error(error: str) -> str:
    """格式化错误事件"""
    return f"event: error\ndata: {json.dumps({'error': error}, ensure_ascii=False)}\n\n"



def format_impact_assessment(data: dict) -> str:
    """Format impact assessment report event for frontend display."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: impact_assessment\ndata: {payload}\n\n"


def format_warning(warning_type: str, data: dict) -> str:
    """Format a warning event (foreshadowing overdue, style drift, etc.)."""
    payload = {"type": warning_type, **data}
    return f"event: warning\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"







# Backward compatibility alias
format_error_message = format_sse_error


# Backward compatibility stubs for legacy agent.py
def format_agent_text(content: str) -> str:
    """格式化 Agent 文本输出事件"""
    return f"event: agent_text\ndata: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"

def format_agent_tool_start(tool_name: str, args: dict = None) -> str:
    return f"event: agent_tool_start\ndata: {json.dumps({'tool': tool_name, 'args': args or {}}, ensure_ascii=False)}\n\n"

def format_agent_tool_result(tool_name: str, result: str) -> str:
    return f"event: agent_tool_result\ndata: {json.dumps({'tool': tool_name, 'result': result}, ensure_ascii=False)}\n\n"

def format_agent_done(message: str = "完成") -> str:
    """格式化 Agent 完成事件"""
    return f"event: agent_done\ndata: {json.dumps({'message': message}, ensure_ascii=False)}\n\n"

def format_agent_progress(tool_name: str, data: dict) -> str:
    """格式化 Agent 工具进度事件"""
    payload = {"tool": tool_name, **data}
    return f"event: agent_progress\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

def format_ai_update(data: dict) -> str:
    """格式化 AI 更新事件"""
    return f"event: ai_update\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

def format_agent_review(data: dict) -> str:
    return f"event: agent_review\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

def format_agent_chapter_preview(content: str) -> str:
    """格式化 Agent 章节预览事件"""
    return f"event: agent_chapter_preview\ndata: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"


# ========== 项目初始化事件 ==========

def format_init_start() -> str:
    """格式化初始化开始事件"""
    return f"event: init:start\ndata: {json.dumps({}, ensure_ascii=False)}\n\n"


def format_init_concept(data: dict) -> str:
    """格式化概念解析完成事件"""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: init:concept\ndata: {payload}\n\n"


def format_init_novel_name(data: dict) -> str:
    """格式化小说名生成完成事件"""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: init:novel_name\ndata: {payload}\n\n"


def format_init_world(data: dict) -> str:
    """格式化世界观生成完成事件"""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: init:world\ndata: {payload}\n\n"


def format_init_characters(data: dict) -> str:
    """格式化角色生成完成事件"""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: init:characters\ndata: {payload}\n\n"


def format_init_outline(data: dict) -> str:
    """格式化大纲生成完成事件"""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: init:outline\ndata: {payload}\n\n"


def format_init_style(data: dict) -> str:
    """格式化风格设定完成事件"""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: init:style\ndata: {payload}\n\n"


def format_init_complete(data: dict, status: str = "complete") -> str:
    """格式化初始化完成事件"""
    data_with_status = {**data, "status": status}
    payload = json.dumps(data_with_status, ensure_ascii=False)
    return f"event: init:complete\ndata: {payload}\n\n"


def format_init_done(data: dict) -> str:
    """格式化初始化结束事件"""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: init:done\ndata: {payload}\n\n"


def format_init_error(data: dict) -> str:
    """格式化初始化错误事件"""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: init:error\ndata: {payload}\n\n"


def format_init_cancelled(data: dict) -> str:
    """格式化初始化取消事件"""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: init:cancelled\ndata: {payload}\n\n"


def format_init_timeout(data: dict) -> str:
    """格式化初始化超时事件"""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: init:timeout\ndata: {payload}\n\n"
