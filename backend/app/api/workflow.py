"""Workflow API routes for creation agent (LangGraph integration)

适配创作智能体 v2 的工作流 API：
- 使用 Phase enum 替代旧的 STAGE_* 常量
- NovelState v2 只存 ID 引用和流程控制，不缓存 DB 数据
- 确认/恢复通过 LangGraph checkpointer 机制
"""

import logging
from typing import Optional, Any, AsyncIterator
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.outline import Outline
from app.models.checkpoint import WorkflowCheckpoint
from app.models.workflow_state import WorkflowState
from app.utils.auth import get_current_user
from app.utils.project import get_project_for_user
from app.agents.sse_events import (
    format_node_start,
    format_node_done,
    format_chunk,
    format_done,
    format_waiting,
    format_sse_error,
)
from app.agents.graph import create_novel_graph_with_checkpointer
from app.agents.state import NovelState, Phase, ConfirmationType

router = APIRouter()

# 创作阶段白名单（Phase enum 值）
VALID_PHASES = [p.value for p in Phase]


async def stream_workflow_events(
    graph,
    config: dict,
    initial_state: dict = None,
) -> AsyncIterator[str]:
    """共享的 LangGraph 工作流 SSE 事件流生成器

    将 LangGraph astream_events 事件转换为 SSE 字符串。

    - initial_state 不为 None → 首次执行
    - initial_state 为 None → 恢复执行

    处理的事件类型：
    - on_chain_start → node_start
    - on_chat_model_stream → chunk（LLM 流式内容）
    - on_chain_end → node_done（或 waiting 如果等待确认）
    """
    try:
        if initial_state is not None:
            yield format_node_start("workflow", "Starting creation agent")
        else:
            yield format_node_start("workflow_resume", "Resuming creation agent")

        async for event in graph.astream_events(initial_state, config, version="v2"):
            event_type = event.get("event")
            event_name = event.get("name", "")
            event_data = event.get("data", {})

            if event_type == "on_chain_start":
                yield format_node_start(event_name)

            elif event_type == "on_chain_end":
                output = event_data.get("output", {})
                if isinstance(output, dict):
                    if output.get("waiting_for_confirmation"):
                        yield format_waiting(
                            output.get("confirmation_type", ""), node=event_name
                        )
                        yield format_done("Agent paused for confirmation")
                        return
                    else:
                        yield format_node_done(event_name, output)
                # output 不是 dict（如 END 字符串）→ 工作流完成

            elif event_type == "on_chat_model_stream":
                chunk = event_data.get("chunk")
                if chunk:
                    content = getattr(chunk, "content", str(chunk))
                    if content:
                        yield format_chunk(content)

        yield format_done("Creation agent completed")

    except Exception as e:
        logger.error(f"stream_workflow_events error: {e}", exc_info=True)
        yield format_sse_error(str(e))


# ========== Request/Response Schemas ==========

class WorkflowRunRequest(BaseModel):
    """工作流运行请求"""
    llm_config_id: Optional[int] = None
    llm_model_name: Optional[str] = None
    review_llm_config_id: Optional[int] = None
    # 创意对话的首条用户消息（可选）
    user_message: Optional[str] = None


class WorkflowConfirmRequest(BaseModel):
    """工作流确认请求"""
    # 用户确认后可能携带的数据
    story_seed: Optional[str] = None
    user_message: Optional[str] = None  # 对话式确认的回复


class WorkflowReplanRequest(BaseModel):
    """重新规划请求"""
    llm_config_id: Optional[int] = None
    llm_model_name: Optional[str] = None


class WorkflowStateResponse(BaseModel):
    """工作流状态响应"""
    project_id: int
    has_checkpoint: bool
    phase: Optional[str] = None
    waiting_for_confirmation: bool = False
    confirmation_type: Optional[str] = None
    current_chapter: int = 0
    chapter_count: int = 0
    current_state: Optional[dict] = None


class WorkflowCleanupResponse(BaseModel):
    """工作流清理响应"""
    message: str
    deleted: int


class UpdatePhaseRequest(BaseModel):
    """更新工作流阶段请求"""
    phase: str

    @field_validator('phase')
    @classmethod
    def validate_phase(cls, v):
        if v not in VALID_PHASES:
            raise ValueError(f'Invalid phase: {v}. Must be one of {VALID_PHASES}')
        return v


# ========== Helper Functions ==========

def build_initial_state(
    project: Project,
    outline: Optional[Outline],
    workflow_state: WorkflowState,
    llm_config_id: Optional[int] = None,
    llm_model_name: Optional[str] = None,
    user_message: Optional[str] = None,
    db: Optional["Session"] = None,
) -> NovelState:
    """构建创作智能体 v2 的初始 NovelState

    NovelState v2 只存 ID 引用和流程控制状态。
    业务数据通过 KnowledgeBaseService 实时读取。
    """
    state: NovelState = {
        # 基本信息
        "project_id": project.id,

        # 阶段控制
        "phase": Phase.INCUBATION.value,

        # 创意孵化
        "story_seed": None,
        "inspiration_messages": [],

        # 知识库 ID 引用
        "outline_id": outline.id if outline else None,
        "world_setting_id": None,
        "style_constraints_id": None,

        # 结构
        "current_plot_block_index": 0,
        "chapter_count": outline.chapter_count_suggested if outline else 0,

        # 写作
        "current_chapter": 1,
        "written_chapters": [],

        # 写作工作记忆
        "chapter_plan": None,
        "assembled_context": None,

        # 写后自检
        "post_write_summary": None,
        "last_review_chapter": 0,

        # 卷管理（Phase 4）
        "current_volume": 1,
        "revision_context": None,

        # 工作流控制
        "waiting_for_confirmation": False,
        "confirmation_type": None,

        # LLM 服务
        "llm_config_id": llm_config_id or workflow_state.llm_config_id,
        "review_llm_config_id": None,
        "llm_model_name": llm_model_name or workflow_state.llm_model_name,

        # Prompt + 上下文窗口
        "_prompts": {},
        "_context_window": 4096,
    }

    # 如果有用户消息，加入创意对话
    if user_message:
        state["inspiration_messages"] = [{"role": "user", "content": user_message}]

    # 预加载 prompts
    if db is not None:
        try:
            state["_prompts"] = _build_prompts_dict(db)
        except Exception as e:
            logger.warning(f"Failed to load custom prompts, using defaults: {e}")
            from app.agents.prompts import DEFAULT_PROMPTS
            state["_prompts"] = DEFAULT_PROMPTS

    # 预加载上下文窗口大小
    if db is not None:
        try:
            from app.agents.token_budget import get_context_window
            from app.models.model_config import ModelConfig

            model_name = state.get("llm_model_name", "")
            model_config_id = state.get("llm_config_id")
            if model_config_id:
                config = db.query(ModelConfig).filter(ModelConfig.id == model_config_id).first()
                state["_context_window"] = get_context_window(model_name, model_config=config)
            else:
                state["_context_window"] = get_context_window(model_name)
        except Exception as e:
            logger.warning(f"Failed to load context window: {e}")
            from app.agents.constants import DEFAULT_CONTEXT_WINDOW
            state["_context_window"] = DEFAULT_CONTEXT_WINDOW

    return state


def _build_prompts_dict(db: Session) -> dict[str, str | dict]:
    """构建预加载的 prompts 字典（所有节点共享）

    创作智能体 v2 使用 15 个核心 prompt 模板。
    """
    from app.agents.prompts import DEFAULT_PROMPTS
    try:
        from app.services.prompt_loader import get_system_prompt

        return {
            "inspiration_dialogue": get_system_prompt(db, "inspiration_dialogue"),
            "story_seed": get_system_prompt(db, "story_seed"),
            "outline_generation": get_system_prompt(db, "outline_generation"),
            "world_setting": get_system_prompt(db, "world_setting"),
            "character_generation": get_system_prompt(db, "character_generation"),
            "relation_generation": get_system_prompt(db, "relation_generation"),
            "style_setup": get_system_prompt(db, "style_setup"),
            "foreshadowing_plan": get_system_prompt(db, "foreshadowing_plan"),
            "question_chain": get_system_prompt(db, "question_chain"),
            "plot_blocks": get_system_prompt(db, "plot_blocks"),
            "subplot_network": get_system_prompt(db, "subplot_network"),
            "rhythm_curve": get_system_prompt(db, "rhythm_curve"),
            "chapter_planning": get_system_prompt(db, "chapter_planning"),
            "chapter_writing": get_system_prompt(db, "chapter_writing"),
            "deep_review": get_system_prompt(db, "deep_review"),
        }
    except Exception:
        return DEFAULT_PROMPTS


def get_latest_checkpoint(project_id: int, thread_id: str = "default", db: Session = None) -> Optional[dict]:
    """获取项目的最新检查点状态"""
    if db is None:
        raise ValueError("db session is required")

    record = db.query(WorkflowCheckpoint).filter(
        WorkflowCheckpoint.project_id == project_id,
        WorkflowCheckpoint.thread_id == thread_id
    ).order_by(WorkflowCheckpoint.updated_at.desc()).first()

    if record:
        return record.checkpoint.get("channel_values", {})
    return None


def delete_project_checkpoints(project_id: int, thread_id: str = "default", db: Session = None) -> int:
    """删除项目的所有检查点"""
    if db is None:
        raise ValueError("db session is required")

    count = db.query(WorkflowCheckpoint).filter(
        WorkflowCheckpoint.project_id == project_id,
        WorkflowCheckpoint.thread_id == thread_id
    ).delete()
    db.commit()
    return count


# ========== API Endpoints ==========

@router.post("/{project_id}/workflow/run")
async def run_workflow(
    project_id: int,
    request: WorkflowRunRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """启动创作智能体工作流（SSE 流式）

    首次启动时从创意孵化阶段开始，用户通过对话形式
    探索和拓展小说创意。
    """
    project = get_project_for_user(project_id, current_user.id, db)

    outline = db.query(Outline).filter(
        Outline.project_id == project_id
    ).first()

    # 获取或创建 WorkflowState
    workflow_state = db.query(WorkflowState).filter(
        WorkflowState.project_id == project_id,
        WorkflowState.thread_id == "main"
    ).first()

    if not workflow_state:
        workflow_state = WorkflowState(project_id=project_id)
        db.add(workflow_state)
        db.commit()
        db.refresh(workflow_state)

    # 获取 LLM 配置
    llm_config_id = None
    llm_model_name = None
    user_message = None
    if request:
        llm_config_id = request.llm_config_id
        llm_model_name = request.llm_model_name
        user_message = request.user_message

    if llm_config_id or llm_model_name:
        workflow_state.llm_config_id = llm_config_id
        workflow_state.llm_model_name = llm_model_name
        db.commit()

    initial_state = build_initial_state(
        project, outline, workflow_state,
        llm_config_id, llm_model_name,
        user_message=user_message, db=db,
    )

    if request and request.review_llm_config_id:
        initial_state["review_llm_config_id"] = request.review_llm_config_id

    graph = create_novel_graph_with_checkpointer(project_id, "default")
    config = {"configurable": {"thread_id": "default"}}

    def stream_generator():
        return stream_workflow_events(graph, config, initial_state)

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{project_id}/workflow/confirm")
async def confirm_workflow(
    project_id: int,
    request: WorkflowConfirmRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """确认当前节点并继续工作流

    用户确认后，更新检查点中的状态并恢复执行。
    支持携带用户消息（用于创意对话的多轮交互）。
    """
    project = get_project_for_user(project_id, current_user.id, db)
    checkpoint_state = get_latest_checkpoint(project_id, "default", db)

    if not checkpoint_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active workflow to confirm",
        )

    if not checkpoint_state.get("waiting_for_confirmation"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow is not waiting for confirmation",
        )

    # 清除等待确认标志
    checkpoint_state["waiting_for_confirmation"] = False

    # 如果是创意对话确认，追加用户消息
    confirmation_type = checkpoint_state.get("confirmation_type")
    if request and request.user_message:
        messages = checkpoint_state.get("inspiration_messages", [])
        messages.append({"role": "user", "content": request.user_message})
        checkpoint_state["inspiration_messages"] = messages

    # 如果是故事种子确认，保存用户修改的种子
    if request and request.story_seed:
        checkpoint_state["story_seed"] = request.story_seed

    # 清除确认类型
    checkpoint_state["confirmation_type"] = None

    # 同步更新检查点到 DB
    record = db.query(WorkflowCheckpoint).filter(
        WorkflowCheckpoint.project_id == project_id,
        WorkflowCheckpoint.thread_id == "default"
    ).order_by(WorkflowCheckpoint.updated_at.desc()).first()

    if record:
        checkpoint_data = record.checkpoint.copy()
        checkpoint_data["channel_values"] = checkpoint_state
        record.checkpoint = checkpoint_data
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(record, "checkpoint")

    # 同步更新 WorkflowState
    workflow_state = db.query(WorkflowState).filter(
        WorkflowState.project_id == project_id,
        WorkflowState.thread_id == "main"
    ).first()

    if workflow_state:
        workflow_state.waiting_for_confirmation = False
        workflow_state.confirmation_type = None
        # 同步阶段
        phase_value = checkpoint_state.get("phase", "incubation")
        workflow_state.stage = phase_value

    db.commit()

    # 通过 LangGraph 恢复执行
    graph = create_novel_graph_with_checkpointer(project_id, "default")
    config = {"configurable": {"thread_id": "default"}}

    def stream_generator():
        return stream_workflow_events(graph, config, None)

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{project_id}/workflow/state", response_model=WorkflowStateResponse)
async def get_workflow_state(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前工作流状态"""
    project = get_project_for_user(project_id, current_user.id, db)
    checkpoint_state = get_latest_checkpoint(project_id, "default", db)

    if checkpoint_state:
        return WorkflowStateResponse(
            project_id=project_id,
            has_checkpoint=True,
            phase=checkpoint_state.get("phase"),
            waiting_for_confirmation=checkpoint_state.get("waiting_for_confirmation", False),
            confirmation_type=checkpoint_state.get("confirmation_type"),
            current_chapter=checkpoint_state.get("current_chapter", 0),
            chapter_count=checkpoint_state.get("chapter_count", 0),
            current_state=checkpoint_state,
        )
    else:
        workflow_state = db.query(WorkflowState).filter(
            WorkflowState.project_id == project_id,
            WorkflowState.thread_id == "main"
        ).first()

        if workflow_state:
            return WorkflowStateResponse(
                project_id=project_id,
                has_checkpoint=False,
                phase=workflow_state.stage,
                waiting_for_confirmation=workflow_state.waiting_for_confirmation,
                confirmation_type=workflow_state.confirmation_type,
                current_chapter=workflow_state.current_chapter,
                chapter_count=0,
                current_state=None,
            )
        else:
            return WorkflowStateResponse(
                project_id=project_id,
                has_checkpoint=False,
                phase=Phase.INCUBATION.value,
                waiting_for_confirmation=False,
                confirmation_type=None,
                current_chapter=0,
                chapter_count=0,
                current_state=None,
            )


@router.post("/{project_id}/workflow/cancel")
async def cancel_workflow(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """取消当前工作流（删除所有检查点）"""
    project = get_project_for_user(project_id, current_user.id, db)
    deleted_count = delete_project_checkpoints(project_id, "default", db)

    return {
        "message": "Workflow cancelled",
        "deleted_checkpoints": deleted_count,
    }


@router.post("/{project_id}/workflow/cleanup", response_model=WorkflowCleanupResponse)
async def cleanup_workflow(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """清理工作流检查点（不删业务数据）"""
    get_project_for_user(project_id, current_user.id, db)
    deleted_count = delete_project_checkpoints(project_id, "default", db)

    return WorkflowCleanupResponse(
        message="Checkpoints cleaned up",
        deleted=deleted_count,
    )


@router.post("/{project_id}/workflow/replan")
async def replan_workflow(
    project_id: int,
    request: WorkflowReplanRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重新启动创作流程

    清理检查点、知识库追踪数据，从创意孵化阶段重新开始。
    保留大纲基础信息。
    """
    project = get_project_for_user(project_id, current_user.id, db)

    outline = db.query(Outline).filter(
        Outline.project_id == project_id
    ).first()

    # 1. 清理检查点
    delete_project_checkpoints(project_id, "default", db)

    # 2. 重置 WorkflowState
    workflow_state = db.query(WorkflowState).filter(
        WorkflowState.project_id == project_id,
        WorkflowState.thread_id == "main"
    ).first()

    if workflow_state:
        workflow_state.stage = Phase.INCUBATION.value
        workflow_state.waiting_for_confirmation = False
        workflow_state.confirmation_type = None
        workflow_state.current_chapter = 1

    # 3. 清理知识库追踪数据（保留大纲）
    from app.models.world_setting import WorldSetting
    from app.models.style_constraints import StyleConstraints
    from app.models.plot_structure import PlotBlock, PlotQuestion, Subplot
    from app.models.foreshadowing import Foreshadowing
    from app.models.timeline import TimelineEntry
    from app.models.style_snapshot import StyleSnapshot
    from app.models.scene_entry import SceneEntry
    from app.models.character import Character, Relation
    from app.models.outline import ChapterOutline

    # 删除追踪数据
    for model in [SceneEntry, StyleSnapshot, TimelineEntry, Foreshadowing,
                  Subplot, PlotQuestion, PlotBlock, StyleConstraints, WorldSetting,
                  Relation, Character, ChapterOutline]:
        db.query(model).filter(model.project_id == project_id).delete()

    # 4. 重置大纲
    if outline:
        outline.title = None
        outline.summary = None
        outline.plot_points = []
        outline.characters = []
        outline.world_setting = None
        outline.emotional_curve = None
        outline.confirmed = False
        outline.chapter_count_suggested = 0

    db.commit()

    # 5. 构建初始状态并启动
    if not workflow_state:
        workflow_state = WorkflowState(project_id=project_id)
        db.add(workflow_state)
        db.commit()
        db.refresh(workflow_state)

    llm_config_id = None
    llm_model_name = None
    if request:
        llm_config_id = request.llm_config_id
        llm_model_name = request.llm_model_name

    if llm_config_id or llm_model_name:
        workflow_state.llm_config_id = llm_config_id
        workflow_state.llm_model_name = llm_model_name
        db.commit()

    initial_state = build_initial_state(
        project, outline, workflow_state,
        llm_config_id, llm_model_name, db=db,
    )

    graph = create_novel_graph_with_checkpointer(project_id, "default")
    config = {"configurable": {"thread_id": "default"}}

    def stream_generator():
        return stream_workflow_events(graph, config, initial_state)

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.put("/{project_id}/workflow/stage")
async def update_workflow_stage(
    project_id: int,
    request: UpdatePhaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新工作流阶段"""
    from app.utils.workflow import get_or_create_workflow_state

    get_project_for_user(project_id, current_user.id, db)
    workflow_state = get_or_create_workflow_state(db, project_id)
    workflow_state.stage = request.phase
    db.commit()

    return {
        "message": "Phase updated",
        "phase": request.phase,
    }


__all__ = ["router"]
