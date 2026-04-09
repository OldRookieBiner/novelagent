"""Outline API routes"""

from fastapi import APIRouter, HTTPException, status, Depends
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
    CollectedInfoUpdate
)
from app.utils.auth import get_current_user
from app.agents.state import (
    STAGE_COLLECTING_INFO,
    STAGE_OUTLINE_GENERATING,
    STAGE_OUTLINE_CONFIRMING,
    STAGE_CHAPTER_COUNT_SUGGESTING,
    STAGE_CHAPTER_OUTLINES_GENERATING
)
from app.agents.nodes.outline_generation import generate_outline_node
from app.agents.nodes.info_collection import info_collection_node
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


@router.post("/{project_id}/outline", response_model=OutlineResponse)
async def generate_outline(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate outline using AI from collected info."""
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

    try:
        # Update project stage
        project.stage = STAGE_OUTLINE_GENERATING
        db.commit()

        # Get LLM service
        llm = get_llm_service(user_settings)

        # Prepare state for outline generation
        state = {
            "collected_info": outline.collected_info or {},
            "outline_title": outline.title,
            "outline_summary": outline.summary,
            "outline_plot_points": outline.plot_points or [],
        }

        # Generate outline using the agent node
        new_state = await generate_outline_node(state, llm)

        # Update outline with generated content
        outline.title = new_state.get("outline_title", "")
        outline.summary = new_state.get("outline_summary", "")
        outline.plot_points = new_state.get("outline_plot_points", [])

        # Update project stage to confirming
        project.stage = STAGE_OUTLINE_CONFIRMING

        db.commit()
        db.refresh(outline)

        return OutlineResponse.model_validate(outline)

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate outline: {str(e)}"
        )


@router.put("/{project_id}/outline", response_model=OutlineResponse)
async def update_outline(
    project_id: int,
    request: OutlineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update outline (title, summary, plot_points)."""
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

    # Confirm the outline
    outline.confirmed = True
    project.stage = STAGE_CHAPTER_COUNT_SUGGESTING

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

    # Update project stage to generate chapter outlines
    project.stage = STAGE_CHAPTER_OUTLINES_GENERATING

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
        project.stage = STAGE_OUTLINE_GENERATING

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

    # Check if project is in collecting_info stage
    if project.stage not in [STAGE_COLLECTING_INFO, STAGE_OUTLINE_GENERATING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project is not in info collection stage"
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
        state = {
            "collected_info": outline.collected_info or {},
            "messages": messages,
            "last_user_message": request.message,
        }

        # Run info collection node
        new_state = await info_collection_node(state, llm)

        # Update outline with new info and messages
        outline.collected_info = new_state.get("collected_info", {})
        outline.messages = new_state.get("messages", [])

        # Check if info is sufficient and update stage
        is_sufficient = new_state.get("stage") == STAGE_OUTLINE_GENERATING
        if is_sufficient:
            project.stage = STAGE_OUTLINE_GENERATING

        db.commit()

        # Build response
        collected_info = outline.collected_info
        return ChatResponse(
            response=new_state.get("last_assistant_message", ""),
            collected_info=CollectedInfo(**collected_info) if collected_info else None,
            is_info_sufficient=is_sufficient
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process chat: {str(e)}"
        )