"""项目工具函数"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.outline import Outline


def get_project_for_user(
    project_id: int,
    user_id: int,
    db: Session
) -> Project:
    """获取项目并验证所有权

    Args:
        project_id: 项目 ID
        user_id: 用户 ID
        db: 数据库会话

    Returns:
        Project 实例

    Raises:
        HTTPException: 项目不存在或无权访问
    """
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


def get_project_and_outline(
    project_id: int,
    user_id: int,
    db: Session
) -> tuple[Project, Outline]:
    """获取项目和大纲，验证所有权

    Args:
        project_id: 项目 ID
        user_id: 用户 ID
        db: 数据库会话

    Returns:
        (Project, Outline) 元组

    Raises:
        HTTPException: 项目或大纲不存在
    """
    project = get_project_for_user(project_id, user_id, db)

    outline = db.query(Outline).filter(
        Outline.project_id == project_id
    ).first()

    if not outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outline not found"
        )

    return project, outline
