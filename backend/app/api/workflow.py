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
from app.models.workflow_state import WorkflowState
from app.utils.auth import get_current_user
from app.utils.project import get_project_for_user
from app.utils.error import format_sse_error
from app.utils.deps import get_user_settings_or_raise
from app.agents.graph import create_novel_graph_with_checkpointer
from app.agents.state import NovelState

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

def build_initial_state(
    project: Project,
    outline: Outline,
    workflow_state: WorkflowState,
    llm_config_id: Optional[int] = None
) -> NovelState:
    """
    从项目、大纲和工作流状态构建初始 NovelState。

    Args:
        project: 项目实例
        outline: 大纲实例
        workflow_state: 工作流状态实例
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

    # 构建状态
    state: NovelState = {
        # 基本信息
        "project_id": project.id,

        # 阶段控制（使用 workflow_state.stage，无需映射）
        "stage": workflow_state.stage,

        # 灵感/输入
        # 优先从 inspiration_template 列读取，回退到 collected_info 字典中的 inspiration_template
        "collected_info": outline.collected_info or {},
        "inspiration_template": outline.inspiration_template or (outline.collected_info or {}).get("inspiration_template"),

        # 大纲
        "outline_title": outline.title,
        "outline_summary": outline.summary,
        "outline_plot_points": outline.plot_points or [],
        "outline_characters": outline.characters or [],
        "outline_world_setting": outline.world_setting,
        "outline_emotional_curve": outline.emotional_curve,
        "outline_confirmed": outline.confirmed,

        # 大纲有效性：有标题或概述即有效，避免路由到 end 导致工作流提前终止
        "outline_valid": bool(outline.title or outline.summary),

        # 章节大纲
        "chapter_count": outline.chapter_count_suggested or 0,
        "chapter_outlines": chapter_outlines,
        "chapter_outlines_confirmed": all(co.confirmed for co in project.chapter_outlines) if chapter_outlines else False,

        # 章节正文
        "written_chapters": written_chapters,
        "current_chapter": workflow_state.current_chapter,

        # 审核/重写
        "review_mode": workflow_state.workflow_mode,
        "review_result": None,
        "rewrite_count": 0,
        "max_rewrite_count": workflow_state.max_rewrite_count,

        # 工作流控制
        "waiting_for_confirmation": workflow_state.waiting_for_confirmation,
        "confirmation_type": workflow_state.confirmation_type,

        # LLM 服务
        "llm_config_id": llm_config_id,
    }

    return state


def get_latest_checkpoint(project_id: int, thread_id: str = "main", db: Session = None) -> Optional[dict]:
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


def delete_project_checkpoints(project_id: int, thread_id: str = "main", db: Session = None) -> int:
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
    project = get_project_for_user(project_id, current_user.id, db)

    # 获取大纲
    outline = db.query(Outline).filter(
        Outline.project_id == project_id
    ).first()

    if not outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outline not found"
        )

    user_settings = get_user_settings_or_raise(current_user, db)

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

    # 获取 LLM 配置 ID
    llm_config_id = None
    if request:
        llm_config_id = request.llm_config_id

    # 构建初始状态
    initial_state = build_initial_state(project, outline, workflow_state, llm_config_id)

    # 使用固定 thread_id，确保 confirm/cancel/state 等操作能找到同一检查点
    thread_id = "main"

    graph = create_novel_graph_with_checkpointer(project_id, thread_id, db)

    # 配置
    config = {
        "configurable": {
            "thread_id": thread_id
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

                    if isinstance(output, dict):
                        yield f"event: node_done\ndata: {json.dumps({'node': node_name, 'state': output})}\n\n"

                    # 大纲生成节点完成后，将结果持久化到 outlines 表
                    if node_name == "outline_generation_node" and isinstance(output, dict):
                        import logging
                        logger = logging.getLogger(__name__)

                        # 验证数据有效性，防止空数据覆盖
                        new_title = output.get("outline_title", "")
                        new_summary = output.get("outline_summary", "")
                        new_characters = output.get("outline_characters", [])
                        new_plot_points = output.get("outline_plot_points", [])

                        if not new_title and not new_summary and not new_characters and not new_plot_points:
                            logger.warning(f"workflow: outline_generation_node returned empty data for project {project_id}")
                            yield f"event: error\ndata: {json.dumps({'error': '大纲生成失败，AI 返回数据为空，请重试'})}\n\n"
                            return
                        else:
                            # 只有有效数据才更新
                            if new_title:
                                outline.title = new_title
                            if new_summary:
                                outline.summary = new_summary
                            if new_plot_points:
                                outline.plot_points = new_plot_points
                            if new_characters:
                                outline.characters = new_characters

                            outline.world_setting = output.get("outline_world_setting", outline.world_setting or {})
                            outline.emotional_curve = output.get("outline_emotional_curve", outline.emotional_curve)
                            outline.chapter_count_suggested = output.get("chapter_count", outline.chapter_count_suggested)

                            logger.info(f"workflow: persisted outline for project {project_id}: title='{new_title}', char={len(new_characters)}, plot={len(new_plot_points)}")

                        db.commit()

                    # 关系生成节点完成后，自动确认大纲并停止（规划阶段完成）
                    if node_name == "generate_relations_node":
                        import logging
                        logger = logging.getLogger(__name__)

                        # 自动确认大纲，允许用户后续生成章节大纲
                        outline.confirmed = True
                        outline.chapter_count_confirmed = True
                        db.commit()
                        logger.info(f"workflow: auto-confirmed outline for project {project_id}")
                        # 规划阶段已完成，发送 done 事件并终止流
                        yield f"event: done\ndata: {json.dumps({'message': 'Generation completed'})}\n\n"
                        return

                    # 章节内容生成节点完成后，将结果持久化到 chapters 表
                    if node_name == "generate_chapter_content_node" and isinstance(output, dict):
                        import logging
                        logger = logging.getLogger(__name__)

                        written_chapters = output.get("written_chapters", [])
                        for chapter_data in written_chapters:
                            chapter_num = chapter_data.get("chapter_number")
                            if not chapter_num:
                                continue
                            # 查找对应的 ChapterOutline
                            chapter_outline = db.query(ChapterOutline).filter(
                                ChapterOutline.project_id == project_id,
                                ChapterOutline.chapter_number == chapter_num
                            ).first()
                            if not chapter_outline:
                                continue
                            # 查找或创建 Chapter 记录
                            chapter = db.query(Chapter).filter(
                                Chapter.chapter_outline_id == chapter_outline.id
                            ).first()
                            if not chapter:
                                chapter = Chapter(
                                    chapter_outline_id=chapter_outline.id,
                                    content=chapter_data.get("content", ""),
                                    word_count=chapter_data.get("word_count", 0),
                                    review_passed=False,
                                    review_feedback=None
                                )
                                db.add(chapter)
                            else:
                                chapter.content = chapter_data.get("content", chapter.content)
                                chapter.word_count = chapter_data.get("word_count", chapter.word_count)
                        db.commit()
                        logger.info(f"workflow: persisted chapter content for project {project_id}")

                    # 审核节点完成后，将审核结果持久化到 chapters 表
                    if node_name == "review_node" and isinstance(output, dict):
                        import logging
                        logger = logging.getLogger(__name__)

                        review_result = output.get("review_result", {})
                        current_chapter = output.get("current_chapter", 1)
                        # current_chapter 在 generate_chapter_content_node 中已递增，所以被审核的是 current_chapter - 1
                        reviewed_chapter_num = current_chapter - 1
                        chapter_outline = db.query(ChapterOutline).filter(
                            ChapterOutline.project_id == project_id,
                            ChapterOutline.chapter_number == reviewed_chapter_num
                        ).first()
                        if chapter_outline:
                            chapter = db.query(Chapter).filter(
                                Chapter.chapter_outline_id == chapter_outline.id
                            ).first()
                            if chapter:
                                from app.agents.nodes.review import check_review_passed
                                chapter.review_passed = check_review_passed(review_result)
                                chapter.review_feedback = review_result.get("raw_response")
                                chapter.review_result = review_result
                                db.commit()
                        logger.info(f"workflow: persisted review result for project {project_id}")

                    # 重写节点完成后，将重写后的内容持久化到 chapters 表
                    if node_name == "rewrite_node" and isinstance(output, dict):
                        import logging
                        logger = logging.getLogger(__name__)

                        written_chapters = output.get("written_chapters", [])
                        for chapter_data in written_chapters:
                            chapter_num = chapter_data.get("chapter_number")
                            if not chapter_num:
                                continue
                            chapter_outline = db.query(ChapterOutline).filter(
                                ChapterOutline.project_id == project_id,
                                ChapterOutline.chapter_number == chapter_num
                            ).first()
                            if not chapter_outline:
                                continue
                            chapter = db.query(Chapter).filter(
                                Chapter.chapter_outline_id == chapter_outline.id
                            ).first()
                            if chapter:
                                chapter.content = chapter_data.get("content", chapter.content)
                                chapter.word_count = chapter_data.get("word_count", chapter.word_count)
                                chapter.rewrite_count = output.get("rewrite_count", chapter.rewrite_count)
                        db.commit()
                        logger.info(f"workflow: persisted rewritten chapter for project {project_id}")

                elif event_type == "on_chat_model_stream":
                    # LLM 流式输出
                    chunk = event_data.get("chunk")
                    if chunk:
                        content = getattr(chunk, "content", str(chunk))
                        yield f"event: chunk\ndata: {json.dumps({'content': content})}\n\n"

            # 工作流完成
            yield f"event: done\ndata: {json.dumps({'message': 'Workflow completed'})}\n\n"

        except Exception as e:
            # 发送错误事件（已清理敏感信息）
            yield format_sse_error(e)

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
    project = get_project_for_user(project_id, current_user.id, db)

    # 获取最新检查点
    checkpoint_state = get_latest_checkpoint(project_id, "main", db)

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
        WorkflowCheckpoint.thread_id == "main"
    ).order_by(WorkflowCheckpoint.updated_at.desc()).first()

    if record:
        checkpoint_data = record.checkpoint.copy()
        checkpoint_data["channel_values"] = checkpoint_state
        record.checkpoint = checkpoint_data

    # 同步更新大纲和项目
    import logging
    logger = logging.getLogger(__name__)
    if confirmation_type == "outline":
        outline = db.query(Outline).filter(Outline.project_id == project_id).first()
        if outline:
            outline.title = checkpoint_state.get("outline_title", outline.title)
            outline.summary = checkpoint_state.get("outline_summary", outline.summary)
            outline.confirmed = True
            logger.info(f"confirm_workflow: setting outline.confirmed=True for project {project_id}")

    # 提交所有数据库更改
    db.commit()

    # 通过 LangGraph 恢复执行
    graph = create_novel_graph_with_checkpointer(project_id, "main", db)
    config = {"configurable": {"thread_id": "main"}}

    async def stream_generator():
        """LangGraph 工作流恢复执行 SSE 流生成器"""
        try:
            yield f"event: node_start\ndata: {json.dumps({'node': 'workflow_resume', 'message': 'Resuming workflow'})}\n\n"

            async for event in graph.astream_events(None, config, version="v2"):
                event_type = event.get("event")
                event_name = event.get("name", "")
                event_data = event.get("data", {})

                if event_type == "on_chain_start":
                    yield f"event: node_start\ndata: {json.dumps({'node': event_name})}\n\n"

                elif event_type == "on_chain_end":
                    output = event_data.get("output", {})
                    if isinstance(output, dict):
                        yield f"event: node_done\ndata: {json.dumps({'node': event_name, 'state': output})}\n\n"

                elif event_type == "on_chat_model_stream":
                    chunk = event_data.get("chunk")
                    if chunk:
                        content = getattr(chunk, "content", str(chunk))
                        yield f"event: chunk\ndata: {json.dumps({'content': content})}\n\n"

            yield f"event: done\ndata: {json.dumps({'message': 'Workflow completed'})}\n\n"

        except Exception as e:
            yield format_sse_error(e)

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
    project = get_project_for_user(project_id, current_user.id, db)

    # 获取最新检查点
    checkpoint_state = get_latest_checkpoint(project_id, "main", db)

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
        # 无检查点，从 WorkflowState 获取状态
        workflow_state = db.query(WorkflowState).filter(
            WorkflowState.project_id == project_id,
            WorkflowState.thread_id == "main"
        ).first()

        if workflow_state:
            return WorkflowStateResponse(
                project_id=project_id,
                has_checkpoint=False,
                stage=workflow_state.stage,
                waiting_for_confirmation=workflow_state.waiting_for_confirmation,
                confirmation_type=workflow_state.confirmation_type,
                current_state=None
            )
        else:
            # 无 WorkflowState，返回默认状态
            return WorkflowStateResponse(
                project_id=project_id,
                has_checkpoint=False,
                stage="inspiration",
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
    project = get_project_for_user(project_id, current_user.id, db)

    # 删除检查点
    deleted_count = delete_project_checkpoints(project_id, "main", db)

    return {
        "message": "Workflow cancelled",
        "deleted_checkpoints": deleted_count
    }


@router.post("/{project_id}/workflow/cleanup")
async def cleanup_workflow_checkpoints(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    清除工作流检查点，用于重试前清理状态。
    """
    project = get_project_for_user(project_id, current_user.id, db)

    deleted = db.query(WorkflowCheckpoint).filter(
        WorkflowCheckpoint.project_id == project_id
    ).delete()

    workflow_state = db.query(WorkflowState).filter(
        WorkflowState.project_id == project_id
    ).first()
    if workflow_state:
        workflow_state.stage = "inspiration"
        workflow_state.waiting_for_confirmation = False
        workflow_state.confirmation_type = None

    db.commit()

    import logging
    logging.getLogger(__name__).info(f"Cleaned up {deleted} checkpoints for project {project_id}")

    return {"message": "Checkpoints cleaned up", "deleted": deleted}


class UpdateStageRequest(BaseModel):
    """更新工作流阶段请求"""
    stage: str


@router.put("/{project_id}/workflow/stage")
async def update_workflow_stage(
    project_id: int,
    request: UpdateStageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新工作流阶段。

    用于手动切换工作流阶段，例如：
    - 灵感采集完成后切换到大纲生成
    - 章节大纲确认后切换到写作
    """
    from app.utils.workflow import get_or_create_workflow_state

    # 验证项目所有权
    get_project_for_user(project_id, current_user.id, db)

    # 获取或创建工作流状态
    workflow_state = get_or_create_workflow_state(db, project_id)

    # 更新阶段
    workflow_state.stage = request.stage
    db.commit()

    return {
        "message": "Stage updated",
        "stage": request.stage
    }


# ========== Export ==========
__all__ = ["router"]
