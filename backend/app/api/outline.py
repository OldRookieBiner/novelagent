"""Outline API routes"""

import json
import asyncio
import logging
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.outline import Outline
from app.schemas.outline import (
    OutlineResponse,
    OutlineUpdate,
    ChapterCountRequest,
    CollectedInfoUpdate,
    OutlineGenerateRequest,
)
from app.utils.auth import get_current_user
from app.utils.deps import get_user_settings_or_raise, get_llm_for_context
from app.utils.project import get_project_for_user, get_project_and_outline
from app.utils.workflow import get_or_create_workflow_state
from app.utils.error import format_sse_error
from app.agents.sse_events import format_done, format_error_message
from app.agents.state import (
    STAGE_OUTLINE,
    STAGE_CHAPTER_OUTLINES
)
from app.agents.nodes.outline_generation import (
    generate_outline_stream,
    parse_outline,
    outline_generation_node,
    # 导入章节数计算常量
    DEFAULT_CHAPTER_COUNT,
    WORDS_THRESHOLD_SHORT,
    WORDS_THRESHOLD_MEDIUM,
    WORDS_THRESHOLD_LONG,
    WORDS_THRESHOLD_VERY_LONG,
    WORDS_PER_CHAPTER_SHORT,
    WORDS_PER_CHAPTER_MEDIUM,
    WORDS_PER_CHAPTER_LONG,
    WORDS_PER_CHAPTER_VERY_LONG,
    WORDS_PER_CHAPTER_EPIC,
    MIN_CHAPTERS_SHORT,
    MIN_CHAPTERS_MEDIUM,
    MIN_CHAPTERS_LONG,
    MIN_CHAPTERS_VERY_LONG,
    MIN_CHAPTERS_EPIC,
)
# info_collection_node 已移除，信息收集由前端表单处理

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{project_id}/outline", response_model=OutlineResponse)
async def get_outline(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get outline for a project."""
    _, outline = get_project_and_outline(project_id, current_user.id, db)
    return OutlineResponse.model_validate(outline)


@router.post("/{project_id}/outline")
async def generate_outline(
    project_id: int,
    request: OutlineGenerateRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate outline using AI from collected info with SSE streaming."""
    from app.services.outline_service import OutlineService

    # 使用 OutlineService 进行验证
    service = OutlineService(db, project_id, current_user.id)
    service.validate_can_generate()

    # 获取项目和大纲（验证通过后必定存在）
    project, outline = service._load_project_outline()

    user_settings = get_user_settings_or_raise(current_user, db)

    # 更新工作流状态
    workflow_state = get_or_create_workflow_state(db, project_id)
    workflow_state.stage = STAGE_OUTLINE
    db.commit()

    # 导入完整 graph 和共享 SSE 流生成器
    from app.api.workflow import build_initial_state, stream_workflow_events
    from app.agents.graph import create_novel_graph_with_checkpointer

    # 构建初始状态
    llm_config_id = request.llm_config_id if request else None
    initial_state = build_initial_state(project, outline, workflow_state, llm_config_id)

    # 创建带检查点的完整 graph
    graph = create_novel_graph_with_checkpointer(project_id, "default", db)
    config = {"configurable": {"thread_id": "default"}}

    async def stream_generator():
        """使用完整 graph + checkpointer 生成大纲，委托共享 SSE 流生成器"""
        node_state = None

        try:
            async for sse_event in stream_workflow_events(graph, config, initial_state):
                # 捕获 outline_generation_node 的 node_done 事件
                if "event: node_done" in sse_event and "outline_generation_node" in sse_event:
                    try:
                        data_str = sse_event.split("data: ", 1)[1].strip()
                        payload = json.loads(data_str)
                        node_state = payload.get("state", {})
                    except (json.JSONDecodeError, IndexError):
                        pass
                    yield sse_event
                elif sse_event.startswith("event: done"):
                    # 替换默认 done 事件为兼容格式
                    pass
                else:
                    yield sse_event

            # 从 node_done state 中提取大纲数据写入 DB
            if node_state:
                outline.title = node_state.get("outline_title")
                outline.summary = node_state.get("outline_summary")
                outline.plot_points = node_state.get("outline_plot_points") or []
                outline.characters = node_state.get("outline_characters") or []
                outline.world_setting = node_state.get("outline_world_setting") or {}
                outline.emotional_curve = node_state.get("outline_emotional_curve")

                # 更新工作流状态
                workflow_state = get_or_create_workflow_state(db, project_id)
                workflow_state.stage = STAGE_OUTLINE

                db.commit()
                db.refresh(outline)

                # 发送兼容前端的 done 事件
                completion_data = {
                    "outline": {
                        "title": node_state.get("outline_title"),
                        "summary": node_state.get("outline_summary"),
                        "plot_points": node_state.get("outline_plot_points") or [],
                        "characters": node_state.get("outline_characters") or [],
                        "world_setting": node_state.get("outline_world_setting") or {},
                        "emotional_curve": node_state.get("outline_emotional_curve"),
                        "confirmed": False,
                        "chapter_count_suggested": outline.chapter_count_suggested,
                    },
                    "stage": STAGE_OUTLINE,
                }
                yield f"event: done\ndata: {json.dumps(completion_data)}\n\n"
            else:
                # node_state 为空时仍然发送完成事件
                yield f"event: done\ndata: {json.dumps({'message': 'Outline generation completed'})}\n\n"

        except asyncio.CancelledError:
            # async generator 中 CancelledError 后不能 yield（连接已关闭），必须 re-raise
            logger.warning("大纲生成 SSE 流被取消")
            raise
        except Exception as e:
            yield format_sse_error(e)
            yield format_done("Error occurred")

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.put("/{project_id}/outline", response_model=OutlineResponse)
async def update_outline(
    project_id: int,
    request: OutlineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update outline (title, summary, plot_points, collected_info, inspiration_template)."""
    _, outline = get_project_and_outline(project_id, current_user.id, db)

    # Check if outline is already confirmed
    if outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update a confirmed outline"
        )

    # Update fields if provided
    if request.title is not None:
        outline.title = request.title
    if request.summary is not None:
        outline.summary = request.summary
    if request.plot_points is not None:
        outline.plot_points = request.plot_points
    if request.collected_info is not None:
        outline.collected_info = request.collected_info
    if request.inspiration_template is not None:
        outline.inspiration_template = request.inspiration_template

    db.commit()
    db.refresh(outline)

    return OutlineResponse.model_validate(outline)


@router.put("/{project_id}/outline/confirm", response_model=OutlineResponse)
async def confirm_outline(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Confirm outline and move to next stage."""
    project, outline = get_project_and_outline(project_id, current_user.id, db)

    # Check if outline has required content
    if not outline.title or not outline.summary:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outline must have title and summary before confirming"
        )

    # Check if already confirmed
    if outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outline is already confirmed"
        )

    # 使用 outline_generation_node 已设置的章节数，不再从 collected_info 计算
    if outline.chapter_count_suggested <= 0:
        outline.chapter_count_suggested = DEFAULT_CHAPTER_COUNT
    outline.chapter_count_confirmed = True

    # Confirm the outline
    outline.confirmed = True
    # Skip chapter count stage, go directly to chapter outlines generating
    workflow_state = get_or_create_workflow_state(db, project_id)
    workflow_state.stage = STAGE_CHAPTER_OUTLINES

    db.commit()
    db.refresh(outline)

    return OutlineResponse.model_validate(outline)


@router.put("/{project_id}/outline/chapter-count", response_model=OutlineResponse)
async def set_chapter_count(
    project_id: int,
    request: ChapterCountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Set chapter count for the outline."""
    project, outline = get_project_and_outline(project_id, current_user.id, db)

    # Check if outline is confirmed
    if not outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outline must be confirmed before setting chapter count"
        )

    # Validate chapter count
    if request.chapter_count < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chapter count must be at least 1"
        )

    # Set chapter count
    outline.chapter_count_suggested = request.chapter_count
    outline.chapter_count_confirmed = True

    # 更新工作流状态
    workflow_state = get_or_create_workflow_state(db, project_id)
    workflow_state.stage = STAGE_CHAPTER_OUTLINES

    db.commit()
    db.refresh(outline)

    return OutlineResponse.model_validate(outline)


@router.put("/{project_id}/outline/collected-info", response_model=OutlineResponse)
async def update_collected_info(
    project_id: int,
    request: CollectedInfoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update collected info directly (skip chat if desired)."""
    project, outline = get_project_and_outline(project_id, current_user.id, db)

    # Check if outline is already confirmed
    if outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update collected info after outline is confirmed"
        )

    # Update collected info
    current_info = dict(outline.collected_info or {})  # 拷贝以触发 SQLAlchemy 变更检测
    if request.genre is not None:
        current_info["genre"] = request.genre
    if request.theme is not None:
        current_info["theme"] = request.theme
    if request.main_characters is not None:
        current_info["main_characters"] = request.main_characters
    if request.world_setting is not None:
        current_info["world_setting"] = request.world_setting
    if request.style_preference is not None:
        current_info["style_preference"] = request.style_preference

    # 处理新增灵感采集字段
    new_fields = [
        'novelType', 'targetWords', 'contextStrategy', 'coreTheme', 'targetReader', 'era',
        'wordsPerChapter', 'customWordsPerChapter', 'maleLead', 'customMaleLead',
        'femaleLead', 'customFemaleLead', 'protagonist', 'narrative',
        'goldFinger', 'customGoldFinger', 'customGenre', 'customWorldSetting',
        'inspiration_template',
    ]
    for field in new_fields:
        value = getattr(request, field, None)
        if value is not None:
            current_info[field] = value

    outline.collected_info = current_info

    # 同步 inspiration_template 到 independent 列，确保 generate_outline 能读取
    if request.inspiration_template is not None:
        outline.inspiration_template = request.inspiration_template

    # Check if all required info is provided (use new field names)
    target_reader = current_info.get("targetReader")
    has_genre = bool(current_info.get("genre") or current_info.get("customGenre"))
    has_world = bool(current_info.get("world_setting") or current_info.get("worldSetting") or current_info.get("customWorldSetting"))
    has_protagonist = bool(
        current_info.get("protagonist") or
        current_info.get("maleLead") or current_info.get("customMaleLead") or
        current_info.get("femaleLead") or current_info.get("customFemaleLead")
    )
    if has_genre and has_world and has_protagonist:
        workflow_state = get_or_create_workflow_state(db, project_id)
        workflow_state.stage = STAGE_OUTLINE

    db.commit()
    db.refresh(outline)

    return OutlineResponse.model_validate(outline)


