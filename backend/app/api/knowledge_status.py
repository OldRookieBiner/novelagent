"""Knowledge base status API

返回项目知识库完整性状态，供前端底部状态栏展示。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.utils.project import get_project_for_user
from app.agents.agent_context import validate_prerequisites

router = APIRouter()


@router.get("/{project_id}/knowledge-status")
async def get_knowledge_status(
    project_id: int,
    current_chapter: int | None = Query(None, description="当前章节号"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取项目知识库完整性状态"""
    get_project_for_user(project_id, current_user.id, db)

    result = validate_prerequisites(project_id, current_chapter)
    return result
