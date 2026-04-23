"""Workflow API routes for LangGraph integration"""

import json
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.outline import Outline, ChapterOutline
from app.models.chapter import Chapter
from app.models.checkpoint import WorkflowCheckpoint
from app.models.settings import UserSettings
from app.utils.auth import get_current_user
from app.agents.graph import create_novel_graph_with_checkpointer
from app.agents.state import (
    NovelState,
    STAGE_INSPIRATION,
    STAGE_OUTLINE,
    STAGE_CHAPTER_OUTLINES,
    STAGE_WRITING,
    STAGE_REVIEW,
    STAGE_COMPLETE,
    WORKFLOW_MODE_STEP_BY_STEP,
    WORKFLOW_MODE_HYBRID,
    WORKFLOW_MODE_AUTO,
)

router = APIRouter()


# ========== Request/Response Schemas ==========

class WorkflowRunRequest(BaseModel):
    """工作流运行请求"""
    llm_config_id: Optional[int] = None  # 指定模型配置 ID


class WorkflowConfirmRequest(BaseModel):
    """工作流确认请求"""
    # 可选：用户修改后的数据
    outline_title: Optional[str] = None
    outline_summary: Optional[str] = None
    chapter_outlines: Optional[list] = None


class WorkflowStateResponse(BaseModel):
    """工作流状态响应"""
    project_id: int
    has_checkpoint: bool
    stage: Optional[str] = None
    waiting_for_confirmation: bool = False
    confirmation_type: Optional[str] = None
    current_state: Optional[dict] = None


# ========== Helper Functions ==========

def get_project_with_ownership(
    project_id: int,
    user_id: int,
    db: Session
) -> Project:
    """
    获取项目并验证所有权。

    Args:
        project_id: 项目 ID
        user_id: 用户 ID
        db: 数据库会话

    Returns:
        Project 实例

    Raises:
        HTTPException: 项目不存在或无权访问
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == user_id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    return project


def build_initial_state(
    project: Project,
    outline: Outline,
    llm_config_id: Optional[int] = None
) -> NovelState:
    """
    从项目和大纲构建初始 NovelState。

    Args:
        project: 项目实例
        outline: 大纲实例
        llm_config_id: 模型配置 ID

    Returns:
        NovelState 字典
    """
    # 获取章节大纲
    chapter_outlines = [
        {
            "chapter_number": co.chapter_number,
            "title": co.title,
            "scene": co.scene,
            "characters": co.characters,
            "plot": co.plot,
            "conflict": co.conflict,
            "ending": co.ending,
            "target_words": co.target_words,
        }
        for co in sorted(project.chapter_outlines, key=lambda x: x.chapter_number)
    ]

    # 获取已写入的章节
    written_chapters = []
    for co in project.chapter_outlines:
        if co.chapter and co.chapter.content:
            written_chapters.append({
                "chapter_number": co.chapter_number,
                "content": co.chapter.content,
                "word_count": co.chapter.word_count,
            })

    # 确定当前阶段
    stage = project.stage
    if stage == "inspiration_collecting":
        stage = STAGE_INSPIRATION
    elif stage == "outline_generating":
        stage = STAGE_OUTLINE
    elif stage == "chapter_writing":
        stage = STAGE_WRITING

    # 构建状态
    state: NovelState = {
        # 基本信息
        "project_id": project.id,

        # 阶段控制
        "stage": stage,

        # 灵感/输入
        "collected_info": outline.collected_info or {},
        "inspiration_template": outline.inspiration_template,

        # 大纲
        "outline_title": outline.title,
        "outline_summary": outline.summary,
        "outline_plot_points": outline.plot_points or [],
        "outline_characters": outline.characters or [],
        "outline_world_setting": outline.world_setting,
        "outline_emotional_curve": outline.emotional_curve,
        "outline_confirmed": outline.confirmed,

        # 章节大纲
        "chapter_count": outline.chapter_count_suggested or 0,
        "chapter_outlines": chapter_outlines,
        "chapter_outlines_confirmed": all(co.confirmed for co in project.chapter_outlines) if chapter_outlines else False,

        # 章节正文
        "written_chapters": written_chapters,
        "current_chapter": len(written_chapters) + 1,

        # 审核/重写
        "review_mode": project.review_mode or WORKFLOW_MODE_HYBRID,
        "review_result": None,
        "rewrite_count": 0,
        "max_rewrite_count": project.max_rewrite_count or 3,

        # 工作流控制
        "waiting_for_confirmation": False,
        "confirmation_type": None,

        # LLM 服务
        "llm_config_id": llm_config_id,
    }

    return state


def get_latest_checkpoint(project_id: int, thread_id: str = "default", db: Session = None) -> Optional[dict]:
    """
    获取项目的最新检查点状态。

    Args:
        project_id: 项目 ID
        thread_id: 线程 ID
        db: 数据库会话（必须传入）

    Returns:
        检查点状态字典，如果不存在则返回 None
    """
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
    """
    删除项目的所有检查点。

    Args:
        project_id: 项目 ID
        thread_id: 线程 ID
        db: 数据库会话（必须传入）

    Returns:
        删除的记录数
    """
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
    current_user: User = Depends(get_current_user)
):
    """
    启动或恢复工作流（SSE 流式）。

    使用 LangGraph 的 astream_events 进行流式传输，
    发送以下 SSE 事件：
    - node_start: 节点开始执行
    - chunk: 内容片段
    - node_done: 节点执行完成
    - waiting: 等待用户确认
    - done: 工作流完成
    - error: 错误
    """
    # 验证项目所有权
    project = get_project_with_ownership(project_id, current_user.id, db)

    # 获取大纲
    outline = db.query(Outline).filter(
        Outline.project_id == project_id
    ).first()

    if not outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outline not found"
        )

    # 获取用户设置
    user_settings = db.query(UserSettings).filter(
        UserSettings.user_id == current_user.id
    ).first()

    if not user_settings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User settings not found"
        )

    # 获取 LLM 配置 ID
    llm_config_id = None
    if request:
        llm_config_id = request.llm_config_id

    # 构建初始状态
    initial_state = build_initial_state(project, outline, llm_config_id)

    # 创建带检查点的图
    graph = create_novel_graph_with_checkpointer(project_id, "default")

    # 配置
    config = {
        "configurable": {
            "thread_id": "default"
        }
    }

    # 创建 SSE 流生成器
    async def stream_generator():
        """LangGraph 工作流 SSE 流生成器"""
        try:
            # 发送开始事件
            yield f"event: node_start\ndata: {json.dumps({'node': 'workflow', 'message': 'Starting workflow'})}\n\n"

            # 使用 astream_events 进行流式传输
            async for event in graph.astream_events(initial_state, config, version="v2"):
                event_type = event.get("event")
                event_name = event.get("name", "")
                event_data = event.get("data", {})

                # 根据事件类型处理
                if event_type == "on_chain_start":
                    # 节点开始执行
                    node_name = event_name
                    yield f"event: node_start\ndata: {json.dumps({'node': node_name})}\n\n"

                elif event_type == "on_chain_end":
                    # 节点执行完成
                    node_name = event_name
                    output = event_data.get("output", {})

                    # 检查是否等待确认
                    if isinstance(output, dict):
                        if output.get("waiting_for_confirmation"):
                            yield f"event: waiting\ndata: {json.dumps({'node': node_name, 'confirmation_type': output.get('confirmation_type')})}\n\n"
                            return  # 停止流
                        else:
                            yield f"event: node_done\ndata: {json.dumps({'node': node_name, 'state': output})}\n\n"

                elif event_type == "on_chat_model_stream":
                    # LLM 流式输出
                    chunk = event_data.get("chunk")
                    if chunk:
                        content = getattr(chunk, "content", str(chunk))
                        yield f"event: chunk\ndata: {json.dumps({'content': content})}\n\n"

            # 工作流完成
            yield f"event: done\ndata: {json.dumps({'message': 'Workflow completed'})}\n\n"

        except Exception as e:
            # 发送错误事件
            error_msg = str(e)
            yield f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/{project_id}/workflow/confirm")
async def confirm_workflow(
    project_id: int,
    request: WorkflowConfirmRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    确认当前节点并继续工作流。

    用于在 step_by_step 或 hybrid 模式下，
    用户确认大纲或章节大纲后继续执行。
    """
    # 验证项目所有权
    project = get_project_with_ownership(project_id, current_user.id, db)

    # 获取最新检查点
    checkpoint_state = get_latest_checkpoint(project_id, "default", db)

    if not checkpoint_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active workflow to confirm"
        )

    # 检查是否正在等待确认
    if not checkpoint_state.get("waiting_for_confirmation"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow is not waiting for confirmation"
        )

    # 更新状态：清除等待确认标志
    checkpoint_state["waiting_for_confirmation"] = False

    # 应用用户修改（如果有）
    if request:
        if request.outline_title:
            checkpoint_state["outline_title"] = request.outline_title
        if request.outline_summary:
            checkpoint_state["outline_summary"] = request.outline_summary
        if request.chapter_outlines:
            checkpoint_state["chapter_outlines"] = request.chapter_outlines

    # 更新确认状态
    confirmation_type = checkpoint_state.get("confirmation_type")
    if confirmation_type == "outline":
        checkpoint_state["outline_confirmed"] = True
    elif confirmation_type == "chapter_outlines":
        checkpoint_state["chapter_outlines_confirmed"] = True

    checkpoint_state["confirmation_type"] = None

    # 更新数据库中的检查点（使用传入的 db 会话）
    record = db.query(WorkflowCheckpoint).filter(
        WorkflowCheckpoint.project_id == project_id,
        WorkflowCheckpoint.thread_id == "default"
    ).order_by(WorkflowCheckpoint.updated_at.desc()).first()

    if record:
        checkpoint_data = record.checkpoint.copy()
        checkpoint_data["channel_values"] = checkpoint_state
        record.checkpoint = checkpoint_data

    # 同步更新大纲和项目
    if confirmation_type == "outline":
        outline = db.query(Outline).filter(Outline.project_id == project_id).first()
        if outline:
            outline.title = checkpoint_state.get("outline_title", outline.title)
            outline.summary = checkpoint_state.get("outline_summary", outline.summary)
            outline.confirmed = True

    # 提交所有数据库更改
    db.commit()

    return {
        "message": "Confirmation received",
        "confirmation_type": confirmation_type,
        "next_stage": checkpoint_state.get("stage")
    }


@router.get("/{project_id}/workflow/state", response_model=WorkflowStateResponse)
async def get_workflow_state(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取当前工作流状态。

    返回检查点状态信息，包括：
    - 是否有检查点
    - 当前阶段
    - 是否等待确认
    - 完整状态数据
    """
    # 验证项目所有权
    project = get_project_with_ownership(project_id, current_user.id, db)

    # 获取最新检查点
    checkpoint_state = get_latest_checkpoint(project_id, "default", db)

    if checkpoint_state:
        return WorkflowStateResponse(
            project_id=project_id,
            has_checkpoint=True,
            stage=checkpoint_state.get("stage"),
            waiting_for_confirmation=checkpoint_state.get("waiting_for_confirmation", False),
            confirmation_type=checkpoint_state.get("confirmation_type"),
            current_state=checkpoint_state
        )
    else:
        # 无检查点，返回项目当前状态
        outline = db.query(Outline).filter(Outline.project_id == project_id).first()

        return WorkflowStateResponse(
            project_id=project_id,
            has_checkpoint=False,
            stage=project.stage,
            waiting_for_confirmation=False,
            confirmation_type=None,
            current_state=None
        )


@router.post("/{project_id}/workflow/cancel")
async def cancel_workflow(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    取消当前工作流。

    删除项目的所有检查点，工作流将无法恢复。
    """
    # 验证项目所有权
    project = get_project_with_ownership(project_id, current_user.id, db)

    # 删除检查点
    deleted_count = delete_project_checkpoints(project_id, "default", db)

    return {
        "message": "Workflow cancelled",
        "deleted_checkpoints": deleted_count
    }


# ========== Export ==========
__all__ = ["router"]
