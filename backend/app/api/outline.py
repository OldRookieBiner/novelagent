"""Outline API routes — CRUD only

AI outline generation is handled by the Agent (chat endpoint in
api/agent.py). This module only provides REST endpoints for reading
and modifying outline data.
"""

import logging
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.outline import Outline
from app.schemas.outline import (
    OutlineResponse,
    OutlineUpdate,
    ChapterCountRequest,
    CollectedInfoUpdate,
)
from app.utils.auth import get_current_user
from app.utils.project import get_project_for_user, get_project_and_outline
from app.utils.workflow import get_or_create_workflow_state
from app.agents.constants import Phase, DEFAULT_CHAPTER_COUNT

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


@router.put("/{project_id}/outline", response_model=OutlineResponse)
async def update_outline(
    project_id: int,
    request: OutlineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update outline (title, summary, plot_points, collected_info, inspiration_template).

    confirmed 仅作为「作者定稿」展示标记，不再阻止编辑：已确认大纲依旧可随时修改。
    """
    _, outline = get_project_and_outline(project_id, current_user.id, db)

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
    """Confirm outline and move to structure phase.

    confirmed 是「作者定稿」书签，不再锁死编辑。本接口幂等：
    可重复调用，已确认的大纲再次确认会直接刷新阶段而不报错。
    """
    project, outline = get_project_and_outline(project_id, current_user.id, db)

    if not outline.title or not outline.summary:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outline must have title and summary before confirming"
        )

    # confirmed 为定稿书签 + 进入结构阶段的便捷入口；幂等：重复确认直接刷新阶段，不报错
    if outline.chapter_count_suggested <= 0:
        outline.chapter_count_suggested = DEFAULT_CHAPTER_COUNT
    outline.chapter_count_confirmed = True

    outline.confirmed = True
    workflow_state = get_or_create_workflow_state(db, project_id)
    workflow_state.stage = Phase.STRUCTURE.value

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
    """Set chapter count for the outline.

    章节数可独立设置，不再要求大纲先确认。
    """
    project, outline = get_project_and_outline(project_id, current_user.id, db)

    if request.chapter_count < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chapter count must be at least 1"
        )

    outline.chapter_count_suggested = request.chapter_count
    outline.chapter_count_confirmed = True

    workflow_state = get_or_create_workflow_state(db, project_id)
    workflow_state.stage = Phase.STRUCTURE.value

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
    """Update collected info directly (skip chat if desired).

    confirmed 不再阻止编辑，已确认大纲依旧可调整 collected_info。
    """
    project, outline = get_project_and_outline(project_id, current_user.id, db)

    current_info = dict(outline.collected_info or {})
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

    if request.inspiration_template is not None:
        outline.inspiration_template = request.inspiration_template

    db.commit()
    db.refresh(outline)

    return OutlineResponse.model_validate(outline)
