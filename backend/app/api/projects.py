"""Projects API routes"""

import logging
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.outline import Outline, ChapterOutline
from app.models.chapter import Chapter
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse, ProjectDetail
)
from app.utils.auth import get_current_user

# 模块日志
logger = logging.getLogger(__name__)

router = APIRouter()


def get_project_detail(project: Project, db: Session) -> ProjectDetail:
    """Build project detail with additional info (optimized query)"""
    from sqlalchemy.orm import joinedload

    # Single query with joins to avoid N+1
    chapter_outlines = db.query(ChapterOutline).options(
        joinedload(ChapterOutline.chapter)
    ).filter(
        ChapterOutline.project_id == project.id
    ).order_by(ChapterOutline.chapter_number).all()

    chapter_count = len(chapter_outlines)
    completed_chapters = sum(
        1 for co in chapter_outlines
        if co.chapter and co.chapter.review_passed
    )

    progress_percentage = (completed_chapters / chapter_count * 100) if chapter_count > 0 else 0

    return ProjectDetail(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        stage=project.stage,
        target_words=project.target_words,
        total_words=project.total_words,
        created_at=project.created_at,
        updated_at=project.updated_at,
        chapter_count=chapter_count,
        completed_chapters=completed_chapters,
        progress_percentage=round(progress_percentage, 1)
    )


@router.get("/", response_model=ProjectListResponse)
async def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    列出当前用户的所有项目
    直接返回包含进度详情的项目列表，避免前端 N+1 请求
    """
    projects = db.query(Project).filter(Project.user_id == current_user.id).all()
    # 直接返回 ProjectDetail 而不是 ProjectResponse，避免前端额外请求
    project_details = [get_project_detail(p, db) for p in projects]
    return ProjectListResponse(
        projects=project_details,
        total=len(projects)
    )


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new project"""
    try:
        project = Project(
            user_id=current_user.id,
            name=request.name,
            target_words=request.target_words
        )
        db.add(project)
        db.flush()  # Get the ID without committing

        # Create empty outline
        outline = Outline(project_id=project.id)
        db.add(outline)

        db.commit()
        db.refresh(project)

        return ProjectResponse.model_validate(project)
    except Exception as e:
        db.rollback()
        # 记录详细错误日志，便于调试
        logger.error(f"创建项目失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建项目失败: {str(e)}"
        )


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get project by ID"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    return get_project_detail(project, db)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    request: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update project"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    if request.name is not None:
        project.name = request.name
    if request.stage is not None:
        project.stage = request.stage
    if request.target_words is not None:
        project.target_words = request.target_words

    db.commit()
    db.refresh(project)

    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete project"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    db.delete(project)
    db.commit()

    return {"success": True, "message": "Project deleted"}