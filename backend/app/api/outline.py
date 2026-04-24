"""Outline API routes"""

import json
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.outline import Outline
from app.models.settings import UserSettings
from app.schemas.outline import (
    OutlineResponse,
    OutlineUpdate,
    ChapterCountRequest,
    ChatMessage,
    ChatResponse,
    CollectedInfoUpdate,
    OutlineGenerateRequest,
)
from app.utils.auth import get_current_user
from app.utils.llm import get_llm_for_user
from app.utils.workflow import get_or_create_workflow_state
from app.agents.state import (
    STAGE_INSPIRATION,
    STAGE_OUTLINE,
    STAGE_CHAPTER_OUTLINES
)
from app.agents.nodes.outline_generation import (
    generate_outline_node,
    generate_outline_stream,
    parse_outline,
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
from app.services.llm import get_llm_service

router = APIRouter()


def get_project_and_outline(
    project_id: int,
    user_id: int,
    db: Session
) -> tuple[Project, Outline]:
    """Get project and outline, verifying ownership."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == user_id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    outline = db.query(Outline).filter(
        Outline.project_id == project_id
    ).first()

    if not outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outline not found"
        )

    return project, outline


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
    project, outline = get_project_and_outline(project_id, current_user.id, db)

    # Check if outline is already confirmed
    if outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot regenerate a confirmed outline"
        )

    # Get user settings for LLM
    user_settings = db.query(UserSettings).filter(
        UserSettings.user_id == current_user.id
    ).first()

    if not user_settings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User settings not found"
        )

    # 更新工作流状态
    workflow_state = get_or_create_workflow_state(db, project_id)
    workflow_state.stage = STAGE_OUTLINE
    db.commit()

    # Get LLM service
    llm_config_id = request.llm_config_id if request else None
    llm = get_llm_for_user(current_user.id, user_settings, db, llm_config_id)

    # Prepare state for outline generation
    state = {
        "collected_info": outline.collected_info or {},
        "inspiration_template": outline.inspiration_template or "",
        "outline_title": outline.title,
        "outline_summary": outline.summary,
        "outline_plot_points": outline.plot_points or [],
    }

    # Create async generator for SSE streaming
    async def stream_generator():
        """Generate outline and stream via SSE."""
        accumulated_content = ""

        try:
            async for chunk in generate_outline_stream(state, llm):
                accumulated_content += chunk
                # Send chunk as SSE event (JSON encode to preserve newlines)
                yield f"data: {json.dumps(chunk)}\n\n"

            # Parse the final outline
            parsed = parse_outline(accumulated_content)

            # Update outline with generated content
            outline.title = parsed["title"]
            outline.summary = parsed["summary"]
            outline.plot_points = parsed["plot_points"]
            # v0.6.1: 保存增强字段
            outline.characters = parsed.get("characters", [])
            outline.world_setting = parsed.get("world_setting", {})
            outline.emotional_curve = parsed.get("emotional_curve")

            # 更新工作流状态
            workflow_state = get_or_create_workflow_state(db, project_id)
            workflow_state.stage = STAGE_OUTLINE

            db.commit()
            db.refresh(outline)

            # Send completion event with parsed outline and updated stage
            completion_data = {
                "outline": {
                    "title": parsed["title"],
                    "summary": parsed["summary"],
                    "plot_points": parsed["plot_points"],
                    "characters": parsed.get("characters", []),
                    "world_setting": parsed.get("world_setting", {}),
                    "emotional_curve": parsed.get("emotional_curve"),
                    "confirmed": False,
                    "chapter_count_suggested": outline.chapter_count_suggested,
                },
                "stage": STAGE_OUTLINE,
            }
            yield f"event: done\ndata: {json.dumps(completion_data)}\n\n"

        except Exception as e:
            # 检查是否有已生成的内容（可能是用户中断）
            if accumulated_content and len(accumulated_content) > 50:
                # 尝试解析已生成的内容
                try:
                    parsed = parse_outline(accumulated_content)
                    if parsed["title"] or parsed["summary"]:
                        # 保存已生成的内容
                        outline.title = parsed["title"]
                        outline.summary = parsed["summary"]
                        outline.plot_points = parsed["plot_points"]
                        # v0.6.1: 保存增强字段
                        outline.characters = parsed.get("characters", [])
                        outline.world_setting = parsed.get("world_setting", {})
                        outline.emotional_curve = parsed.get("emotional_curve")
                        workflow_state = get_or_create_workflow_state(db, project_id)
                        workflow_state.stage = STAGE_OUTLINE
                        db.commit()

                        # 发送中断完成事件
                        completion_data = {
                            "outline": {
                                "title": parsed["title"],
                                "summary": parsed["summary"],
                                "plot_points": parsed["plot_points"],
                                "characters": parsed.get("characters", []),
                                "world_setting": parsed.get("world_setting", {}),
                                "emotional_curve": parsed.get("emotional_curve"),
                                "confirmed": False,
                                "chapter_count_suggested": outline.chapter_count_suggested,
                            },
                            "stage": STAGE_OUTLINE,
                            "interrupted": True,
                        }
                        yield f"event: done\ndata: {json.dumps(completion_data)}\n\n"
                        return
                except Exception:
                    pass

            # Send error event
            yield f"event: error\ndata: {json.dumps(str(e))}\n\n"

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


@router.post("/{project_id}/outline/confirm", response_model=OutlineResponse)
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

    # 从灵感数据计算章节数
    collected_info = outline.collected_info or {}
    target_words = collected_info.get("targetWords", 100000)

    # 使用常量计算章节数
    chapter_count = DEFAULT_CHAPTER_COUNT
    if isinstance(target_words, int):
        if target_words <= WORDS_THRESHOLD_SHORT:
            chapter_count = max(MIN_CHAPTERS_SHORT, int(target_words / WORDS_PER_CHAPTER_SHORT))
        elif target_words <= WORDS_THRESHOLD_MEDIUM:
            chapter_count = max(MIN_CHAPTERS_MEDIUM, int(target_words / WORDS_PER_CHAPTER_MEDIUM))
        elif target_words <= WORDS_THRESHOLD_LONG:
            chapter_count = max(MIN_CHAPTERS_LONG, int(target_words / WORDS_PER_CHAPTER_LONG))
        elif target_words <= WORDS_THRESHOLD_VERY_LONG:
            chapter_count = max(MIN_CHAPTERS_VERY_LONG, int(target_words / WORDS_PER_CHAPTER_VERY_LONG))
        else:
            chapter_count = max(MIN_CHAPTERS_EPIC, int(target_words / WORDS_PER_CHAPTER_EPIC))

    # Update outline with chapter count
    outline.chapter_count_suggested = chapter_count
    outline.chapter_count_confirmed = True

    # Confirm the outline
    outline.confirmed = True
    # Skip chapter count stage, go directly to chapter outlines generating
    workflow_state = get_or_create_workflow_state(db, project_id)
    workflow_state.stage = STAGE_CHAPTER_OUTLINES

    db.commit()
    db.refresh(outline)

    return OutlineResponse.model_validate(outline)


@router.post("/{project_id}/outline/chapter-count", response_model=OutlineResponse)
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
    current_info = outline.collected_info or {}
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

    outline.collected_info = current_info

    # Check if all required info is provided
    required_fields = ["genre", "main_characters", "world_setting"]
    if all(field in current_info and current_info[field] for field in required_fields):
        workflow_state = get_or_create_workflow_state(db, project_id)
        workflow_state.stage = STAGE_OUTLINE

    db.commit()
    db.refresh(outline)

    return OutlineResponse.model_validate(outline)


@router.post("/{project_id}/outline/chat", response_model=ChatResponse)
async def info_collection_chat(
    project_id: int,
    request: ChatMessage,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Chat with AI for info collection."""
    project, outline = get_project_and_outline(project_id, current_user.id, db)

    # Check if project is in inspiration_collecting stage
    workflow_state = get_or_create_workflow_state(db, project_id)
    if workflow_state.stage not in [STAGE_INSPIRATION, STAGE_OUTLINE]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project is not in inspiration collection stage"
        )

    # Check if outline is already confirmed
    if outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot chat after outline is confirmed"
        )

    # Get user settings for LLM
    user_settings = db.query(UserSettings).filter(
        UserSettings.user_id == current_user.id
    ).first()

    if not user_settings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User settings not found"
        )

    try:
        # Get LLM service
        llm = get_llm_service(user_settings)

        # Get existing messages
        messages = outline.messages or []

        # Prepare state for info collection
        # 注意：info_collection_node 已移除，信息收集现在由前端表单处理
        # 这里保留聊天功能用于向后兼容，但简化处理

        # 简化处理：直接返回用户消息，不进行 AI 处理
        # 前端已使用灵感表单收集信息，此端点仅保留用于兼容性
        return ChatResponse(
            response="信息收集功能已由前端表单处理。请使用灵感表单提交您的创作信息。",
            collected_info=CollectedInfo(**outline.collected_info) if outline.collected_info else None,
            is_info_sufficient=True  # 前端表单已完成收集
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process chat: {str(e)}"
        )