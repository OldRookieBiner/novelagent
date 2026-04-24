"""Chapters API routes"""

import json
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.outline import Outline, ChapterOutline
from app.models.chapter import Chapter
from app.models.settings import UserSettings
from app.schemas.chapter import (
    ChapterOutlineResponse,
    ChapterOutlineUpdate,
    ChapterResponse,
    ChapterContentUpdate,
    ReviewRequest,
    ReviewResponse
)
from app.schemas.outline import ChapterOutlinesGenerateRequest
from app.utils.auth import get_current_user
from app.utils.llm import get_llm_for_user
from app.utils.workflow import get_or_create_workflow_state
from app.agents.state import (
    STAGE_CHAPTER_OUTLINES,
    STAGE_WRITING
)
from app.agents.nodes.chapter_generation import (
    generate_chapter_outlines_node,
    generate_chapter_outlines_stream,
    generate_chapter_content_stream,
)
from app.agents.nodes.review import review_chapter_node

router = APIRouter()


def get_project_for_user(
    project_id: int,
    user_id: int,
    db: Session
) -> Project:
    """Get project, verifying ownership."""
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


def get_outline_for_project(
    project_id: int,
    db: Session
) -> Outline:
    """Get outline for a project."""
    outline = db.query(Outline).filter(
        Outline.project_id == project_id
    ).first()

    if not outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outline not found. Please create an outline first."
        )

    return outline


@router.get("/{project_id}/chapter-outlines", response_model=List[ChapterOutlineResponse])
async def list_chapter_outlines(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all chapter outlines for a project."""
    project = get_project_for_user(project_id, current_user.id, db)

    # 使用 LEFT JOIN 一次性获取所有章节数据，避免 N+1 查询
    from sqlalchemy.orm import joinedload
    from sqlalchemy import func

    # 获取所有章节大纲，并预加载关联的章节
    chapter_outlines = db.query(ChapterOutline).options(
        joinedload(ChapterOutline.chapter)
    ).filter(
        ChapterOutline.project_id == project_id
    ).order_by(ChapterOutline.chapter_number).all()

    # Build response with has_content flag
    response = []
    for co in chapter_outlines:
        # 检查是否有对应的章节内容（已通过 JOIN 加载）
        has_content = co.chapter is not None

        outline_dict = {
            "id": co.id,
            "project_id": co.project_id,
            "chapter_number": co.chapter_number,
            "title": co.title,
            "scene": co.scene,
            "characters": co.characters,
            "plot": co.plot,
            "conflict": co.conflict,
            "ending": co.ending,
            "target_words": co.target_words,
            "confirmed": co.confirmed,
            "created_at": co.created_at,
            "has_content": has_content
        }
        response.append(ChapterOutlineResponse(**outline_dict))

    return response


@router.post("/{project_id}/chapter-outlines")
async def create_chapter_outlines(
    project_id: int,
    request: ChapterOutlinesGenerateRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate all chapter outlines using AI with SSE streaming."""
    project = get_project_for_user(project_id, current_user.id, db)
    outline = get_outline_for_project(project_id, db)

    # Check if outline is confirmed and chapter count is set
    if not outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outline must be confirmed before generating chapter outlines"
        )

    if not outline.chapter_count_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chapter count must be set before generating chapter outlines"
        )

    # Check if chapter outlines already exist
    existing = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chapter outlines already exist. Delete them first to regenerate."
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
    workflow_state.stage = STAGE_CHAPTER_OUTLINES
    db.commit()

    # Get LLM service
    llm_config_id = request.llm_config_id if request else None
    llm = get_llm_for_user(current_user.id, user_settings, db, llm_config_id)

    # Prepare state for chapter outline generation
    state = {
        "project_id": project_id,
        "outline_title": outline.title,
        "outline_summary": outline.summary,
        "outline_plot_points": outline.plot_points or [],
        # v0.6.1 增强字段
        "outline_characters": outline.characters or [],
        "outline_world_setting": outline.world_setting or {},
        "outline_emotional_curve": outline.emotional_curve,
        "chapter_count_suggested": outline.chapter_count_suggested,
        "collected_info": outline.collected_info or {},
    }

    # Create async generator for SSE streaming
    async def stream_generator():
        """Generate chapter outlines one by one and stream via SSE."""
        created_outlines = []

        try:
            async for event in generate_chapter_outlines_stream(state, llm):
                if event["type"] == "progress":
                    # Save chapter to database
                    chapter_data = event["chapter"]
                    chapter_outline = ChapterOutline(
                        project_id=project_id,
                        chapter_number=chapter_data.get("chapter_number", 1),
                        title=chapter_data.get("title"),
                        scene=chapter_data.get("scene"),
                        characters=chapter_data.get("characters"),
                        plot=chapter_data.get("plot"),
                        conflict=chapter_data.get("conflict"),
                        ending=chapter_data.get("ending"),
                        target_words=chapter_data.get("target_words", 3000),
                        confirmed=False
                    )
                    db.add(chapter_outline)
                    db.commit()
                    db.refresh(chapter_outline)
                    created_outlines.append(chapter_outline)

                    # Send progress event
                    progress_data = {
                        "chapter_number": event["chapter_number"],
                        "total": event["total"],
                        "chapter": {
                            "id": chapter_outline.id,
                            "chapter_number": chapter_outline.chapter_number,
                            "title": chapter_outline.title,
                        }
                    }
                    yield f"event: progress\ndata: {json.dumps(progress_data)}\n\n"

                elif event["type"] == "done":
                    # 更新工作流状态
                    workflow_state = get_or_create_workflow_state(db, project_id)
                    workflow_state.stage = STAGE_CHAPTER_OUTLINES
                    db.commit()

                    # Send completion event
                    completion_data = {
                        "total": len(created_outlines),
                        "stage": STAGE_CHAPTER_OUTLINES
                    }
                    yield f"event: done\ndata: {json.dumps(completion_data)}\n\n"

        except Exception as e:
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


@router.put("/{project_id}/chapter-outlines/{chapter_num}", response_model=ChapterOutlineResponse)
async def update_chapter_outline(
    project_id: int,
    chapter_num: int,
    request: ChapterOutlineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a specific chapter outline."""
    project = get_project_for_user(project_id, current_user.id, db)

    # Find the chapter outline
    chapter_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num
    ).first()

    if not chapter_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter outline {chapter_num} not found"
        )

    # Check if already confirmed
    if chapter_outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update a confirmed chapter outline"
        )

    # Update fields if provided
    if request.title is not None:
        chapter_outline.title = request.title
    if request.scene is not None:
        chapter_outline.scene = request.scene
    if request.characters is not None:
        chapter_outline.characters = request.characters
    if request.plot is not None:
        chapter_outline.plot = request.plot
    if request.conflict is not None:
        chapter_outline.conflict = request.conflict
    if request.ending is not None:
        chapter_outline.ending = request.ending
    if request.target_words is not None:
        chapter_outline.target_words = request.target_words

    db.commit()
    db.refresh(chapter_outline)

    # Check if chapter content exists
    has_content = db.query(Chapter).filter(
        Chapter.chapter_outline_id == chapter_outline.id
    ).first() is not None

    return ChapterOutlineResponse(
        id=chapter_outline.id,
        project_id=chapter_outline.project_id,
        chapter_number=chapter_outline.chapter_number,
        title=chapter_outline.title,
        scene=chapter_outline.scene,
        characters=chapter_outline.characters,
        plot=chapter_outline.plot,
        conflict=chapter_outline.conflict,
        ending=chapter_outline.ending,
        target_words=chapter_outline.target_words,
        confirmed=chapter_outline.confirmed,
        created_at=chapter_outline.created_at,
        has_content=has_content
    )


@router.post("/{project_id}/chapter-outlines/{chapter_num}/confirm", response_model=ChapterOutlineResponse)
async def confirm_chapter_outline(
    project_id: int,
    chapter_num: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Confirm a chapter outline."""
    project = get_project_for_user(project_id, current_user.id, db)

    # Find the chapter outline
    chapter_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num
    ).first()

    if not chapter_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter outline {chapter_num} not found"
        )

    # Check if already confirmed
    if chapter_outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chapter outline is already confirmed"
        )

    # Check if outline has required content
    if not chapter_outline.title or not chapter_outline.plot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chapter outline must have title and plot before confirming"
        )

    # Confirm the chapter outline
    chapter_outline.confirmed = True

    # Check if all chapter outlines are confirmed
    total_outlines = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id
    ).count()

    confirmed_outlines = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.confirmed == True
    ).count()

    # If all confirmed, update workflow state to chapter writing
    if total_outlines > 0 and confirmed_outlines == total_outlines:
        workflow_state = get_or_create_workflow_state(db, project_id)
        workflow_state.stage = STAGE_WRITING

    db.commit()
    db.refresh(chapter_outline)

    # Check if chapter content exists
    has_content = db.query(Chapter).filter(
        Chapter.chapter_outline_id == chapter_outline.id
    ).first() is not None

    return ChapterOutlineResponse(
        id=chapter_outline.id,
        project_id=chapter_outline.project_id,
        chapter_number=chapter_outline.chapter_number,
        title=chapter_outline.title,
        scene=chapter_outline.scene,
        characters=chapter_outline.characters,
        plot=chapter_outline.plot,
        conflict=chapter_outline.conflict,
        ending=chapter_outline.ending,
        target_words=chapter_outline.target_words,
        confirmed=chapter_outline.confirmed,
        created_at=chapter_outline.created_at,
        has_content=has_content
    )


# =============================================================================
# Chapter Content Endpoints
# =============================================================================

@router.get("/{project_id}/chapters/{chapter_num}", response_model=ChapterResponse)
async def get_chapter_content(
    project_id: int,
    chapter_num: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get chapter content by chapter number."""
    project = get_project_for_user(project_id, current_user.id, db)

    # Find the chapter outline
    chapter_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num
    ).first()

    if not chapter_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter outline {chapter_num} not found"
        )

    # Find the chapter content
    chapter = db.query(Chapter).filter(
        Chapter.chapter_outline_id == chapter_outline.id
    ).first()

    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter {chapter_num} content not found"
        )

    return ChapterResponse(
        id=chapter.id,
        chapter_outline_id=chapter.chapter_outline_id,
        content=chapter.content,
        word_count=chapter.word_count,
        review_passed=chapter.review_passed,
        review_feedback=chapter.review_feedback,
        review_result=chapter.review_result,
        rewrite_count=chapter.rewrite_count,
        created_at=chapter.created_at,
        updated_at=chapter.updated_at
    )


@router.post("/{project_id}/chapters/{chapter_num}", response_model=ChapterResponse, status_code=status.HTTP_201_CREATED)
async def create_chapter(
    project_id: int,
    chapter_num: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create an empty chapter entry linked to chapter outline."""
    project = get_project_for_user(project_id, current_user.id, db)

    # Find the chapter outline
    chapter_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num
    ).first()

    if not chapter_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter outline {chapter_num} not found"
        )

    # Check if chapter already exists
    existing_chapter = db.query(Chapter).filter(
        Chapter.chapter_outline_id == chapter_outline.id
    ).first()

    if existing_chapter:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chapter {chapter_num} already exists"
        )

    # Create new empty chapter
    chapter = Chapter(
        chapter_outline_id=chapter_outline.id,
        content=None,
        word_count=0,
        review_passed=False,
        review_feedback=None
    )

    db.add(chapter)
    db.commit()
    db.refresh(chapter)

    return ChapterResponse(
        id=chapter.id,
        chapter_outline_id=chapter.chapter_outline_id,
        content=chapter.content,
        word_count=chapter.word_count,
        review_passed=chapter.review_passed,
        review_feedback=chapter.review_feedback,
        review_result=chapter.review_result,
        rewrite_count=chapter.rewrite_count,
        created_at=chapter.created_at,
        updated_at=chapter.updated_at
    )


@router.put("/{project_id}/chapters/{chapter_num}", response_model=ChapterResponse)
async def update_chapter_content(
    project_id: int,
    chapter_num: int,
    request: ChapterContentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update chapter content."""
    project = get_project_for_user(project_id, current_user.id, db)

    # Find the chapter outline
    chapter_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num
    ).first()

    if not chapter_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter outline {chapter_num} not found"
        )

    # Find the chapter
    chapter = db.query(Chapter).filter(
        Chapter.chapter_outline_id == chapter_outline.id
    ).first()

    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter {chapter_num} content not found"
        )

    # Update content and word count (use len() for Chinese text)
    chapter.content = request.content
    chapter.word_count = len(request.content) if request.content else 0

    db.commit()
    db.refresh(chapter)

    return ChapterResponse(
        id=chapter.id,
        chapter_outline_id=chapter.chapter_outline_id,
        content=chapter.content,
        word_count=chapter.word_count,
        review_passed=chapter.review_passed,
        review_feedback=chapter.review_feedback,
        review_result=chapter.review_result,
        rewrite_count=chapter.rewrite_count,
        created_at=chapter.created_at,
        updated_at=chapter.updated_at
    )


@router.post("/{project_id}/chapters/{chapter_num}/generate")
async def generate_chapter(
    project_id: int,
    chapter_num: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate chapter content with SSE streaming."""
    project = get_project_for_user(project_id, current_user.id, db)
    outline = get_outline_for_project(project_id, db)

    # Find the chapter outline
    chapter_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num
    ).first()

    if not chapter_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter outline {chapter_num} not found"
        )

    # Check if chapter outline is confirmed
    if not chapter_outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chapter outline must be confirmed before generating content"
        )

    # Get or create chapter
    chapter = db.query(Chapter).filter(
        Chapter.chapter_outline_id == chapter_outline.id
    ).first()

    if not chapter:
        chapter = Chapter(
            chapter_outline_id=chapter_outline.id,
            content=None,
            word_count=0,
            review_passed=False,
            review_feedback=None
        )
        db.add(chapter)
        db.commit()
        db.refresh(chapter)

    # Get user settings for LLM
    user_settings = db.query(UserSettings).filter(
        UserSettings.user_id == current_user.id
    ).first()

    if not user_settings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User settings not found"
        )

    # Get LLM service
    llm = get_llm_for_user(current_user.id, user_settings, db)

    # Prepare state for generation
    state = {
        "project_id": project_id,
        "outline_title": outline.title,
        "outline_summary": outline.summary,
        # v0.6.1 增强字段
        "outline_characters": outline.characters or [],
        "outline_world_setting": outline.world_setting or {},
        "outline_emotional_curve": outline.emotional_curve,
        "collected_info": outline.collected_info or {},
    }

    # Prepare chapter outline dict for generation
    chapter_outline_dict = {
        "chapter_number": chapter_outline.chapter_number,
        "title": chapter_outline.title or "",
        "scene": chapter_outline.scene or "",
        "characters": chapter_outline.characters or "",
        "plot": chapter_outline.plot or "",
        "conflict": chapter_outline.conflict or "",
        "ending": chapter_outline.ending or "",
        "target_words": chapter_outline.target_words or 3000
    }

    # Create async generator for SSE streaming
    async def stream_generator():
        """Generate chapter content and stream via SSE."""
        accumulated_content = ""

        try:
            async for chunk in generate_chapter_content_stream(state, chapter_outline_dict, llm):
                accumulated_content += chunk
                # Send chunk as SSE event (JSON encode to preserve newlines)
                yield f"data: {json.dumps(chunk)}\n\n"

            # Update chapter content after streaming completes
            chapter.content = accumulated_content
            chapter.word_count = len(accumulated_content) if accumulated_content else 0
            db.commit()

            # Send completion event
            yield f"event: done\ndata: {chapter.word_count}\n\n"

        except Exception as e:
            # Send error event
            yield f"event: error\ndata: {str(e)}\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/{project_id}/chapters/{chapter_num}/review", response_model=ReviewResponse)
async def review_chapter(
    project_id: int,
    chapter_num: int,
    request: ReviewRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Review chapter quality."""
    project = get_project_for_user(project_id, current_user.id, db)
    outline = get_outline_for_project(project_id, db)

    # Find the chapter outline
    chapter_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num
    ).first()

    if not chapter_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter outline {chapter_num} not found"
        )

    # Find the chapter
    chapter = db.query(Chapter).filter(
        Chapter.chapter_outline_id == chapter_outline.id
    ).first()

    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter {chapter_num} content not found"
        )

    if not chapter.content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chapter has no content to review"
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

    # Get LLM service
    llm = get_llm_for_user(current_user.id, user_settings, db)

    # Prepare state for review
    state = {
        "project_id": project_id,
        "outline_title": outline.title,
        "outline_summary": outline.summary,
        # v0.6.1 增强字段
        "outline_characters": outline.characters or [],
        "outline_world_setting": outline.world_setting or {},
        "outline_emotional_curve": outline.emotional_curve,
        "collected_info": outline.collected_info or {},
    }

    # Prepare chapter outline dict for review
    chapter_outline_dict = {
        "chapter_number": chapter_outline.chapter_number,
        "title": chapter_outline.title or "",
        "plot": chapter_outline.plot or "",
    }

    # Get strictness from request
    strictness = request.strictness if request else "standard"

    try:
        # Perform review
        review_result = await review_chapter_node(
            state=state,
            chapter_content=chapter.content,
            chapter_outline=chapter_outline_dict,
            llm=llm,
            strictness=strictness
        )

        # Update chapter with review results
        chapter.review_passed = review_result.get("passed", False)
        chapter.review_feedback = review_result.get("feedback", "")
        # v0.6.1: 保存完整的审核结果
        chapter.review_result = review_result
        db.commit()

        return ReviewResponse(
            passed=review_result.get("passed", False),
            feedback=review_result.get("feedback", ""),
            issues=review_result.get("issues", [])
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to review chapter: {str(e)}"
        )