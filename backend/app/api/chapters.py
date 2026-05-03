"""Chapters API routes"""

import json
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.outline import Outline, ChapterOutline
from app.models.chapter import Chapter
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
from app.utils.deps import get_user_settings_or_raise, get_llm_for_context
from app.utils.project import get_project_for_user
from app.utils.workflow import get_or_create_workflow_state
from app.utils.error import format_sse_error
from app.agents.state import (
    STAGE_CHAPTER_OUTLINES,
    STAGE_WRITING
)
from app.agents.nodes.chapter_generation import (
    generate_chapter_outlines_node,
    generate_chapter_outlines_stream,
)

router = APIRouter()


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

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"create_chapter_outlines: project_id={project_id}, outline.confirmed={outline.confirmed}, outline.chapter_count_confirmed={outline.chapter_count_confirmed}")

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

    user_settings = get_user_settings_or_raise(current_user, db)

    # 更新工作流状态
    workflow_state = get_or_create_workflow_state(db, project_id)
    workflow_state.stage = STAGE_CHAPTER_OUTLINES
    db.commit()

    # Get LLM service
    llm = get_llm_for_context(request, current_user, user_settings, db)

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
            # Send error event (sanitized)
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


@router.put("/{project_id}/chapter-outlines/{chapter_num}/confirm", response_model=ChapterOutlineResponse)
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

    # Check if all chapter outlines are confirmed - 使用两个简单查询
    from sqlalchemy import func

    total_outlines = db.query(func.count(ChapterOutline.id)).filter(
        ChapterOutline.project_id == project_id
    ).scalar() or 0

    confirmed_outlines = db.query(func.count(ChapterOutline.id)).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.confirmed == True
    ).scalar() or 0

    # 确认后，已确认数需要 +1（因为当前章节还未 commit）
    confirmed_outlines += 1

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
    request: Request = None,
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

    user_settings = get_user_settings_or_raise(current_user, db)

    # Get LLM service
    llm = get_llm_for_context(request, current_user, user_settings, db)

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
        """直接调用 LLM 流式生成章节内容，绕过 LangGraph 事件系统

        LangGraph 的 astream_events 无法捕获自定义 LLMService.chat_stream
        的 on_chat_model_stream 事件（LLMService 不是 LangChain 组件），
        因此直接使用 llm.chat_stream 生成内容并手动构建 SSE 事件。
        """
        from app.agents.nodes.chapter_generation import (
            generate_chapter_content_stream,
            clean_chapter_content,
        )
        from app.agents.nodes.utils import (
            _format_chapter_outline_str,
            format_characters_info,
            format_relations_info,
            format_evolution_info,
            format_world_setting,
        )
        from app.agents.prompts import GENERATE_CHAPTER_CONTENT_PROMPT

        # 获取上一章结尾
        previous_ending = ""
        if chapter_outline.chapter_number > 1:
            prev_outline = (
                db.query(ChapterOutline)
                .filter(
                    ChapterOutline.project_id == project_id,
                    ChapterOutline.chapter_number == chapter_outline.chapter_number - 1,
                )
                .first()
            )
            if prev_outline and prev_outline.chapter and prev_outline.chapter.content:
                prev_content = prev_outline.chapter.content
                previous_ending = prev_content[-500:] if len(prev_content) > 500 else prev_content

        # 构建章节大纲 dict
        chapter_outline_dict = {
            "chapter_number": chapter_outline.chapter_number,
            "title": chapter_outline.title or "",
            "scene": chapter_outline.scene or "",
            "characters": chapter_outline.characters or "",
            "plot": chapter_outline.plot or "",
            "conflict": chapter_outline.conflict or "",
            "ending": chapter_outline.ending or "",
            "target_words": chapter_outline.target_words or 3000,
        }

        # 格式化 prompt 各部分
        info = outline.collected_info or {}
        outline_str = _format_chapter_outline_str(chapter_outline_dict)
        chars_str = format_characters_info(state)
        relations_str = format_relations_info(state, chapter_outline_dict.get("chapter_number", 1))
        evolution_str, evolution_plans_str = format_evolution_info(state, chapter_outline_dict.get("chapter_number", 1))
        world_str = format_world_setting(state)
        combined_characters_str = chars_str + relations_str + evolution_str + evolution_plans_str
        target_words = chapter_outline_dict.get("target_words", 3000)

        prompt = GENERATE_CHAPTER_CONTENT_PROMPT.format(
            chapter_outline=outline_str,
            previous_ending=previous_ending,
            genre=info.get("novelType", "未指定"),
            main_characters=combined_characters_str,
            world_setting=world_str,
            style_preference=info.get("stylePreference", "未指定"),
            target_words=target_words,
        )

        yield f"event: node_start\ndata: {json.dumps({'message': 'Starting generation'})}\n\n"

        accumulated_content = ""
        try:
            async for chunk in llm.chat_stream([{"role": "user", "content": prompt}]):
                accumulated_content += chunk
                yield f"event: chunk\ndata: {json.dumps({'content': chunk})}\n\n"

            content = clean_chapter_content(accumulated_content) if accumulated_content else ""
            if not content:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="AI 返回内容为空，请重试",
                )

            word_count = len(content)
            chapter.content = content
            chapter.word_count = word_count
            db.commit()

            chapter_response = {
                "id": chapter.id,
                "chapter_outline_id": chapter.chapter_outline_id,
                "content": content,
                "word_count": word_count,
            }
            yield f"event: done\ndata: {json.dumps(chapter_response)}\n\n"

        except HTTPException:
            raise
        except Exception as e:
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

    user_settings = get_user_settings_or_raise(current_user, db)

    # Get LLM service
    llm = get_llm_for_context(request, current_user, user_settings, db)

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

    from app.agents.streaming import create_single_node_graph
    from app.agents.nodes.review import review_node, check_review_passed

    graph_state = {
        "project_id": project_id,
        "current_chapter": chapter_num + 1,
        "chapter_outlines": [
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
            for co in db.query(ChapterOutline)
            .filter(ChapterOutline.project_id == project_id)
            .order_by(ChapterOutline.chapter_number)
            .all()
        ],
        "written_chapters": [
            {"chapter_number": chapter_num, "content": chapter.content}
        ],
        "collected_info": outline.collected_info or {},
        "outline_characters": outline.characters or [],
        "outline_world_setting": outline.world_setting or {},
        "review_result": None,
        "llm_config_id": request.llm_config_id if request else None,
    }

    graph = create_single_node_graph(review_node)
    config = {"configurable": {"thread_id": f"review-{project_id}-{chapter_num}"}}

    result = await graph.ainvoke(graph_state, config)

    review_result = result.get("review_result", {})
    if review_result:
        chapter.review_passed = check_review_passed(review_result)
        chapter.review_feedback = review_result.get("raw_response")
        chapter.review_result = review_result
        db.commit()

    return ReviewResponse(
        passed=chapter.review_passed,
        feedback=chapter.review_feedback or "",
        issues=review_result.get("issues", []) if review_result else [],
    )