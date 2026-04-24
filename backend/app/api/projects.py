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
from app.models.workflow_state import WorkflowState
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse,
    ProjectListResponse, ProjectDetailResponse, WorkflowStateResponse
)
from app.utils.auth import get_current_user

# 模块日志
logger = logging.getLogger(__name__)

router = APIRouter()


def get_or_create_workflow_state(db: Session, project_id: int, thread_id: str = "main") -> WorkflowState:
    """获取或创建工作流状态

    确保每个项目都有对应的工作流状态记录。
    如果不存在则创建默认状态。

    Args:
        db: 数据库会话
        project_id: 项目 ID
        thread_id: 工作流线程 ID，默认为 "main"

    Returns:
        WorkflowState 实例
    """
    workflow_state = db.query(WorkflowState).filter(
        WorkflowState.project_id == project_id,
        WorkflowState.thread_id == thread_id
    ).first()

    if not workflow_state:
        workflow_state = WorkflowState(
            project_id=project_id,
            thread_id=thread_id
        )
        db.add(workflow_state)
        db.flush()  # 获取 ID 但不提交，让调用者决定何时提交

    return workflow_state


def get_project_detail(project: Project, db: Session) -> ProjectDetailResponse:
    """构建项目详情，包含工作流状态和章节进度（优化查询）"""
    from sqlalchemy.orm import joinedload

    # 单次查询带关联加载，避免 N+1 问题
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

    # 获取工作流状态
    workflow_state = get_or_create_workflow_state(db, project.id)

    return ProjectDetailResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        target_words=project.target_words,
        total_words=project.total_words,
        created_at=project.created_at,
        updated_at=project.updated_at,
        workflow_state=WorkflowStateResponse.model_validate(workflow_state),
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
    # 直接返回 ProjectDetailResponse 而不是 ProjectResponse，避免前端额外请求
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
    """创建新项目，同时创建关联的大纲和工作流状态"""
    try:
        project = Project(
            user_id=current_user.id,
            name=request.name,
            target_words=request.target_words
        )
        db.add(project)
        db.flush()  # 获取 ID 但不提交

        # 创建空大纲
        outline = Outline(project_id=project.id)
        db.add(outline)

        # 创建工作流状态
        workflow_state = WorkflowState(project_id=project.id)
        db.add(workflow_state)

        db.commit()
        db.refresh(project)

        return ProjectResponse(
            id=project.id,
            user_id=project.user_id,
            name=project.name,
            target_words=project.target_words,
            total_words=project.total_words,
            created_at=project.created_at,
            updated_at=project.updated_at,
            workflow_state=WorkflowStateResponse.model_validate(workflow_state)
        )
    except Exception as e:
        db.rollback()
        # 记录详细错误日志，便于调试
        logger.error(f"创建项目失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建项目失败: {str(e)}"
        )


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取项目详情"""
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
    """更新项目"""
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
    if request.target_words is not None:
        project.target_words = request.target_words

    db.commit()
    db.refresh(project)

    # 获取工作流状态
    workflow_state = get_or_create_workflow_state(db, project.id)

    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        target_words=project.target_words,
        total_words=project.total_words,
        created_at=project.created_at,
        updated_at=project.updated_at,
        workflow_state=WorkflowStateResponse.model_validate(workflow_state)
    )


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除项目（级联删除关联数据）"""
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
