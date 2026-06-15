"""AI Creation Agent API routes

Phase-aware agent chat with cognitive tools and impact assessment.
"""

import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.utils.auth import get_current_user
from app.utils.project import get_project_for_user
from app.models.user import User
from app.models.project import Project
from app.models.agent_conversation import AgentConversation, AgentMessage
from app.models.model_config import ModelConfig
from app.agents.agent_graph import create_agent_graph
from app.agents.prompts import AGENT_SYSTEM_PROMPT
from app.models.workflow_state import WorkflowState
from app.agents.constants import Phase
from app.agents.agent_context import ProjectContextAssembler
from app.agents.token_budget import get_context_window, estimate_tokens
from app.agents.tool_context import set_tool_context, reset_tool_context, set_loaded_keys
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.sse_events import (
    format_agent_text,
    format_agent_tool_start,
    format_agent_tool_result,
    format_agent_done,
    format_agent_progress,
    format_impact_assessment,
    format_warning,
    format_error_message,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

BUSY_TIMEOUT_SECONDS = 300

# 会话数量软限制
MAX_CONVERSATIONS_PER_PROJECT = 20

PHASE_LABELS = {
    Phase.INCUBATION.value: "创意孵化",
    Phase.STRUCTURE.value: "结构设计",
    Phase.WRITING.value: "写作中",
    Phase.REVISION.value: "修订中",
}

# Tools that produce impact assessment reports
IMPACT_TOOLS = {"propose_setting_change", "propose_outline_adjustment", "propose_chapter_rewrite"}

# Tools that produce warnings
WARNING_TOOLS = {"foreshadowing_check", "style_analysis", "rhythm_analysis"}


class AgentChatRequest(BaseModel):
    message: str
    model_config_id: Optional[int] = None
    model_name: Optional[str] = None
    active_tab: Optional[str] = None
    active_menu_item: Optional[str] = None
    current_chapter_number: Optional[int] = None
    history: Optional[list[dict]] = None


class ImpactDecisionRequest(BaseModel):
    """Author decision on a proposed setting change."""
    change_id: int
    decision: str  # "proceed" | "adjust" | "abandon"
    adjusted_value: Optional[str] = None  # JSON, only when decision="adjust"


class ConversationRenameRequest(BaseModel):
    """重命名会话请求"""
    title: str = Field(min_length=1, max_length=50, description="会话标题")


def _acquire_busy_lock(db: Session, project_id: int, owner: str = "agent") -> bool:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return False
    now = datetime.utcnow()
    if project.is_busy:
        if project.busy_since and (now - project.busy_since).total_seconds() > BUSY_TIMEOUT_SECONDS:
            logger.warning(f"Project {project_id} busy lock expired, preempting")
        else:
            return False
    project.is_busy = True
    project.busy_since = now
    project.busy_by = owner
    db.commit()
    return True


def _release_busy_lock(project_id: int):
    db = SessionLocal()
    committed = False
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project and project.busy_by == "agent":
            project.is_busy = False
            project.busy_since = None
            project.busy_by = None
            db.commit()
            committed = True
    except Exception as e:
        logger.error(f"Failed to release busy lock: {e}")
    finally:
        if not committed:
            try:
                db.rollback()
            except Exception:
                pass
        try:
            db.close()
        except Exception:
            pass


def _get_active_conversation(db: Session, project_id: int) -> AgentConversation:
    """获取项目当前激活的会话，不存在则创建"""
    conv = db.query(AgentConversation).filter(
        AgentConversation.project_id == project_id,
        AgentConversation.is_active == True,
    ).first()
    if not conv:
        conv = AgentConversation(project_id=project_id, is_active=True)
        db.add(conv)
        db.commit()
        db.refresh(conv)
    return conv


def _save_user_message(project_id: int, message: str):
    db = SessionLocal()
    committed = False
    try:
        conv = _get_active_conversation(db, project_id)
        msg = AgentMessage(
            conversation_id=conv.id,
            role="user",
            content=message or "",
        )
        db.add(msg)
        conv.message_count = (conv.message_count or 0) + 1
        if not conv.title:
            conv.title = message[:20]
        conv.updated_at = datetime.utcnow()
        db.commit()
        committed = True
    except Exception as e:
        logger.error(f"Failed to save user message: {e}")
    finally:
        if not committed:
            try:
                db.rollback()
            except Exception:
                pass
        try:
            db.close()
        except Exception:
            pass


def _save_assistant_message(project_id: int, content: str, segments: list, actions: list):
    db = SessionLocal()
    committed = False
    try:
        conv = _get_active_conversation(db, project_id)
        msg = AgentMessage(
            conversation_id=conv.id,
            role="assistant",
            content=content or "",
            segments=segments or [],
            actions=actions or [],
        )
        db.add(msg)
        conv.message_count = (conv.message_count or 0) + 1
        conv.updated_at = datetime.utcnow()
        db.commit()
        committed = True
    except Exception as e:
        logger.error(f"Failed to save assistant message: {e}")
    finally:
        if not committed:
            try:
                db.rollback()
            except Exception:
                pass
        try:
            db.close()
        except Exception:
            pass


def _build_truncated_history(history: list[dict], history_budget: int) -> list[dict]:
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


def _serialize_conversation(conv: AgentConversation) -> dict:
    """序列化会话为 API 响应 dict"""
    return {
        "id": conv.id,
        "title": conv.title,
        "message_count": conv.message_count,
        "is_active": conv.is_active,
        "created_at": conv.created_at.isoformat() + "Z" if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() + "Z" if conv.updated_at else None,
    }


async def stream_agent_events(
    graph,
    messages: list,
    project_id: int,
    conversation_id: int,
    accumulator: dict | None = None,
):
    """Stream Agent events with cognitive tool awareness."""
    try:
        async for event in graph.astream_events(
            {"messages": messages},
            config={"configurable": {"thread_id": f"agent-{project_id}-{conversation_id}"}},
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
                # 进度报告工具：不记录到 accumulator actions，不发 tool_start，只发 progress
                if tool_name == "report_progress":
                    if accumulator is not None:
                        accumulator.setdefault("segments", []).append({
                            "type": "progress",
                            "content": str(tool_input.get("message", "")),
                            "data": {"percent": tool_input.get("percent", 0)},
                        })
                    yield format_agent_progress(tool_name, tool_input)
                else:
                    if accumulator is not None:
                        accumulator.setdefault("actions", []).append({
                            "tool": tool_name,
                            "status": "running",
                            "args": tool_input,
                        })
                        accumulator.setdefault("segments", []).append({
                            "type": "tool_start",
                            "content": tool_name,
                            "data": {"tool": tool_name},
                        })
                    yield format_agent_tool_start(tool_name, tool_input)

            elif kind == "on_tool_end":
                tool_name = event.get("name", "")
                tool_output = event.get("data", {}).get("output", {})

                # 进度报告工具：只发 progress 事件，跳过 tool_result / actions
                if tool_name == "report_progress" and isinstance(tool_output, dict):
                    yield format_agent_progress(tool_name, tool_output)
                    if accumulator is not None:
                        accumulator.setdefault("segments", []).append({
                            "type": "progress",
                            "content": str(tool_output.get("progress_message", "")),
                            "data": {"percent": tool_output.get("progress_percent", 0)},
                        })
                else:
                    output_str = json.dumps(tool_output, ensure_ascii=False) if isinstance(tool_output, dict) else str(tool_output)
                    yield format_agent_tool_result(tool_name, {"output": output_str[:800]})

                    if accumulator is not None:
                        actions = accumulator.get("actions", [])
                        for a in reversed(actions):
                            if a["tool"] == tool_name and a.get("status") == "running":
                                a["status"] = "done"
                                a["result"] = tool_output if isinstance(tool_output, dict) else {"output": str(tool_output)}
                                break
                        accumulator.setdefault("segments", []).append({
                            "type": "tool_result",
                            "content": tool_name,
                            "data": {"tool": tool_name},
                        })

                    # Impact assessment tools: emit dedicated SSE event
                    if tool_name in IMPACT_TOOLS and isinstance(tool_output, dict):
                        if tool_output.get("change_id"):
                            yield format_impact_assessment(tool_output)

                    # Warning-producing tools: emit warning if flagged
                    if tool_name in WARNING_TOOLS and isinstance(tool_output, dict):
                        if tool_output.get("warning"):
                            yield format_warning(tool_name, {"message": tool_output["warning"]})

        yield format_agent_done()

    except Exception as e:
        logger.error(f"Agent stream error: {e}")
        yield format_error_message(str(e))


# ─── 会话 CRUD 端点 ───


@router.get("/{project_id}/agent/conversations")
async def list_conversations(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出项目所有会话"""
    get_project_for_user(project_id, current_user.id, db)
    convs = db.query(AgentConversation).filter(
        AgentConversation.project_id == project_id
    ).order_by(AgentConversation.updated_at.desc()).all()
    return [_serialize_conversation(c) for c in convs]


@router.post("/{project_id}/agent/conversations")
async def create_conversation(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """新建会话"""
    project = get_project_for_user(project_id, current_user.id, db)

    if not _acquire_busy_lock(db, project_id, "agent"):
        holder = project.busy_by or "未知"
        raise HTTPException(status_code=409, detail=f"项目正在被{holder}使用，请稍后再试")

    try:
        # 软限制检查
        count = db.query(AgentConversation).filter(
            AgentConversation.project_id == project_id
        ).count()
        if count >= MAX_CONVERSATIONS_PER_PROJECT:
            raise HTTPException(
                status_code=400,
                detail=f"会话数量已达上限（{MAX_CONVERSATIONS_PER_PROJECT}条），请删除旧会话后再创建",
            )

        # 将当前活跃会话置为非活跃
        db.query(AgentConversation).filter(
            AgentConversation.project_id == project_id,
            AgentConversation.is_active == True,
        ).update({"is_active": False})

        # 创建新会话
        conv = AgentConversation(project_id=project_id, is_active=True, title="")
        db.add(conv)
        db.commit()
        db.refresh(conv)

        return _serialize_conversation(conv)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _release_busy_lock(project_id)


@router.put("/{project_id}/agent/conversations/{conversation_id}")
async def rename_conversation(
    project_id: int,
    conversation_id: int,
    req: ConversationRenameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重命名会话"""
    get_project_for_user(project_id, current_user.id, db)
    conv = db.query(AgentConversation).filter(
        AgentConversation.id == conversation_id,
        AgentConversation.project_id == project_id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    conv.title = req.title
    conv.updated_at = datetime.utcnow()
    db.commit()
    return _serialize_conversation(conv)


@router.post("/{project_id}/agent/conversations/{conversation_id}/activate")
async def activate_conversation(
    project_id: int,
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """切换到指定会话"""
    project = get_project_for_user(project_id, current_user.id, db)

    if not _acquire_busy_lock(db, project_id, "agent"):
        holder = project.busy_by or "未知"
        raise HTTPException(status_code=409, detail=f"项目正在被{holder}使用，请稍后再试")

    try:
        target = db.query(AgentConversation).filter(
            AgentConversation.id == conversation_id,
            AgentConversation.project_id == project_id,
        ).first()
        if not target:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 同一事务中：先取消当前活跃，再激活目标
        db.query(AgentConversation).filter(
            AgentConversation.project_id == project_id,
            AgentConversation.is_active == True,
        ).update({"is_active": False})
        target.is_active = True
        db.commit()

        return _serialize_conversation(target)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _release_busy_lock(project_id)


@router.delete("/{project_id}/agent/conversations/{conversation_id}")
async def delete_conversation(
    project_id: int,
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除指定会话"""
    project = get_project_for_user(project_id, current_user.id, db)

    if not _acquire_busy_lock(db, project_id, "agent"):
        holder = project.busy_by or "未知"
        raise HTTPException(status_code=409, detail=f"项目正在被{holder}使用，请稍后再试")

    try:
        conv = db.query(AgentConversation).filter(
            AgentConversation.id == conversation_id,
            AgentConversation.project_id == project_id,
        ).first()
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在")
        if conv.is_active:
            raise HTTPException(status_code=400, detail="无法删除当前激活的会话")

        # 删除 DB 记录（cascade 会删除关联消息）
        db.delete(conv)
        db.commit()

        return {"detail": "会话已删除"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _release_busy_lock(project_id)


# ─── 会话消息端点 ───


@router.get("/{project_id}/agent/conversation")
async def get_conversation(
    project_id: int,
    conversation_id: Optional[int] = None,
    limit: int = 50,
    before_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取指定会话或当前激活会话的消息"""
    get_project_for_user(project_id, current_user.id, db)

    if conversation_id:
        conv = db.query(AgentConversation).filter(
            AgentConversation.id == conversation_id,
            AgentConversation.project_id == project_id,
        ).first()
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在")
    else:
        conv = _get_active_conversation(db, project_id)

    query = db.query(AgentMessage).filter(
        AgentMessage.conversation_id == conv.id
    )
    if before_id is not None:
        query = query.filter(AgentMessage.id < before_id)
    query = query.order_by(AgentMessage.created_at.desc()).limit(limit)

    messages_raw = list(reversed(query.all()))
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
    """清空当前激活会话的消息（保留会话）"""
    get_project_for_user(project_id, current_user.id, db)
    conv = _get_active_conversation(db, project_id)
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
    """Chat with the AI creation agent (SSE streaming)."""
    project = get_project_for_user(project_id, current_user.id, db)

    if not _acquire_busy_lock(db, project_id, "agent"):
        holder = project.busy_by or "未知"
        raise HTTPException(status_code=409, detail=f"项目正在被{holder}使用，请稍后再试")

    # 获取当前激活会话（在 busy lock 保护下）
    conv = _get_active_conversation(db, project_id)

    _save_user_message(project_id, req.message)

    # Read current workflow phase
    workflow_state = db.query(WorkflowState).filter(
        WorkflowState.project_id == project_id
    ).first()
    phase = workflow_state.stage if workflow_state else Phase.INCUBATION.value

    # Get model context window（优先使用子模型的 context_window）
    model_config = None
    if req.model_config_id:
        model_config = db.query(ModelConfig).filter(
            ModelConfig.id == req.model_config_id
        ).first()
    context_window = get_context_window(model_config, req.model_name)

    # Build phase-aware project context via ProjectContextAssembler
    assembler = ProjectContextAssembler(project_id)
    context_result = assembler.build(
        context_window=context_window,
        phase=phase,
        current_chapter_number=req.current_chapter_number,
    )

    # 分离 project_data 和 previous_text
    project_data_block = json.dumps(context_result["project_data"], ensure_ascii=False, default=str)
    previous_text = context_result.get("previous_text", "")

    # Build prerequisites warning text
    prereq = context_result.get("project_data", {}).get("prerequisites", {})
    if prereq.get("blocked"):
        blocked_items = "\n".join([f"- {item['message']}" for item in prereq["blocked"]])
        context_prerequisites_warning = f"""⚠️ 当前无法生成正文，存在以下阻断问题：

{blocked_items}

请先在知识库中补全以上内容。"""
    elif prereq.get("warnings"):
        warning_items = "\n".join([f"- {item['message']}" for item in prereq["warnings"]])
        context_prerequisites_warning = f"""📝 当前存在以下次要项缺失（不影响生成）：

{warning_items}

你可以在写作时留意这些方面。"""
    else:
        context_prerequisites_warning = ""

    # previous_text 独立段落
    previous_section = ""
    if previous_text:
        previous_section = f"\n\n## 前文上下文\n\n{previous_text}"

    # Build system message
    phase_label = PHASE_LABELS.get(phase, "未知阶段")
    system_content = AGENT_SYSTEM_PROMPT.format(
        phase_label=phase_label,
        project_name=project.name,
        context_block=project_data_block,
        context_prerequisites_warning=context_prerequisites_warning,
    ) + previous_section

    # Calculate history budget and truncate
    system_used = estimate_tokens(system_content)
    history_budget = int(context_window * 0.7) - system_used
    if history_budget <= 0:
        # 系统消息占用过多 —— 压缩上下文为精简版
        slim_data = {
            k: v for k, v in context_result.get("project_data", {}).items()
            if k in ("outline", "style_constraints", "current_plot_block",
                      "pending_foreshadowings", "overdue_foreshadowings")
        }
        slim_block = json.dumps(slim_data, ensure_ascii=False, default=str)
        system_content = AGENT_SYSTEM_PROMPT.format(
            phase_label=phase_label,
            project_name=project.name,
            context_block=slim_block,
            context_prerequisites_warning=context_prerequisites_warning,
        ) + previous_section
        system_used = estimate_tokens(system_content)
        # 至少保留当前消息 4 倍的预算给历史
        min_history = estimate_tokens(req.message) * 4
        history_budget = max(min_history, int(context_window * 0.3) - system_used)
    truncated_history = _build_truncated_history(
        req.history or [],
        max(history_budget, 0),
    )

    messages = [{"role": "system", "content": system_content}]
    messages.extend(truncated_history)
    messages.append({"role": "user", "content": req.message})

    # 计算输出 token 上限：context_window × 80%，留 20% 给输入+估算误差
    max_output_tokens = int(context_window * 0.8)

    # Create agent graph with phase-aware tools
    try:
        graph = create_agent_graph(
            model_config_id=req.model_config_id,
            user_id=current_user.id,
            phase=phase,
            model_name=req.model_name,
            max_output_tokens=max_output_tokens,
            project_id=project_id,
        )
    except ValueError as e:
        _release_busy_lock(project_id)
        raise HTTPException(status_code=400, detail=str(e))

    # Set tool context (including project_id for cognitive tools)
    context_tokens = set_tool_context(
        model_config_id=req.model_config_id,
        user_id=current_user.id,
        project_id=project_id,
    )

    # 设置预加载数据声明
    loaded_keys = context_result.get("loaded_keys", [])
    if loaded_keys:
        set_loaded_keys(loaded_keys)

    async def _stream_with_cleanup():
        acc: dict = {}
        try:
            async for event in stream_agent_events(
                graph, messages, project_id, conv.id, accumulator=acc
            ):
                yield event
        finally:
            # 无论正常完成还是中断，都尝试保存已有内容
            if acc.get("full") or acc.get("segments"):
                try:
                    _save_assistant_message(
                        project_id,
                        content=acc.get("full", ""),
                        segments=acc.get("segments", []),
                        actions=acc.get("actions", []),
                    )
                except Exception as e:
                    logger.error(f"Failed to save assistant message: {e}")
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


@router.post("/{project_id}/agent/impact-decision")
async def impact_decision(
    project_id: int,
    req: ImpactDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Author decides on a proposed setting change.

    Three options:
    - proceed: Apply the change as proposed
    - adjust: Apply with adjusted value (requires adjusted_value)
    - abandon: Discard the proposal
    """
    get_project_for_user(project_id, current_user.id, db)
    kb = KnowledgeBaseService(project_id)

    change = kb.changes.get(req.change_id)
    if not change:
        raise HTTPException(status_code=404, detail="变更提案不存在")
    if change.get("status") != "proposed":
        raise HTTPException(status_code=400, detail=f"提案状态为 {change.get('status')}，无法决策")

    if req.decision == "abandon":
        kb.changes.update(req.change_id, {
            "status": "abandoned",
            "author_decision": "abandon",
        })
        return {"change_id": req.change_id, "status": "abandoned", "message": "已放弃修改"}

    elif req.decision == "proceed":
        _apply_change(kb, change)
        kb.changes.update(req.change_id, {
            "status": "applied",
            "author_decision": "proceed",
        })
        return {"change_id": req.change_id, "status": "applied", "message": "已按原方案修改"}

    elif req.decision == "adjust":
        if not req.adjusted_value:
            raise HTTPException(status_code=400, detail="adjust 决策需要提供 adjusted_value")
        try:
            adjusted = json.loads(req.adjusted_value)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="adjusted_value 不是有效的 JSON")

        # Apply the adjusted value instead
        change["new_value"] = adjusted
        _apply_change(kb, change)
        kb.changes.update(req.change_id, {
            "status": "applied",
            "author_decision": "adjust",
            "new_value": adjusted,
        })
        return {"change_id": req.change_id, "status": "applied", "message": "已按调整方案修改"}

    else:
        raise HTTPException(status_code=400, detail=f"无效决策: {req.decision}")


def _apply_change(kb: KnowledgeBaseService, change):
    """Apply a proposed change to the actual knowledge base object.

    Delegates to the appropriate Store update method
    based on target_type. change is a dict (Store 返回值).
    """
    target_type = change["target_type"]
    target_id = change["target_id"]
    new_value = change["new_value"] if not isinstance(change.get("new_value"), str) else json.loads(change["new_value"])

    if target_type == "world_setting":
        kb.world_setting.update_by_id(target_id, new_value)
    elif target_type == "character":
        kb.characters.update_character(target_id, new_value)
    elif target_type == "style":
        kb.styles.update_constraints_by_id(target_id, new_value)
    elif target_type == "foreshadowing":
        kb.foreshadowings.update(target_id, new_value)
    elif target_type == "outline_adjustment":
        # Outline adjustments are structural; mark as applied but don't auto-modify
        pass
    elif target_type == "chapter_rewrite":
        # Chapter rewrites are handled by the main writing loop
        pass
