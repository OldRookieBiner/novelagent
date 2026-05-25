# backend/app/api/agent.py
"""AI 搭档 Agent API 路由"""

import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.utils.auth import get_current_user
from app.utils.project import get_project_for_user
from app.models.user import User
from app.models.project import Project
from app.models.agent_conversation import AgentConversation, AgentMessage
from app.models.model_config import ModelConfig
from app.agents.agent_graph import create_agent_graph
from app.agents.prompts import AGENT_INSPIRATION_SYSTEM_PROMPT
from app.models.workflow_state import WorkflowState
from app.agents.state import STAGE_INSPIRATION
from app.agents.agent_context import build_project_context, get_context_window, estimate_tokens
from app.agents.tool_context import set_tool_context, reset_tool_context
from app.agents.sse_events import (
    format_agent_text,
    format_agent_tool_start,
    format_agent_tool_result,
    format_agent_done,
    format_ai_update,
    format_agent_review,
    format_agent_chapter_preview,
    format_error_message,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

BUSY_TIMEOUT_SECONDS = 300  # 5 分钟超时自动释放


class AgentChatRequest(BaseModel):
    """Agent 聊天请求"""
    message: str
    model_config_id: Optional[int] = None
    active_tab: Optional[str] = None
    active_menu_item: Optional[str] = None
    current_chapter_number: Optional[int] = None
    history: Optional[list[dict]] = None


def _acquire_busy_lock(db: Session, project_id: int, owner: str = "agent") -> bool:
    """尝试获取项目忙锁，返回是否成功"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return False
    now = datetime.utcnow()
    if project.is_busy:
        if project.busy_since and (now - project.busy_since).total_seconds() > BUSY_TIMEOUT_SECONDS:
            logger.warning(f"Project {project_id} busy lock expired, preempting (was held by {project.busy_by})")
        else:
            return False
    project.is_busy = True
    project.busy_since = now
    project.busy_by = owner
    db.commit()
    return True


def _release_busy_lock(project_id: int):
    """释放项目忙锁（使用独立 Session）"""
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project and project.busy_by == "agent":
            project.is_busy = False
            project.busy_since = None
            project.busy_by = None
            db.commit()
    except Exception as e:
        logger.error(f"Failed to release busy lock: {e}")
        db.rollback()
    finally:
        db.close()


def _get_or_create_conversation(db: Session, project_id: int) -> AgentConversation:
    """获取或创建项目会话（每个项目仅一个）"""
    conv = db.query(AgentConversation).filter(
        AgentConversation.project_id == project_id
    ).first()
    if not conv:
        conv = AgentConversation(project_id=project_id)
        db.add(conv)
        db.commit()
        db.refresh(conv)
    return conv


def _save_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
    segments: list | None = None,
    actions: list | None = None,
) -> AgentMessage:
    """保存一条消息（不 commit，由调用方管理事务）"""
    msg = AgentMessage(
        conversation_id=conversation_id,
        role=role,
        content=content or "",
        segments=segments or [],
        actions=actions or [],
    )
    db.add(msg)
    return msg


def _save_user_message(project_id: int, message: str):
    """保存用户消息（独立 Session，fire-and-forget）"""
    db = SessionLocal()
    try:
        conv = _get_or_create_conversation(db, project_id)
        _save_message(db, conv.id, "user", message)
        conv.message_count = (conv.message_count or 0) + 1
        if not conv.title:
            conv.title = message[:50]
        conv.updated_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save user message: {e}")
        db.rollback()
    finally:
        db.close()


def _save_assistant_message(project_id: int, content: str, segments: list, actions: list):
    """保存 assistant 消息（独立 Session，agent_done 后调用）"""
    db = SessionLocal()
    try:
        conv = _get_or_create_conversation(db, project_id)
        _save_message(db, conv.id, "assistant", content, segments, actions)
        conv.message_count = (conv.message_count or 0) + 1
        conv.updated_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save assistant message: {e}")
        db.rollback()
    finally:
        db.close()


def _build_truncated_history(
    history: list[dict],
    history_budget: int,
) -> list[dict]:
    """从最新往前截断 history，不超 history_budget token"""
    if not history or history_budget <= 0:
        return []

    kept: list[dict] = []
    used = 0
    for msg in reversed(history):
        msg_tokens = estimate_tokens(str(msg.get("content", "")))
        if used + msg_tokens > history_budget:
            break
        kept.insert(0, msg)
        used += msg_tokens
    return kept


async def stream_agent_events(
    graph,
    messages: list,
    project_id: int,
    accumulator: dict | None = None,
):
    """流式输出 Agent 事件

    accumulator 为 dict 时，函数会在其中累积 full_content/segments/actions，
    供调用方在流结束后保存到 DB。
    """
    write_tools = {
        "update_outline", "update_character", "create_character",
        "update_chapter_outline", "update_relations",
        "generate_chapter_content", "rewrite_chapter",
        "edit_paragraph", "insert_scene", "revise_section", "polish_prose",
        "update_inspiration_brief",
    }
    module_map = {
        "update_outline": "outline",
        "update_character": "characters",
        "create_character": "characters",
        "update_chapter_outline": "chapter_outlines",
        "update_relations": "relations",
        "generate_chapter_content": "writing",
        "rewrite_chapter": "writing",
        "edit_paragraph": "writing",
        "insert_scene": "writing",
        "revise_section": "writing",
        "polish_prose": "writing",
        "update_inspiration_brief": "inspiration",
    }

    try:
        async for event in graph.astream_events(
            {"messages": messages},
            config={"configurable": {"thread_id": f"agent-{project_id}"}},
            version="v2",
        ):
            kind = event.get("event", "")

            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and chunk.content and isinstance(chunk.content, str):
                    if accumulator is not None:
                        accumulator["full"] = accumulator.get("full", "") + chunk.content
                        accumulator.setdefault("segments", []).append(
                            {"type": "agent_text", "content": chunk.content}
                        )
                    yield format_agent_text(chunk.content)

            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                tool_input = event.get("data", {}).get("input", {})
                if accumulator is not None:
                    accumulator.setdefault("actions", []).append({
                        "tool": tool_name,
                        "status": "running",
                        "args": tool_input,
                    })
                yield format_agent_tool_start(tool_name, tool_input)

            elif kind == "on_tool_end":
                tool_name = event.get("name", "")
                tool_output = event.get("data", {}).get("output", {})

                if tool_name in write_tools:
                    module = module_map.get(tool_name, "unknown")
                    yield format_ai_update(module, f"{tool_name} 执行完成")

                output_data = json.dumps(tool_output, ensure_ascii=False) if isinstance(tool_output, dict) else str(tool_output)
                yield format_agent_tool_result(tool_name, {"output": output_data[:500]})

                # 标记 action 为 done
                if accumulator is not None:
                    actions = accumulator.get("actions", [])
                    for a in reversed(actions):
                        if a["tool"] == tool_name and a.get("status") == "running":
                            a["status"] = "done"
                            a["result"] = (
                                tool_output if isinstance(tool_output, dict)
                                else {"output": str(tool_output)}
                            )
                            break

                # 生成类 tool：发送章节预览事件
                if tool_name in ("generate_chapter_content", "rewrite_chapter") and isinstance(tool_output, dict):
                    if tool_output.get("success"):
                        yield format_agent_chapter_preview({
                            "chapter_number": tool_output.get("chapter_number"),
                            "title": tool_output.get("title", ""),
                            "word_count": tool_output.get("word_count", 0),
                            "preview": tool_output.get("preview", ""),
                            "action": "generated" if tool_name == "generate_chapter_content" else "rewritten",
                        })

                # 审核 tool：发送审核结果事件
                if tool_name == "review_chapter" and isinstance(tool_output, dict):
                    if tool_output.get("success") and tool_output.get("review"):
                        yield format_agent_review(tool_output["review"])

        yield format_agent_done()

    except Exception as e:
        logger.error(f"Agent stream error: {e}")
        yield format_error_message(str(e))


@router.get("/{project_id}/agent/conversation")
async def get_conversation(
    project_id: int,
    limit: int = 50,
    before_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前项目的 AI 搭档会话及消息"""
    get_project_for_user(project_id, current_user.id, db)

    conv = _get_or_create_conversation(db, project_id)

    query = db.query(AgentMessage).filter(
        AgentMessage.conversation_id == conv.id
    )
    if before_id is not None:
        query = query.filter(AgentMessage.id < before_id)
    query = query.order_by(AgentMessage.created_at.desc()).limit(limit)

    messages_raw = query.all()
    # 反转为升序
    messages_raw = list(reversed(messages_raw))

    messages = [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "segments": m.segments or [],
            "actions": m.actions or [],
            "timestamp": int(m.created_at.timestamp() * 1000) if m.created_at else 0,
        }
        for m in messages_raw
    ]

    return {
        "conversation_id": conv.id,
        "title": conv.title,
        "message_count": conv.message_count,
        "messages": messages,
    }


@router.delete("/{project_id}/agent/conversation")
async def clear_conversation(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """清空当前项目的 AI 搭档对话"""
    get_project_for_user(project_id, current_user.id, db)

    conv = db.query(AgentConversation).filter(
        AgentConversation.project_id == project_id
    ).first()
    if conv:
        db.query(AgentMessage).filter(
            AgentMessage.conversation_id == conv.id
        ).delete()
        conv.message_count = 0
        conv.title = ""
        conv.updated_at = datetime.utcnow()
        db.commit()

    return {"detail": "对话已清空"}


@router.post("/{project_id}/agent/chat")
async def agent_chat(
    project_id: int,
    req: AgentChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """与 AI 搭档对话（SSE 流式）"""
    project = get_project_for_user(project_id, current_user.id, db)

    # 并发控制：获取忙锁
    if not _acquire_busy_lock(db, project_id, "agent"):
        holder = project.busy_by or "未知"
        raise HTTPException(status_code=409, detail=f"项目正在被{holder}使用，请稍后再试")

    # 保存用户消息到 DB（fire-and-forget，失败不阻塞）
    _save_user_message(project_id, req.message)

    # 读取当前工作流阶段
    workflow_state = db.query(WorkflowState).filter(
        WorkflowState.project_id == project_id
    ).first()
    stage = workflow_state.stage if workflow_state else None

    # 获取模型 context_window
    model_config = None
    if req.model_config_id:
        model_config = db.query(ModelConfig).filter(
            ModelConfig.id == req.model_config_id
        ).first()
    context_window = get_context_window(model_config)

    # 构建项目上下文（原文注入 + token budget）
    context = build_project_context(
        project_id,
        current_chapter_number=req.current_chapter_number,
    )

    # 构建 system message（阶段感知）
    current_chapter_line = f"\n当前章节：第{req.current_chapter_number}章" if req.current_chapter_number else ""

    if stage == STAGE_INSPIRATION:
        # 灵感阶段：使用专门的灵感提示词
        inspiration_brief = context.get("inspiration_brief", "")
        system_content = AGENT_INSPIRATION_SYSTEM_PROMPT.format(
            inspiration_brief=inspiration_brief or "（尚未创建灵感简报，请引导用户描述创意）",
            active_tab=req.active_tab or "灵感",
        )
    else:
        # 其他阶段：使用通用提示词
        system_content = f"""你是一位专业的小说创作搭档。你可以帮助用户修改大纲、角色设定、章节大纲，也可以生成章节正文、审核章节、重写章节。

## 项目上下文

### 大纲
{json.dumps(context.get('outline', {}), ensure_ascii=False)}

### 角色
{json.dumps(context.get('characters', []), ensure_ascii=False)}

### 章节总览
{chr(10).join(context.get('all_chapters', []))}

### 当前章节正文
{json.dumps(context.get('current_chapter', {}), ensure_ascii=False)}

### 当前章节大纲
{json.dumps(context.get('current_outline', {}), ensure_ascii=False)}

## 行为准则

1. 生成章节后必须调用 review_chapter 审核质量
2. 审核不通过时应根据审核意见调用 rewrite_chapter 重写
3. 修改大纲/角色/章节后简要说明改了什么
4. 优先使用 revise_section 做局部修改，避免整章重写

用户当前查看：{req.active_tab or '未知'}{f' / {req.active_menu_item}' if req.active_menu_item else ''}{current_chapter_line}

请根据用户的需求，调用相应的工具来修改项目内容或生成内容。修改后简要说明你做了什么。"""

    # 计算 history budget 并截断
    system_used = estimate_tokens(system_content)
    history_budget = int(context_window * 0.7) - system_used
    truncated_history = _build_truncated_history(
        req.history or [],
        max(history_budget, 0),
    )

    # 拼装 messages
    messages = [{"role": "system", "content": system_content}]
    messages.extend(truncated_history)
    messages.append({"role": "user", "content": req.message})

    # 创建 Agent 图
    try:
        graph = create_agent_graph(
            model_config_id=req.model_config_id,
            user_id=current_user.id,
            stage=stage,
        )
    except ValueError as e:
        _release_busy_lock(project_id)
        raise HTTPException(status_code=400, detail=str(e))

    # 设置 tool 运行时上下文（contextvars）
    context_tokens = set_tool_context(
        model_config_id=req.model_config_id,
        user_id=current_user.id,
    )

    async def _stream_with_cleanup():
        acc: dict = {}
        try:
            async for event in stream_agent_events(graph, messages, project_id, accumulator=acc):
                yield event
            # 流完成后保存 assistant 消息
            _save_assistant_message(
                project_id,
                content=acc.get("full", ""),
                segments=acc.get("segments", []),
                actions=acc.get("actions", []),
            )
        finally:
            _release_busy_lock(project_id)
            reset_tool_context(context_tokens)

    return StreamingResponse(
        _stream_with_cleanup(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
