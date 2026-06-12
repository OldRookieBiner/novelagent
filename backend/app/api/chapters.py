"""Chapters API routes — CRUD only

AI generation/review/rewrite operations are handled by the Agent
(chat endpoint in api/agent.py). This module only provides REST
endpoints for reading and modifying chapter data.
"""

import logging
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.outline import Outline, ChapterOutline
from app.models.chapter import Chapter
from app.models.workflow_state import WorkflowState
from app.utils.auth import get_current_user
from app.utils.project import get_project_for_user
from app.utils.workflow import get_or_create_workflow_state
from app.agents.constants import Phase
from app.schemas.chapter import (
    ChapterOutlineUpdate,
    ChapterOutlineResponse,
    ChapterContentUpdate,
    ChapterResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


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

    from sqlalchemy.orm import joinedload

    chapter_outlines = db.query(ChapterOutline).options(
        joinedload(ChapterOutline.chapter)
    ).filter(
        ChapterOutline.project_id == project_id
    ).order_by(ChapterOutline.chapter_number).all()

    response = []
    for co in chapter_outlines:
        has_content = co.chapter is not None

        outline_dict = {
            "id": co.id,
            "project_id": co.project_id,
            "chapter_number": co.chapter_number,
            "arc_id": co.arc_id,
            "title": co.title,
            "scene": co.scene,
            "characters": co.characters,
            "plot": co.plot,
            "conflict": co.conflict,
            "turning_point": co.turning_point,
            "hook": co.hook,
            "transition": co.transition,
            "ending": co.ending,
            "opening_state": co.opening_state,
            "emotional_arc": co.emotional_arc,
            "key_scenes": co.key_scenes,
            "pacing_note": co.pacing_note,
            "target_words": co.target_words,
            "confirmed": co.confirmed,
            "created_at": co.created_at,
            "has_content": has_content
        }
        response.append(ChapterOutlineResponse(**outline_dict))

    return response


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

    chapter_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num
    ).first()

    if not chapter_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter outline {chapter_num} not found"
        )

    if chapter_outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update a confirmed chapter outline"
        )

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
    if request.turning_point is not None:
        chapter_outline.turning_point = request.turning_point
    if request.hook is not None:
        chapter_outline.hook = request.hook
    if request.transition is not None:
        chapter_outline.transition = request.transition
    if request.ending is not None:
        chapter_outline.ending = request.ending
    if request.target_words is not None:
        chapter_outline.target_words = request.target_words
    if request.opening_state is not None:
        chapter_outline.opening_state = request.opening_state
    if request.emotional_arc is not None:
        chapter_outline.emotional_arc = request.emotional_arc
    if request.key_scenes is not None:
        chapter_outline.key_scenes = request.key_scenes
    if request.pacing_note is not None:
        chapter_outline.pacing_note = request.pacing_note

    db.commit()
    db.refresh(chapter_outline)

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
        turning_point=chapter_outline.turning_point,
        hook=chapter_outline.hook,
        transition=chapter_outline.transition,
        ending=chapter_outline.ending,
        opening_state=chapter_outline.opening_state,
        emotional_arc=chapter_outline.emotional_arc,
        key_scenes=chapter_outline.key_scenes,
        pacing_note=chapter_outline.pacing_note,
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

    chapter_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num
    ).first()

    if not chapter_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter outline {chapter_num} not found"
        )

    if chapter_outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chapter outline is already confirmed"
        )

    if not chapter_outline.title or not chapter_outline.plot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chapter outline must have title and plot before confirming"
        )

    chapter_outline.confirmed = True

    from sqlalchemy import func

    total_outlines = db.query(func.count(ChapterOutline.id)).filter(
        ChapterOutline.project_id == project_id
    ).scalar() or 0

    confirmed_outlines = db.query(func.count(ChapterOutline.id)).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.confirmed == True
    ).scalar() or 0

    confirmed_outlines += 1

    if total_outlines > 0 and confirmed_outlines == total_outlines:
        workflow_state = get_or_create_workflow_state(db, project_id)
        workflow_state.stage = Phase.WRITING.value

    db.commit()
    db.refresh(chapter_outline)

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
        turning_point=chapter_outline.turning_point,
        hook=chapter_outline.hook,
        transition=chapter_outline.transition,
        ending=chapter_outline.ending,
        opening_state=chapter_outline.opening_state,
        emotional_arc=chapter_outline.emotional_arc,
        key_scenes=chapter_outline.key_scenes,
        pacing_note=chapter_outline.pacing_note,
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

    chapter_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num
    ).first()

    if not chapter_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter outline {chapter_num} not found"
        )

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

    chapter_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num
    ).first()

    if not chapter_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter outline {chapter_num} not found"
        )

    existing_chapter = db.query(Chapter).filter(
        Chapter.chapter_outline_id == chapter_outline.id
    ).first()

    if existing_chapter:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chapter {chapter_num} already exists"
        )

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

    chapter_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num
    ).first()

    if not chapter_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter outline {chapter_num} not found"
        )

    chapter = db.query(Chapter).filter(
        Chapter.chapter_outline_id == chapter_outline.id
    ).first()

    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter {chapter_num} content not found"
        )

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
