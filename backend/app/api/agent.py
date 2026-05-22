# backend/app/api/agent.py

"""AI 搭档 Agent API 路由"""

import json
import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.auth import get_current_user
from app.utils.project import get_project_for_user
from app.models.user import User
from app.models.project import Project
from app.agents.agent_graph import create_agent_graph, build_project_context
from app.agents.sse_events import (
    format_agent_text,
    format_agent_tool_start,
    format_agent_tool_result,
    format_agent_done,
    format_ai_update,
    format_error_message,
    format_heartbeat,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


router = APIRouter()


class AgentChatRequest(BaseModel):
    """Agent 聊天请求"""
    message: str
    model_config_id: Optional[int] = None
    active_tab: Optional[str] = None
    active_menu_item: Optional[str] = None
    # 多轮对话：前端传入历史消息（MVP 阶段由前端管理）
    history: Optional[list[dict]] = None


async def stream_agent_events(graph, messages: list, project_id: int):
    """流式输出 Agent 事件"""
    try:
        async for event in graph.astream_events(
            {"messages": messages},
            config={"configurable": {"thread_id": f"agent-{project_id}"}},
            version="v2",
        ):
            kind = event.get("event", "")

            # LLM 文本输出
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and chunk.content and isinstance(chunk.content, str):
                    yield format_agent_text(chunk.content)

            # Tool 调用开始
            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                tool_input = event.get("data", {}).get("input", {})
                yield format_agent_tool_start(tool_name, tool_input)

            # Tool 调用结束
            elif kind == "on_tool_end":
                tool_name = event.get("name", "")
                tool_output = event.get("data", {}).get("output", {})
                # 判断是否是写操作，发送 ai_update 通知
                write_tools = {"update_outline", "update_character", "create_character", "update_chapter_outline"}
                if tool_name in write_tools:
                    module_map = {
                        "update_outline": "outline",
                        "update_character": "characters",
                        "create_character": "characters",
                        "update_chapter_outline": "chapter_outlines",
                    }
                    module = module_map.get(tool_name, "unknown")
                    yield format_ai_update(module, f"{tool_name} 执行完成")
                # 序列化 tool output
                output_str = json.dumps(tool_output, ensure_ascii=False) if isinstance(tool_output, dict) else str(tool_output)
                yield format_agent_tool_result(tool_name, {"output": output_str[:500]})

        yield format_agent_done()

    except Exception as e:
        logger.error(f"Agent stream error: {e}")
        yield format_error_message(str(e))


@router.post("/{project_id}/agent/chat")
async def agent_chat(
    project_id: int,
    req: AgentChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """与 AI 搭档对话（SSE 流式）"""
    # 验证项目归属
    project = get_project_for_user(project_id, current_user.id, db)

    # 构建项目上下文
    context = build_project_context(project_id)

    # 构建 system message
    system_content = f"""你是一位专业的小说创作搭档。你可以帮助用户修改大纲、角色设定、章节大纲等。

当前项目上下文：
- 大纲：{json.dumps(context.get('outline', {}), ensure_ascii=False)}
- 角色：{json.dumps(context.get('characters', []), ensure_ascii=False)}
- 章节大纲：{json.dumps(context.get('chapter_outlines', {}), ensure_ascii=False)}
- 用户当前查看：{req.active_tab or '未知'}{f' / {req.active_menu_item}' if req.active_menu_item else ''}

请根据用户的需求，调用相应的工具来修改项目内容。修改后简要说明你做了什么。"""

    # 构建消息列表（包含历史）
    messages = [{"role": "system", "content": system_content}]
    if req.history:
        messages.extend(req.history)
    messages.append({"role": "user", "content": req.message})

    # 创建 Agent 图
    try:
        graph = create_agent_graph(
            model_config_id=req.model_config_id,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return StreamingResponse(
        stream_agent_events(graph, messages, project_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
